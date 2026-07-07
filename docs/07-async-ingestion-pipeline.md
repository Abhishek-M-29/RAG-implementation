# Stage 7 of 14 — Async Ingestion Pipeline

**Source roadmap section covered:** §12 (Backend architecture — async ingestion pipeline)
**Depends on:** Stage 6 — auth/rate limiting must already protect the ingestion router before it's restructured onto a queue.
**Followed by:** Stage 8 — Reliability (retries, timeouts, streaming).

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure, never operated as a hosted service by us.

**Connector scope for the whole build:** only **FAISS** and **Google Gemini** are implemented; every other backend is a documented extension point.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** the seven correctness fixes are already applied.

**What already exists when this stage starts:** `POST /v1/documents` (Stage 3) currently processes uploads synchronously, protected by `ingest`-scoped auth (Stage 6); a cache Layer 1 `index_fingerprint` counter exists (Stage 4) that the query cache invalidates against; structured logging with request IDs (Stage 5).

---

## 2. Why this stage exists

The current `run_indexing` behavior — even after Stage 3 wrapped it in an HTTP endpoint — is synchronous and blocking: one large PDF batch ties up the whole request/process. This stage decouples ingestion load from query latency by moving it onto a background job queue, so a large upload no longer blocks anyone asking questions.

---

## 3. Production shape of the pipeline

1. `POST /v1/documents` uploads the file to object storage (adopter-configured — **local disk by default** for the reference deployment, **S3 documented as the swap-in** for cloud deployments) and enqueues a job. It returns `{"job_id": ..., "status": "queued"}` immediately — this response shape already matches `DocumentUploadResponse` from Stage 3's schemas, so no schema change is needed, only a behavior change (the route no longer blocks until processing finishes).
2. A worker pool (**Celery or RQ**, backed by Redis) picks up the job: extract text → chunk → embed → upsert, via the configured vector store connector (`get_vector_store(settings)` from Stage 2 — the worker must go through the same registry as the API process, never construct a connector directly).
3. `GET /v1/documents/{job_id}` (already stubbed in Stage 3; made real here) reports status: `queued` → `processing` → `done` / `failed`. A webhook is documented as an adopter's alternative option, not built as a default.
4. On success, bump the `index_fingerprint` counter used by the Stage 4 query cache, so stale cached answers expire naturally — this call site already exists conceptually from Stage 4; this stage just moves it from "end of a synchronous request" to "end of a background job."

## 4. Object storage

Local disk is the default for the reference deployment (a configured directory, e.g., `Settings.object_storage_path: str = "uploads/"`), keeping the zero-external-dependencies promise intact for local/dev use. S3 (or S3-compatible storage) is documented as the production swap-in for cloud deployments, but is **not implemented as a second connector class in this stage** — treat it as a documented deployment note for Stage 13/14, not new abstraction work here. If you do add a pluggable storage interface, keep it minimal and don't let it become a third full connector abstraction layer on the scale of `BaseVectorStore`/`BaseLLMProvider` — that would be scope creep beyond what this roadmap calls for.

## 5. Worker pool

Celery or RQ, backed by Redis — this is the first place in the framework where Redis becomes load-bearing rather than optional (unlike the Stage 4 cache/memory backends, which work fine as `memory` with zero external dependencies, the async ingestion pipeline inherently needs *some* shared queue). Document this clearly: **running ingestion asynchronously requires Redis**; adopters who want a truly zero-dependency setup can still use the framework's synchronous ingestion path as a fallback (keep the Stage 3 synchronous code path available behind a settings flag, e.g., `Settings.async_ingestion: bool = True`, rather than deleting it outright) for local development or very low-volume deployments.

## 6. Job status reporting

`GET /v1/documents/{job_id}` must report one of exactly four states: `queued`, `processing`, `done`, `failed`. On `failed`, surface the per-file error captured by correctness fix #1 (already applied) so the caller knows *why* it failed, not just that it did. Do not collapse `failed` into a generic error with no detail — the whole point of fix #1 was to stop swallowing these errors, and this stage is where that detail finally reaches the API consumer.

---

## 7. What not to do in this stage

