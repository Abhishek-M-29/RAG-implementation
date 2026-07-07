# Stage 5 of 14 — Structured Logging & Correlation IDs

**Source roadmap section covered:** §10 (Backend architecture — logging)
**Depends on:** Stage 4 — caching and memory layers must exist, since this stage instruments them.
**Followed by:** Stage 6 — Authorization & Rate Limiting.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure, never operated as a hosted service by us.

**Connector scope for the whole build:** only **FAISS** and **Google Gemini** are implemented; every other backend is a documented extension point.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** correctness fix #1 (PDF load errors caught and logged per-file, never silently swallowed) is already applied. This stage is where "logged" gets a real, structured destination instead of `print()`.

**What already exists when this stage starts:** working query/ingestion/health routes (Stage 3); four cache layers and session memory (Stage 4); the codebase still uses `print()` everywhere for anything resembling logging, exactly as the original POC did.

---

## 2. Why this stage exists

Logging is a **distinct concern from observability** (Stage 9) — logging tells you what happened to one request; observability tells you the health and behavior of the whole system over time. This stage's entire job is: replace every `print()` in the codebase with Python's `logging` module, structured as JSON, with a correlation ID that ties one request's full lifecycle together across ingestion, embedding, retrieval, and generation.

---

## 3. Logging setup

Create `ragframework/observability/logging.py`:

```python
# ragframework/observability/logging.py
import logging, sys
from pythonjsonlogger import jsonlogger

def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s %(request_id)s"
    ))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
```

Use one logger per module throughout the codebase: `logging.getLogger(__name__)`. Do not use the root logger directly from application code, and do not instantiate ad hoc `logging.Logger` objects with custom names — `__name__` gives every log line a traceable module origin for free.

## 4. Log levels — by meaning, not verbosity preference

| Level | Used for |
|---|---|
| `DEBUG` | Verbose internal state, dev-only (retrieved chunk text, full prompts) |
| `INFO` | Normal request lifecycle: request received, cache hit/miss, retrieval count, generation started/completed |
| `WARNING` | Recoverable issues: a retry attempt, an unusually slow query |
| `ERROR` | Failures: a PDF failed to parse, an LLM call failed after retries |
| `CRITICAL` | Service-level failures: vector store unreachable at startup |

Treat this table as a contract, not a suggestion. A common failure mode in this kind of migration is defaulting everything to `INFO` because it's the path of least resistance — resist that. If a log line represents a retry, it's `WARNING`, not `INFO`; if it represents a startup-blocking failure, it's `CRITICAL`, not `ERROR`.

## 5. Correlation ID

Generated once per request at the API gateway/middleware layer, propagated through the async call stack via `contextvars`, included in every log line (the `request_id` field in the formatter above) and echoed back to the client as an `X-Request-ID` response header.

This is what makes a single query's full trace — ingestion → embedding → retrieval → generation — greppable end to end from one ID, and it's what a support conversation ("my query returned a bad answer") anchors on. Implement this as FastAPI middleware in `ragframework/api/main.py`: generate a UUID if the incoming request has no `X-Request-ID` header (respect one if the caller already supplied it, e.g., from an upstream gateway), set it in a `contextvars.ContextVar`, and have `configure_logging`'s formatter pull it from there via a custom `logging.Filter` (the `%(request_id)s` field in the formatter string above needs a filter that injects it, since it isn't a standard `LogRecord` attribute).

## 6. What gets logged at each stage

