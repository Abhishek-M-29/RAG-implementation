# Stage 3 of 14 — Backend API: Routing & Schemas

**Source roadmap section covered:** §8 (Backend architecture — routing)
**Depends on:** Stage 2 — `get_vector_store(settings)` and `get_llm(settings)` must be fully functional.
**Followed by:** Stage 4 — Caching & Memory Layer.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure, never operated as a hosted service by us.

**Connector scope for the whole build:** only **FAISS** (vector store) and **Google Gemini** (LLM) are implemented. Every other backend is a documented extension point.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** the seven correctness fixes are already applied — most relevantly for this stage, `session_id` is always caller-supplied, never a hardcoded global.

**What already exists when this stage starts:** `ragframework/config.py` defines `Settings`; `ragframework/vectorstores/registry.py` and `ragframework/llms/registry.py` expose `get_vector_store(settings)` and `get_llm(settings)`; `ragframework/core/generation.py` builds an LCEL chain from a `BaseChatModel`.

---

## 2. Why this stage exists

Every prior stage built logic with no way to reach it over the network. This stage stands up the actual HTTP surface: a FastAPI app, versioned routers, and typed request/response schemas. **Scope discipline matters here** — this stage produces working `/v1/query` and `/v1/documents` endpoints that call the connectors *synchronously and directly*, with no caching, no auth, no job queue, and no retries. Those are not omissions; they are Stages 4, 6, 7, and 8, layered on top of this same routing skeleton without changing its shape. Building them prematurely here means redoing this stage's work when those stages arrive.

---

## 3. Framework and versioning

- **Framework:** FastAPI. It's async-native, pairs naturally with LangChain's async methods, and generates OpenAPI docs for free — all useful properties for a framework other developers will integrate against.
- **Versioning:** all routes live under `/v1/...` from day one. A future breaking change gets its own `/v2/...` rather than breaking existing adopters mid-flight. Do not ship any unversioned route, including health checks — put those under `/v1/` too, per the endpoint table below.

## 4. Router separation

Each router owns its own auth scope and its own rate-limit policy (both wired in Stage 6 — for now, routers simply exist with no auth dependency attached):

| Router | Routes | Scope |
|---|---|---|
| `query.py` | `POST /v1/query` | read-only |
| `ingestion.py` | `POST /v1/documents`, `DELETE /v1/documents/{id}`, `GET /v1/documents` | write / admin |
| `health.py` | `GET /v1/health`, `GET /v1/ready` | unauthenticated |

Full endpoint reference (some of these return placeholder/synchronous behavior until later stages complete them — see the notes column):

| Method | Path | Purpose | Auth scope | Status in this stage |
|---|---|---|---|---|
| `POST` | `/v1/query` | Ask a question, streamed answer | query | Implemented synchronously; streaming arrives in Stage 8 |
| `POST` | `/v1/documents` | Upload and enqueue a document for indexing | ingest | Implemented synchronously; real queueing arrives in Stage 7 |
| `GET` | `/v1/documents` | List indexed documents | ingest | Implemented |
| `GET` | `/v1/documents/{job_id}` | Ingestion job status | ingest | Stubbed; meaningful once Stage 7's job queue exists |
| `DELETE` | `/v1/documents/{id}` | Remove a document and its chunks | ingest | Implemented, calls `BaseVectorStore.delete()` |
| `GET` | `/v1/health` | Liveness | none | Stubbed here; completed in Stage 9 |
| `GET` | `/v1/ready` | Readiness — checks connector health | none | Stubbed here; completed in Stage 9 |

Create the router files now with real route signatures and schemas, even where the body is a simplified synchronous version that later stages will extend. Do not leave routes undefined — every route in the table must exist and be reachable in this stage's build.

## 5. Request/response schemas

Create `ragframework/api/schemas.py`. **Never accept or return raw dicts** from a route handler — every request body and response body is a typed Pydantic model:

```python
class QueryRequest(BaseModel):
    query: str
    session_id: str
    top_k: int | None = None

class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    cached: bool

class DocumentUploadResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
```

`QueryRequest.session_id` is required and caller-supplied — this is correctness fix #2 made permanent at the API boundary. There is no default and no server-generated fallback; if the caller doesn't supply one, the request is invalid (return a 422, which FastAPI does automatically for a missing required field).

`QueryResponse.cached` exists now even though caching isn't implemented until Stage 4 — set it to `False` unconditionally in this stage's handler. This avoids a breaking schema change later; Stage 4 only needs to start setting the field correctly, not add it.

Define `SourceChunk` here as well (chunk text snippet, source filename, page number) — it's referenced by the frontend's sources panel in Stage 10, so get its shape right now rather than iterating on it later.

## 6. Reverse proxy and TLS

TLS termination and forwarding to the FastAPI app are handled by a reverse proxy in front of it — Nginx, Traefik, or a cloud load balancer, adopter's choice. This is a **deployment concern** (documented fully in Stage 13), not something baked into the framework itself. The framework must not assume any particular proxy is present, and must not attempt to terminate TLS itself.

## 7. Streaming-aware routing

The query endpoint is *designed* in this stage to return a streamed response (`StreamingResponse` / Server-Sent Events) — the route signature and response-type declaration should reflect this now, even though the actual token-by-token streaming implementation is Stage 8's job (built at the connector layer via `.stream()`). For this stage, it is acceptable for the handler to internally call `.invoke()` and return the full answer as a single SSE event or a plain JSON body — but do not design the route in a way that would require a breaking signature change when Stage 8 adds real streaming.

