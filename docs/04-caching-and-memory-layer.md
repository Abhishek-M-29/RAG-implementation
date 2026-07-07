# Stage 4 of 14 — Caching & Memory Layer

**Source roadmap section covered:** §9 (Backend architecture — caching), plus the `memory/` package from §5 (Repository layout)
**Depends on:** Stage 3 — routers and schemas must exist, with `QueryResponse.cached` already present (hardcoded `False`) and `QueryRequest.session_id` already required.
**Followed by:** Stage 5 — Structured Logging & Correlation IDs.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure, never operated as a hosted service by us.

**Connector scope for the whole build:** only **FAISS** and **Google Gemini** are implemented; every other backend is a documented extension point.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** correctness fix #2 (per-session history, no shared global) and fix #4 (locked/lifespan-managed singletons instead of unlocked lazy globals) are already applied to the original POC. This stage is where fix #4 gets its permanent, production home — see Section 4 ("Layer 3").

**What already exists when this stage starts:** working `/v1/query` and `/v1/documents` routes (Stage 3) that call connectors synchronously; `QueryRequest.session_id` is a required field; `QueryResponse.cached` exists but is hardcoded `False`.

---

## 2. Why this stage exists

Two related but distinct concerns get built in this stage, both because the build-order checklist groups them together and both because they share the same "swappable backend behind a tiny interface" shape as everything else in this framework:

1. **Caching** — four independent layers that reduce latency and LLM cost.
2. **Session memory** — the per-session conversation history abstraction that replaces the POC's global `ChatMessageHistory`, made swappable (in-memory vs. Redis) the same way the cache is.

Both are behind the same small interface pattern so the backend (memory vs. Redis) is swappable without touching call sites.

---

## 3. The cache interface

Create `ragframework/cache/base.py`:

```python
# ragframework/cache/base.py
class BaseCache(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None: ...
    @abstractmethod
    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None: ...
    @abstractmethod
    def delete(self, key: str) -> None: ...
    @abstractmethod
    def clear(self) -> None: ...
```