- **Ingestion:** file received (name, size), chunk count produced, embedding time, upsert result, per-file errors — never silently swallowed, per correctness fix #1, which this stage gives a real structured home to instead of a bare `print()` or an unstructured log line.
- **Retrieval:** query hash (not raw text, by default — see redaction below), `top_k`, latency, number of chunks returned, cache hit/miss (from Stage 4's Layer 1).
- **Generation:** model name, prompt token count, completion token count, latency, cache hit/miss.

## 7. Destination

The framework emits structured JSON to stdout/stderr only — 12-factor-app style. It does **not** hardcode a destination (CloudWatch, ELK, Loki, Datadog). The adopter's own log collector agent picks it up. This matches the "bring your own infrastructure" guiding principle — the framework's job ends at emitting well-structured logs to stdout; shipping them anywhere is the adopter's concern, not something this stage builds.

## 8. Redaction

**Never log API keys or credentials, full stop.** These are pulled from `Settings` and must never appear in a log record — this includes not logging the entire `Settings` object or a connector's `config` dict at `DEBUG` level without first stripping secret fields.

Raw user query text is logged only under an explicit `log_raw_queries: bool = False` setting (add this to `Settings`); by default only a hash is logged, since query content can be sensitive. This is the same hash used for the Layer 1 cache key in Stage 4 — reuse it rather than computing a second hash.

---

## 9. What not to do in this stage

- **Do not leave any `print()` call in the codebase.** Grep for `print(` across the entire repository after this stage and confirm zero matches outside of the CLI's genuinely user-facing terminal output (e.g., a CLI progress message intended for a human running `ragframework index` interactively is a legitimate UI element, not a log line — use judgment, but default to `logging` even there where practical).
- **Do not log a `SecretStr` field by calling `str()` on the `Settings` object or a sub-dict without explicit redaction.** Pydantic's `SecretStr` helps but doesn't protect a raw `config` dict that was built from `.env` values before being wrapped.
- **Do not log raw query text by default.** The `log_raw_queries` flag must default to `False`.
- **Do not hardcode a log destination, format transport, or third-party logging SDK.** Structured JSON to stdout only.
- **Do not use `INFO` for everything.** Follow the level table in Section 4 by meaning.
- **Do not generate a new correlation ID partway through a request's lifecycle**, and do not let it get lost across an `await` boundary — verify it survives async calls by testing a request that spans multiple `await`s (e.g., embedding then LLM call) and confirming every log line carries the same `request_id`.

---

## 10. Instructions to the implementing agent

1. Add `pythonjsonlogger` (or equivalent) as a dependency.
2. Create `ragframework/observability/logging.py` with `configure_logging()` exactly as specified in Section 3.
3. Add a `contextvars.ContextVar` for the request ID and a `logging.Filter` subclass that injects it into every `LogRecord` as `request_id` (defaulting to `"-"` or similar for log lines emitted outside a request context, e.g., during CLI usage or startup).
4. Add FastAPI middleware in `ragframework/api/main.py` that reads/generates `X-Request-ID`, sets the context var, calls `next()`, and echoes the header back on the response.
5. Call `configure_logging()` once at process startup (both in `api/main.py`'s app creation and in `cli.py`'s entry point), reading the level from a new `Settings.log_level: str = "INFO"` field.
6. Add `Settings.log_raw_queries: bool = False`.
7. Go through every module — `core/ingestion.py`, `core/chunking.py`, `core/retrieval.py`, `core/generation.py`, `vectorstores/faiss_store.py`, `llms/google_genai.py`, `cache/*`, `memory/*`, `api/routers/*` — and replace every `print()` with an appropriately-leveled `logger.info/warning/error/critical(...)` call, using `logging.getLogger(__name__)` in each module.
8. Add the specific log lines enumerated in Section 6 at their respective stages, using the query hash (shared with Stage 4's cache key) rather than raw text unless `log_raw_queries` is set.
9. Audit every log call for accidental secret exposure — specifically anywhere a `config` dict or `Settings` instance might be interpolated into a message string.
10. Manually verify: send a request with no `X-Request-ID` header and confirm one is generated and echoed back; send a request with an existing `X-Request-ID` and confirm it's preserved end to end; grep the emitted logs for the request's ID and confirm ingestion/retrieval/generation log lines for that one request all share it; confirm an API key never appears anywhere in stdout across a full ingestion + query cycle.

---

## 11. Definition of done

- [ ] Zero `print()` calls remain outside legitimate interactive CLI output.
- [ ] All logs are structured JSON to stdout, using `logging.getLogger(__name__)` per module.
- [ ] Log levels follow the meaning-based table in Section 4, not a blanket `INFO`.
- [ ] Every log line includes a `request_id` field, correctly propagated across async boundaries within one request.
- [ ] `X-Request-ID` is echoed back on every response, generated if absent, preserved if present.
- [ ] Raw query text never appears in logs unless `log_raw_queries=True` is explicitly set.
- [ ] No API key, credential, or other secret appears in any log line under any configuration.
- [ ] Ingestion, retrieval, and generation each log the specific fields listed in Section 6.

## 12. Handoff to Stage 6

Stage 6 adds optional API-key auth and rate limiting. It will use this stage's request-ID/logging infrastructure to log authorization failures and rate-limit rejections at `WARNING`/`ERROR` as appropriate, and it must be careful never to log the API key itself when logging an auth failure — only whether a key was present/valid and which scope was required.
