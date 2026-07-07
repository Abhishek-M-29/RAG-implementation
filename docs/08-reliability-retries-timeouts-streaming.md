# Stage 8 of 14 — Reliability: Retries, Timeouts & Streaming

**Source roadmap section covered:** §13 (Backend architecture — reliability)
**Depends on:** Stage 7 — the async ingestion pipeline must exist, since its worker call sites are one of the two places this stage's reliability wrapping applies.
**Followed by:** Stage 9 — Observability.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure, never operated as a hosted service by us.

**Connector scope for the whole build:** only **FAISS** and **Google Gemini** are implemented; every other backend is a documented extension point.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** the seven correctness fixes are already applied.

**What already exists when this stage starts:** `ragframework/llms/google_genai.py` (Stage 2) constructs a `ChatGoogleGenerativeAI` instance but has no retry/timeout/streaming logic yet, by explicit deferral from that stage; `ragframework/api/routers/query.py` (Stage 3) designed its response type with streaming in mind but returns a full answer synchronously; the async ingestion worker (Stage 7) makes embedding and upsert calls with no retry wrapping yet.

---

## 2. Why this stage exists

This is the stage the connector layer has been deliberately left unfinished for, twice: Stage 2 explicitly deferred retries/timeouts/streaming on the Gemini connector, and Stage 7 explicitly deferred retry wrapping on the ingestion worker's external calls. Building reliability **once, here, at the connector layer** means every current and future LLM connector inherits it automatically — a future OpenAI or Anthropic connector gets retries "for free" because it also produces a `BaseChatModel`, and this stage's retry wrapper operates on that shared interface, not on `ChatGoogleGenerativeAI` specifically.

---

## 3. Retries with exponential backoff

Use `tenacity` on transient LLM API errors (rate limits, transient 5xx responses, connection resets). Apply this at the connector layer — wrap the calls inside `ragframework/llms/google_genai.py`'s construction or invocation path, not inside `core/generation.py`, so the retry behavior is a property of "being an LLM connector," not of the generation chain that calls it.

Apply the same principle to the vector store connector's external calls where relevant (e.g., a future networked connector like pgvector/Qdrant would need this even more than local FAISS does — but FAISS is local and mostly doesn't need network retries; don't manufacture retry logic around local file I/O that doesn't need it).

Be specific about what counts as "transient" — do not retry on errors that indicate a bad request (e.g., an invalid API key, a malformed prompt) since retrying those just wastes time and burns rate-limit budget for a failure that will never succeed. Retry on rate limits and connection-level failures; fail immediately and loudly on authentication/configuration errors.

## 4. Explicit timeouts

Every external call needs an explicit timeout — vector store, LLM, object storage (from Stage 7). No external call in the framework should be allowed to hang indefinitely. Set sane defaults (e.g., `Settings.llm_timeout_seconds: float = 30.0`) and make them adopter-configurable, since acceptable latency varies by use case and by which model the adopter has configured.

## 5. Streaming responses

Surface the LLM connector's `.stream()` method (inherited automatically from LangChain's `BaseChatModel` interface — the connector doesn't need custom code to support it, just needs to expose it) through the query endpoint as Server-Sent Events. This is meaningfully better perceived latency than waiting for the full generation, and it's the piece Stage 3 deliberately left as a "full answer in one response" placeholder specifically so this stage could complete it without a breaking route signature change.

Update `ragframework/api/routers/query.py` to return a real `StreamingResponse` that yields tokens as they arrive from `.stream()`, rather than the Stage 3 placeholder that called `.invoke()` and returned the full text at once. The `QueryResponse` schema's shape (answer, sources, cached) still needs to be deliverable somehow at the end of a stream — document and implement a clear convention (e.g., a final SSE event carrying the structured metadata after the token stream completes) so the frontend (Stage 10) has something concrete to consume.

## 6. Token/context budget guard

Add a per-request guard that prevents one query from blowing past a reasonable cost envelope — e.g., a configurable maximum combined prompt+completion token budget (`Settings.max_tokens_per_request`). If a request would exceed it (for example, retrieval returning enough chunks to build an oversized prompt), fail clearly before spending money on the LLM call, rather than either silently truncating context in a way that changes answer quality unpredictably or letting an unbounded request through.

## 7. Fail-fast on missing config