Document now, for the deployment guide that Stage 13 will write: if the adopter puts a load balancer in front with sticky-session or idle-timeout settings, streamed responses need longer idle timeouts than typical REST calls. This is a common first-deployment gotcha.

## 8. Internal dispatch vs. HTTP routing

Be explicit in code comments and in any developer-facing docs about the distinction between two different things both called "routing" in this system:

- **HTTP routing** — the FastAPI routers built in this stage, matching a URL path to a handler function.
- **Connector routing** — the `get_vector_store()` / `get_llm()` factory calls from Stage 2, which dispatch each request's config to the right connector implementation.

They are unrelated mechanisms that happen to share a name. A route handler performs HTTP routing by virtue of FastAPI decorators, then performs connector routing by calling `get_vector_store(settings)` inside its body.

---

## 9. What not to do in this stage

- **Do not implement caching, auth, a job queue, or retries in this stage.** Every route handler in this stage calls the connectors directly and synchronously. Adding any of those concerns now means Stage 4/6/7/8 have to unwind and rebuild your work instead of layering onto it.
- **Do not accept or return a raw `dict` anywhere in a route signature.** Every request and response body is a Pydantic model from `schemas.py`.
- **Do not default or fabricate `session_id` server-side.** It is a required field the caller must supply.
- **Do not put TLS termination, CORS configuration for a specific frontend, or reverse-proxy logic inside the FastAPI app.** CORS *allowlisting a specific origin* is real application config and does belong here structurally, but the actual origins are adopter-supplied via settings, not hardcoded — and full CORS/security hardening is Stage 11's job, not this one. For this stage, it's enough that the app doesn't default to `*` if you choose to stub CORS middleware in.
- **Do not build `/v1/health` or `/v1/ready` with real connector health logic yet.** Stub them (e.g., `/v1/health` returns `{"status": "ok"}` unconditionally) — Stage 9 owns making `/v1/ready` actually call `health_check()`.
- **Do not skip creating a route from the endpoint table** even if its real behavior is deferred to a later stage. An agent picking up Stage 4 or Stage 7 should find every route already present and extend it, not create it from scratch.

---

## 10. Instructions to the implementing agent

1. Create `ragframework/api/main.py` — the FastAPI app assembly, mounting all three routers under `/v1`.
2. Create `ragframework/api/schemas.py` with `QueryRequest`, `QueryResponse`, `SourceChunk`, `DocumentUploadResponse`, and any other response models needed for `GET /v1/documents`, `GET /v1/documents/{job_id}`.
3. Create `ragframework/api/routers/query.py` implementing `POST /v1/query`: parse `QueryRequest`, call `core/retrieval.py` against `get_vector_store(settings)`, call `core/generation.py` against `get_llm(settings)`, return a `QueryResponse` with `cached=False`.
4. Create `ragframework/api/routers/ingestion.py` implementing `POST /v1/documents` (accept upload, run ingestion synchronously for now, return `DocumentUploadResponse`), `GET /v1/documents` (list from the vector store's known documents — implement whatever minimal listing the FAISS connector can support), `GET /v1/documents/{job_id}` (stub — acceptable to return a fixed "done" status in this stage since there's no real job concept yet), `DELETE /v1/documents/{id}` (call `BaseVectorStore.delete()`).
5. Create `ragframework/api/routers/health.py` implementing `GET /v1/health` (always `{"status": "ok"}`) and `GET /v1/ready` (stub — acceptable to always return ready in this stage).
6. Create `ragframework/api/deps.py` as an empty-but-present module — Stage 6 will add auth/rate-limit dependencies here; create it now so imports referencing it elsewhere don't need to change later.
7. Wire `ragframework/cli.py`'s `serve` subcommand to launch the FastAPI app (e.g., via `uvicorn`).
8. Manually verify: start the server, `POST /v1/query` with a valid `session_id` and a query against a small pre-indexed FAISS store, confirm a `QueryResponse` comes back; `POST /v1/documents` with a sample PDF, confirm it's retrievable afterward via a query; `DELETE /v1/documents/{id}` and confirm a subsequent query no longer surfaces that content; hit `/v1/health` and `/v1/ready` and confirm both return 200.

---

## 11. Definition of done

- [ ] All seven routes from the endpoint table in Section 4 exist and are reachable under `/v1/`.
- [ ] `schemas.py` defines typed models for every request and response body — no raw dicts in any route signature.
- [ ] `QueryRequest.session_id` is required with no server-side default.
- [ ] Query and ingestion routes call `get_vector_store(settings)` / `get_llm(settings)` — never a concrete connector class directly.
- [ ] No caching, auth, job-queue, or retry logic exists yet anywhere in the API layer.
- [ ] Manual end-to-end query and ingestion round trips succeed against the FAISS + Gemini connectors.
- [ ] `/v1/health` and `/v1/ready` exist (stubbed) and return 200.

## 12. Handoff to Stage 4

Stage 4 adds the query/answer cache, embedding cache, and warm-model cache in front of and around these same route handlers — `query.py`'s handler will gain a cache-check before calling retrieval, and `QueryResponse.cached` will start reflecting real cache hits instead of a hardcoded `False`. Stage 4 also introduces the session-memory abstraction that `session_id` on `QueryRequest` will be used to key into.