- **Do not make the worker construct a `FaissStore` or `GoogleGenAIProvider` directly.** It must call `get_vector_store(settings)` exactly like the API process does — two different processes constructing connectors two different ways is exactly the kind of drift the registry pattern exists to prevent.
- **Do not remove the synchronous ingestion code path entirely.** Keep it available (gated by a settings flag) so the framework still works with zero external dependencies for adopters who don't want to run Redis + a worker for light local use.
- **Do not build a second full connector abstraction for object storage.** Local disk default, S3 as a documented swap-in, kept minimal — this is explicitly flagged as a secondary concern relative to the vector-store/LLM connector abstractions.
- **Do not implement webhooks as the only status-reporting mechanism.** Polling via `GET /v1/documents/{job_id}` is the baseline that must work; webhooks are an adopter option, not a replacement.
- **Do not forget to bump `index_fingerprint`** on job success — if you do, Stage 4's query cache will keep serving stale answers indefinitely after a reindex, silently.
- **Do not let a failed job vanish without a status.** Every job must resolve to `done` or `failed`, never disappear or hang in `processing` forever without at least a timeout that transitions it to `failed`.
- **Do not bypass the `ingest`-scope auth check from Stage 6** when restructuring the route — re-verify it's still applied after the handler body changes.

---

## 8. Instructions to the implementing agent

1. Add Celery or RQ and a Redis client as dependencies (document the choice and why in a code comment — pick one, don't support both).
2. Add `Settings.object_storage_path: str = "uploads/"` and `Settings.async_ingestion: bool = True`.
3. Implement the upload handling in `ingestion.py`'s `POST /v1/documents`: save the file to `object_storage_path`, enqueue a job with the file path, return `DocumentUploadResponse(job_id=..., status="queued")` immediately.
4. Create the worker task (e.g., `ragframework/workers/ingestion_worker.py`): given a file path, run extract → chunk → embed → upsert using `core/ingestion.py`, `core/chunking.py`, and `get_vector_store(settings)`, updating job status in Redis (or the queue backend's result store) at each transition.
5. Implement `GET /v1/documents/{job_id}` to read real job status from the queue backend and return one of the four states, including error detail on `failed`.
6. On successful job completion, bump the `index_fingerprint` counter from Stage 4.
7. Keep the previous synchronous ingestion code path reachable when `Settings.async_ingestion=False`, so local/dev use without Redis still works.
8. Re-verify `ingest`-scope auth (Stage 6) still applies to the restructured route.
9. Update structured logging (Stage 5) to log job lifecycle transitions (`queued`→`processing`→`done`/`failed`) with the request ID that originated the upload, propagated into the worker context if feasible (note in a comment if full request-ID propagation into a separate worker process requires passing it explicitly through the job payload — do this rather than losing the correlation).
10. Manually verify: upload a large multi-file batch and confirm `POST /v1/documents` returns immediately with a `job_id`; poll `GET /v1/documents/{job_id}` and observe the status progress through `queued` → `processing` → `done`; confirm a query issued while ingestion is still processing is not blocked by it; deliberately upload a malformed/corrupt PDF and confirm the job resolves to `failed` with a specific error message rather than hanging or crashing the worker; confirm `async_ingestion=False` still works end-to-end without Redis running.

---

## 9. Definition of done

- [ ] `POST /v1/documents` returns immediately with `{"job_id", "status": "queued"}`, regardless of file size.
- [ ] A worker pool processes jobs independently of the API process, using `get_vector_store(settings)` for all vector store access.
- [ ] `GET /v1/documents/{job_id}` reports one of `queued`/`processing`/`done`/`failed`, with error detail on failure.
- [ ] `index_fingerprint` is bumped on job success, correctly invalidating the Stage 4 query cache.
- [ ] The synchronous ingestion path remains available via a settings flag for zero-Redis local use.
- [ ] `ingest`-scope auth (Stage 6) still protects the route.
- [ ] Query latency is unaffected by concurrent ingestion load (verified manually).

## 10. Handoff to Stage 8

Stage 8 adds retries, timeouts, and streaming at the connector layer — this applies to both the query path and the ingestion worker's calls to the vector store and LLM connectors. The worker built in this stage should have clear, isolated call sites for embedding and upserting so Stage 8's retry/timeout wrapping can be applied without restructuring the worker again.