If a required connector config value (API key, index path) is absent at startup, the service should **refuse to start** with a clear error — not fail on the first request. This is a hard requirement, and it generalizes a pattern Stage 4 already introduced narrowly (Redis URL missing when a Redis backend was selected) — apply the same fail-fast philosophy comprehensively now: validate `Settings` at process startup (both `api/main.py`'s app creation and `cli.py`'s entry point) and raise immediately if anything required for the *selected* connectors/backends is missing.

---

## 8. What not to do in this stage

- **Do not implement retry logic inside `core/generation.py` or any other core module.** Retries belong at the connector layer so they're automatically inherited by future connectors — implementing them in `core/` means every future LLM connector has to remember to opt in, which defeats the point.
- **Do not retry non-transient errors.** An invalid API key or a malformed request should fail immediately and loudly, not retry three times and then fail slowly.
- **Do not leave any external call (LLM, vector store, object storage) without an explicit timeout.** "It'll probably respond eventually" is not a timeout strategy.
- **Do not change `QueryResponse`'s field names or drop any field** when moving to streaming — the metadata (sources, cached) must still reach the client, just via a different delivery mechanism (e.g., a trailing event) rather than disappearing.
- **Do not silently truncate retrieved context to fit a token budget without surfacing that this happened.** If a budget guard changes what's sent to the LLM, that's worth a log line at minimum (Stage 5's logging is already in place — use it) and ideally a flag in the response.
- **Do not let the service start successfully with a missing required API key or index path and then fail on the first real request.** That's a strictly worse experience than refusing to start, and it directly contradicts the fail-fast requirement.

---

## 9. Instructions to the implementing agent

1. Add `tenacity` as a dependency.
2. In `ragframework/llms/google_genai.py`, wrap the underlying chat model's invocation path (or configure LangChain's own retry parameters, if `ChatGoogleGenerativeAI` exposes them) with exponential backoff on transient errors specifically — enumerate which exception types/status codes count as transient in a code comment, and exclude authentication/validation errors explicitly.
3. Add `Settings.llm_timeout_seconds`, `Settings.vector_store_timeout_seconds`, and apply them at each respective connector's external call sites, including the Stage 7 worker's embedding/upsert calls.
4. Rewrite `ragframework/api/routers/query.py`'s handler to use `.stream()` and return a `StreamingResponse` emitting SSE events, with a final event carrying `sources` and `cached` after the token stream completes. Update the frontend-facing contract documentation (for Stage 10) to describe this event sequence precisely.
5. Add `Settings.max_tokens_per_request` and a budget-check step before the LLM call in the query path, logging (Stage 5) and failing clearly (not truncating silently) when it would be exceeded.
6. Add a startup validation routine — called from both `api/main.py`'s app creation and `cli.py`'s entry point — that checks every config value required by the *currently selected* `vector_store`/`llm_provider`/`cache_backend`/`memory_backend` and raises a clear, specific error (naming the missing variable) if anything required is absent. Do not validate config for connectors that aren't selected.
7. Manually verify: temporarily point the LLM config at an invalid API key and confirm the service refuses to start with a clear message naming the problem, rather than starting and failing on first query; simulate a transient failure (e.g., a mocked rate-limit response) and confirm retry-with-backoff occurs and eventually succeeds or fails clearly after exhausting retries; confirm a deliberately invalid API key does *not* get retried three times before failing; issue a query and confirm the client receives streamed tokens followed by a final metadata event; construct a query that would produce an oversized prompt and confirm the budget guard rejects it clearly rather than silently truncating.

---

## 10. Definition of done

- [ ] LLM calls retry with exponential backoff on transient errors only, not on auth/validation errors.
- [ ] Every external call (LLM, vector store, object storage) has an explicit, configurable timeout.
- [ ] `/v1/query` streams tokens via SSE, with a trailing event carrying `sources` and `cached`.
- [ ] A configurable token/context budget guard rejects oversized requests clearly, without silent truncation.
- [ ] The service refuses to start (with a specific, actionable error) if required config for the *selected* connectors/backends is missing — it never fails on the first request instead.
- [ ] Retry/timeout logic lives at the connector layer, not inside `core/`.

## 11. Handoff to Stage 9

Stage 9 adds OpenTelemetry tracing and metrics, instrumenting exactly the call boundaries this stage hardened — retries, timeouts, and the streaming path all become spans and metrics. It also completes the `/v1/health` and `/v1/ready` endpoints (stubbed since Stage 3) using the `health_check()` contract method and the fail-fast config validation this stage introduced.
