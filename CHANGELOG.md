# Changelog

## v1.0.0 (2026-07-07)

Initial public release of RAG Framework — a distributable, bring-your-own-backend
RAG orchestration framework with FAISS and Google Gemini as the shipped connectors.

### Features

- **Pluggable connector contracts** — `BaseVectorStore` and `BaseLLMProvider` ABCs
  with a registry pattern; adding a new connector means one class + one registration,
  no core changes.
- **Shipped connectors** — FAISS (local on-disk vector store) and Google Gemini
  (LLM with `langchain-google-genai`), with a retry wrapper for transient errors.
- **FastAPI backend** — Query endpoint with SSE streaming, document ingestion
  (PDF upload), health/readiness probes, and config introspection.
- **Query caching** — Configurable in-memory (`cachetools.TTLCache`) or Redis-backed
  cache keyed on normalized query + index fingerprint.
- **Session memory** — Configurable per-session chat history (in-memory or Redis).
- **API-key authentication** — Scoped access (`query`, `ingest`) with `slowapi`
  rate limiting.
- **Async ingestion pipeline** — RQ-backed, Redis-queued document processing with
  job status polling.
- **Reliability layer** — Exponential-backoff retry on transient API errors
  (tenacity), configurable timeouts, token-budget guard on query context.
- **Observability** — Structured JSON logging with correlation IDs, OpenTelemetry
  metrics (request counts, latency, cache hit/miss, token usage, queue depth),
  and distributed tracing.
- **Reference frontend** — React 19 / TypeScript / Vite 8 / Tailwind 4 SPA with
  chat UI and document upload.
- **Security hardening** — File-type validation (magic bytes + extension),
  upload size limits, CORS configuration, secret redaction in logs.
- **Containerized deployment** — Multi-stage Dockerfiles for API, worker, and
  frontend; `docker-compose.yml` with Redis, healthchecks, and shared volumes.
- **CI pipeline** — GitHub Actions: ruff lint, pyright typecheck, oxlint frontend
  lint, tsc typecheck, pytest (contract + unit + integration), Docker image build.
- **30+ tests** — Contract tests parametrized over the connector registries,
  integration tests for auth, CORS, upload, health, query flow, and async ingestion.

### Known limitations

- **FAISS `allow_dangerous_deserialization=True`** — FAISS uses pickle for
  index persistence; there is no safe-load path for indexes saved by a prior
  session. This is documented in the per-connector guide and is a property of
  the FAISS connector, not the framework. Networked vector stores (pgvector,
  Qdrant, etc.) do not share this risk.
- **FAISS `delete()` is O(n)** — deleting a document rebuilds the entire index
  from remaining documents. This is a known FAISS tradeoff; a networked vector
  store is recommended for deployments that need efficient deletion.
- **Only two connectors shipped** — FAISS (vector store) and Google Gemini (LLM).
  Adding pgvector, Qdrant, Pinecone, OpenAI, Anthropic, etc. follows the
  documented extension process in `CONTRIBUTING.md`.
