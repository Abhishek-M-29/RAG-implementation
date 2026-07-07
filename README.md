<div align="center">

# RAG Framework

**Bring-your-own-vector-store, bring-your-own-LLM — RAG orchestration you deploy yourself.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-0E7C86?style=flat-square)](https://www.langchain.com)
[![FAISS](https://img.shields.io/badge/FAISS-Vector%20Store-2B6CB0?style=flat-square)](https://github.com/facebookresearch/faiss)
[![Gemini](https://img.shields.io/badge/Gemini-LLM-4285F4?style=flat-square&logo=google)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[Quickstart](#quickstart) • [Configuration](#configuration) • [API](#api) • [Docker](#docker) • [Connectors](#adding-a-connector) • [Contributing](CONTRIBUTING.md)

</div>

RAG Framework is a **distributable RAG orchestration framework** you run on your own infrastructure — never a hosted service. It supplies:

- Pluggable contracts for vector stores and LLM providers
- Two shipped connectors: **FAISS** (local on-disk) + **Google Gemini**
- A FastAPI backend with query (SSE streaming), document ingestion, health probes
- Configurable caching, session memory, auth, rate limiting
- Async ingestion pipeline (RQ + Redis)
- OpenTelemetry observability (metrics, tracing, structured logging)
- A reference React frontend
- Containerized deployment (Docker + docker-compose)

## Quickstart

Three steps to a running instance:

```bash
pip install ragframework
```

Copy and fill in your configuration:

```bash
# Create .env from the template
cp .env.example .env
# Edit .env — set at minimum LLM_CONFIG__API_KEY=your-gemini-key
```

Start the server:

```bash
ragframework serve
```

The API is now running at `http://localhost:8000`. Try it:

```bash
curl http://localhost:8000/v1/health
```

> **No Docker? No problem.** The pip path runs everything locally with the
> in-memory cache and synchronous ingestion. If you need Redis-backed caching,
> session memory, or async ingestion, see the [Docker](#docker) section.

## Configuration

All configuration is via environment variables or a `.env` file in the working
directory. The `Settings` model is defined in `ragframework/config.py`.

### Connector selection

| Variable | Default | Description |
|---|---|---|
| `VECTOR_STORE` | `faiss` | Vector store backend (`faiss` only in this release) |
| `VECTOR_STORE_CONFIG__INDEX_PATH` | `index_store/faiss_index` | FAISS index on-disk path |
| `VECTOR_STORE_CONFIG__MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model for FAISS |
| `VECTOR_STORE_TIMEOUT_SECONDS` | `30.0` | Timeout for vector store operations |
| `LLM_PROVIDER` | `google_genai` | LLM provider (`google_genai` only in this release) |
| `LLM_CONFIG__API_KEY` | — | **Required.** Your Google Gemini API key |
| `LLM_CONFIG__MODEL` | `gemini-3.1-flash-lite` | Gemini model name |
| `LLM_CONFIG__TIMEOUT` | — | Per-provider timeout override (overrides `LLM_TIMEOUT_SECONDS`) |
| `LLM_TIMEOUT_SECONDS` | `30.0` | Timeout for LLM calls |

### Chunking & retrieval

| Variable | Default | Description |
|---|---|---|
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `100` | Overlap between chunks |
| `TOP_K` | `5` | Documents retrieved per query |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model for vector search |

### Caching & memory

| Variable | Default | Description |
|---|---|---|
| `CACHE_BACKEND` | `memory` | Query cache backend (`memory` or `redis`) |
| `QUERY_CACHE_TTL` | `3600` | Query cache TTL in seconds |
| `MEMORY_BACKEND` | `memory` | Session memory backend (`memory` or `redis`) |
| `REDIS_URL` | — | Redis connection URL (required when using `redis` backends or async ingestion) |

### Auth & rate limiting

| Variable | Default | Description |
|---|---|---|
| `AUTH_ENABLED` | `false` | Enable API-key authentication |
| `API_KEYS` | `{}` | JSON dict mapping API keys to scope lists: `{"sk-abc":["query"],"sk-xyz":["ingest"]}` |
| `QUERY_RATE_LIMIT` | `60/minute` | Rate limit for query endpoint |
| `INGESTION_RATE_LIMIT` | `10/minute` | Rate limit for ingestion endpoint |

### Ingestion

| Variable | Default | Description |
|---|---|---|
| `ASYNC_INGESTION` | `false` | Enable async ingestion via RQ (requires Redis) |
| `OBJECT_STORAGE_PATH` | `uploads/` | Directory for uploaded files |
| `OBJECT_STORAGE_TIMEOUT_SECONDS` | `30.0` | Timeout for file operations |
| `MAX_UPLOAD_SIZE_BYTES` | `50000000` | Maximum upload file size (50 MB) |

### Observability

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_RAW_QUERIES` | `false` | Log full query text |
| `OTEL_EXPORTER_ENDPOINT` | — | OpenTelemetry OTLP gRPC endpoint (optional) |
| `RAG_TRACING_PROVIDER` | `none` | LangChain tracing provider (`none`, `langsmith`, `langfuse`) |

### CORS

| Variable | Default | Description |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | `[]` | JSON list of allowed CORS origins, e.g. `["http://localhost:3000"]` |

### LLM generation

| Variable | Default | Description |
|---|---|---|
| `MAX_TOKENS_PER_REQUEST` | `4000` | Estimated token budget guard |

## API

All endpoints are served from `http://localhost:8000`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/health` | Liveness probe — always returns `{"status": "ok"}` |
| `GET` | `/v1/ready` | Readiness probe — tests vector store + LLM connectivity |
| `GET` | `/v1/config` | Returns active `vector_store`, `llm_provider`, `auth_enabled` |
| `POST` | `/v1/query` | RAG query — accepts `{"query": "...", "top_k": 5, "session_id": "..."}`, returns SSE stream |
| `POST` | `/v1/documents` | Upload a PDF for ingestion (multipart form) |
| `GET` | `/v1/documents` | List ingested documents |
| `GET` | `/v1/documents/{job_id}` | Poll async ingestion job status |
| `DELETE` | `/v1/documents/{id}` | Delete a document from the index |

### Query response format

The query endpoint streams [Server-Sent Events](https://html.spec.whatwg.org/multipage/server-sent-events.html):

```
data: {"type": "token", "content": "The answer begins..."}
data: {"type": "token", "content": " and continues."}
data: {"type": "metadata", "sources": [...], "cached": false}
```

## Docker

For the full stack (API + ingestion worker + Redis + frontend):

```bash
git clone https://github.com/Abhishek-M-29/RAG-implementation.git
cd RAG-implementation
cp .env.example .env
# Edit .env
docker compose -f docker/docker-compose.yml up
```

This starts:
- **Redis** — job queue + cache/memory backend
- **API** — FastAPI on `:8000`
- **Worker** — RQ ingestion worker
- **Frontend** — React SPA on `:3000`

## Per-connector guides

- [FAISS + Google Gemini](docs/connectors/faiss-gemini.md) — the shipped default

Each connector guide follows a reusable template so a future "pgvector + OpenAI"
page can slot in without restructuring the docs.

## Adding a connector

This framework ships with **FAISS** (vector store) and **Google Gemini** (LLM).
Adding a new backend requires writing exactly one class and registering it:

1. Implement `BaseVectorStore` or `BaseLLMProvider` in a new module
2. Register it in the corresponding registry (`vectorstores/registry.py` or `llms/registry.py`)
3. Add vendor dependencies as an extras group in `pyproject.toml`

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full walkthrough.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                       FastAPI (uvicorn)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  Query   │  │Ingestion │  │  Health  │  │    Config     │  │
│  │ (SSE)    │  │ (PDF)    │  │ /ready   │  │  introspection│  │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └───────────────┘  │
│       │              │                                          │
├───────┴──────────────┴──────────────────────────────────────────┤
│                      Core Layer                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  Cache   │  │  Memory  │  │  RAG     │  │  Token budget │  │
│  │ (mem/redis)│ (mem/redis)│  │  chain   │  │  guard        │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
├────────────────────────────────────────────────────────────────┤
│                 Connector Layer (pluggable)                     │
│  ┌─────────────────────┐  ┌──────────────────────────────┐     │
│  │  BaseVectorStore    │  │     BaseLLMProvider           │     │
│  │  ├─ FAISS (shipped) │  │     ├─ Google Gemini (shipped)│     │
│  │  └─ pgvector (next) │  │     └─ OpenAI (next)          │     │
│  └─────────────────────┘  └──────────────────────────────┘     │
├────────────────────────────────────────────────────────────────┤
│                    Infrastructure                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐     │
│  │  Redis   │  │  RQ      │  │  OpenTelemetry            │     │
│  │ (cache/  │  │ (async   │  │  (metrics/tracing/logs)   │     │
│  │  memory) │  │  ingest) │  │                           │     │
│  └──────────┘  └──────────┘  └──────────────────────────┘     │
└────────────────────────────────────────────────────────────────┘
```

### Stack

| Component | Technology |
|---|---|
| Framework | Python 3.10+, LangChain 0.3 |
| API server | FastAPI + uvicorn |
| Vector store | FAISS (shipped); extendable via `BaseVectorStore` |
| LLM | Google Gemini (shipped); extendable via `BaseLLMProvider` |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Cache | In-memory (`cachetools.TTLCache`) or Redis |
| Session memory | In-memory or Redis |
| Async jobs | RQ (Redis-backed) |
| Auth | API-key scopes (`query`, `ingest`) + `slowapi` rate limiting |
| Observability | OpenTelemetry (OTLP), structured JSON logging |
| Frontend | React 19, TypeScript, Vite 8, Tailwind 4 |
| Deployment | Docker multi-stage builds, docker-compose |
| CI | GitHub Actions (ruff, pyright, oxlint, tsc, pytest, Docker) |

## Development

```bash
# Clone and install with dev dependencies
git clone https://github.com/Abhishek-M-29/RAG-implementation.git
cd RAG-implementation
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check ragframework/

# Typecheck
pyright ragframework/
```

## License

MIT