- **Default:** `ragframework/cache/memory_cache.py` — a simple `cachetools.TTLCache`. Correct for a single-process deployment and for local development with zero external dependencies.
- **Optional:** `ragframework/cache/redis_cache.py` — same interface, for adopters running multiple backend instances that need a shared cache. Selected via `Settings.cache_backend` (already defined in Stage 2's `Settings` model) and `Settings.redis_url`.

## 4. The four cache layers

**Layer 1 — query/answer cache.** Cache key is a hash of `(normalized query text, top_k, index_fingerprint)`. `index_fingerprint` is a version counter bumped on every successful ingestion job — this means a re-index naturally invalidates stale cached answers without needing to actively purge anything. Default TTL: 1 hour, configurable via `Settings`. This is the layer that makes `QueryResponse.cached` meaningful — update the Stage 3 query handler to check this cache before calling retrieval/generation, and set `cached=True` on a hit.

**Layer 2 — embedding cache.** Cache key is a hash of `(chunk text, embedding model name)`. Prevents recomputing embeddings for unchanged content when a reindex/append runs after adding one new document — this directly addresses a real cost in the original `run_indexing` flow, which recomputed everything on every call. Wire this into `core/ingestion.py`'s chunk-embedding step.

**Layer 3 — connection/model warm cache.** Keep the embedding model, the vector store client, and the LLM client resident per worker process. **This is where correctness fix #4 gets its permanent implementation.** In the original POC this was an ad hoc global (`_embedding_model`, `_llm`) initialized lazily on first call; replace it with FastAPI's `lifespan` context manager so initialization happens once at process startup, under a proper async lock, not on the first incoming request. Update `ragframework/api/main.py` (from Stage 3) to use `lifespan` for this.

**Layer 4 — HTTP-level caching.** `Cache-Control` headers on static frontend assets (relevant once Stage 10 builds the frontend). Not applicable to the query/ingestion API responses themselves, since those are per-session and dynamic — do not add HTTP caching headers to `/v1/query` or `/v1/documents` responses.

**Invalidation summary:**

| Cache | Key includes | Invalidation |
|---|---|---|
| Query/answer | index fingerprint | Automatic — fingerprint changes on reindex |
| Embedding | model name | Manual — bump on embedding model upgrade |
| Warm models | — | Process restart only |

---

## 5. The session memory abstraction

The repository layout (Stage 1) reserved a `ragframework/memory/` package, parallel in shape to `cache/`, for conversation session history — this is what `QueryRequest.session_id` keys into. Build it now, in this stage, using the same interface-first pattern as everything else in the framework:

Create `ragframework/memory/base.py` with a contract shaped like:

- `get_history(session_id: str) -> list[...]` — return the conversation turns for a session.
- `append(session_id: str, message: ...) -> None` — add a turn to a session's history.
- `clear(session_id: str) -> None` — reset a session's history.

- **Default:** `ragframework/memory/in_memory.py` — wraps a per-session `ChatMessageHistory` object keyed by `session_id` in a dict. This is the direct, permanent fix for correctness bug #2: instead of one global `ChatMessageHistory()` shared by every caller under a hardcoded `"cli_session"` ID, every distinct `session_id` gets its own isolated history object, created on first use.
- **Optional:** `ragframework/memory/redis_memory.py` — same interface, persists sessions across process restarts and across multiple backend instances. Selected via `Settings.memory_backend` and `Settings.redis_url` (already defined in Stage 2).

Wire the Stage 3 query handler to fetch the session's history via this abstraction before building the generation prompt, and append the new turn after generation completes.

---

## 6. Configuration touched in this stage

`Settings.cache_backend`, `Settings.memory_backend`, and `Settings.redis_url` were already declared in Stage 2's `Settings` model — this stage is the first to actually branch on them.

| Variable | Default | Description |
|---|---|---|
| `CACHE_BACKEND` | `memory` | `memory` or `redis` |
| `MEMORY_BACKEND` | `memory` | `memory` or `redis` |
| `REDIS_URL` | — | Required if either backend above is `redis` |

If `CACHE_BACKEND=redis` or `MEMORY_BACKEND=redis` but `REDIS_URL` is unset, fail fast at startup with a clear error (this pattern is formalized further in Stage 8, but don't wait until then to apply it here — a missing Redis URL should never surface as a confusing runtime error on the first cache write).

---

## 7. What not to do in this stage

- **Do not build a single combined cache/memory class.** They are conceptually distinct (one is a performance optimization with TTLs and fingerprint-based invalidation, the other is stateful conversation history that must never silently expire mid-conversation) and must remain two separate packages with two separate interfaces, even though they're built in the same stage.
- **Do not put TTL-based expiry on session memory.** A cache entry expiring is fine; a mid-conversation history silently vanishing is a functional bug, not a performance tradeoff. If session cleanup is needed, it should be an explicit `clear()` call, not a TTL.
- **Do not make Redis a hard dependency.** `memory_cache.py` and `in_memory.py` must work with zero external services running — this is what keeps the framework's "zero external dependencies out of the box" promise intact.
- **Do not put the warm-model singleton initialization back on the first-request path.** That's precisely the bug fix #4 closed; moving it into FastAPI's `lifespan` is the whole point of Layer 3.
- **Do not cache raw query text as the visible cache key without hashing it**, especially if it will ever be logged (Stage 5 will log cache keys) — hash it, consistent with the query-privacy stance the logging stage takes.
- **Do not add HTTP `Cache-Control` headers to any `/v1/*` API response.** Those endpoints are dynamic and per-session; only static frontend assets (Stage 10/13) get HTTP-level caching.

---

## 8. Instructions to the implementing agent

1. Create `ragframework/cache/base.py` with `BaseCache` exactly as specified in Section 3.
2. Create `ragframework/cache/memory_cache.py` using `cachetools.TTLCache`.
3. Create `ragframework/cache/redis_cache.py` implementing the same interface against a Redis client, gated on `Settings.redis_url` being present.
4. Add a small factory (e.g., `get_cache(settings)`) analogous in spirit to the connector registries, dispatching on `Settings.cache_backend`.
5. Implement Layer 1 (query/answer cache): add an `index_fingerprint` counter (in-memory is fine for now; persistence considerations belong to whichever vector store connector needs it), bump it on successful ingestion, and use it plus normalized query text and `top_k` as the Layer 1 cache key. Update the Stage 3 query handler to check this cache first and set `QueryResponse.cached` accurately.
6. Implement Layer 2 (embedding cache) inside `core/ingestion.py`'s embedding step, keyed on `(chunk text, embedding model name)`.
7. Implement Layer 3 (warm cache): refactor `ragframework/api/main.py` to initialize the embedding model, vector store client, and LLM client once in a `lifespan` context manager, guarded by an async lock during startup.
8. Create `ragframework/memory/base.py`, `ragframework/memory/in_memory.py`, and `ragframework/memory/redis_memory.py` per Section 5, plus a `get_memory(settings)` factory.
9. Update the Stage 3 query handler to pull conversation history via `get_memory(settings).get_history(session_id)` before generation and `.append(...)` after.
10. Verify fail-fast behavior: set `CACHE_BACKEND=redis` with no `REDIS_URL` and confirm the app refuses to start (or fails clearly at first use, at minimum — full fail-fast-at-startup is formalized in Stage 8) rather than throwing an opaque error deep in a request handler.
11. Manually verify: repeat an identical query twice and confirm the second response has `cached: true` and near-zero added latency; run two different `session_id`s through multi-turn conversations and confirm their histories don't bleed into each other; re-run ingestion and confirm the query cache is invalidated (a previously-cached answer is recomputed).

---

## 9. Definition of done

- [ ] `BaseCache` and `BaseMemory`-equivalent interfaces exist, each with in-memory and Redis implementations.
- [ ] Layer 1 (query/answer), Layer 2 (embedding), and Layer 3 (warm models via `lifespan`) are all implemented and wired into the relevant call sites.
- [ ] `QueryResponse.cached` reflects real cache hits/misses.
- [ ] Session memory is isolated per `session_id` — no shared global history object remains anywhere in the codebase.
- [ ] The app runs with zero external services when both backends are `memory` (the default).
- [ ] Selecting `redis` for either backend without `REDIS_URL` fails clearly rather than silently.
- [ ] No TTL-based expiry exists on session memory.

## 10. Handoff to Stage 5

Stage 5 replaces every remaining `print()` with structured logging and adds request-ID propagation. It will log cache hit/miss events (as a hash, not raw query text) and ingestion timing that this stage's caches produce — make sure the cache-check and cache-write points built in this stage are easy to instrument (i.e., isolated, named functions/methods) rather than inlined in a way that makes adding a log line awkward.
