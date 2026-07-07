# Deployment Guide

This directory contains the container images and Docker Compose configuration for deploying the RAG Framework.

## Quickstart

```bash
# 1. Clone the repository
git clone <repo-url> && cd ragframework

# 2. Create environment config from the template
cp .env.example .env

# 3. Fill in your Gemini API key
#    Edit .env and set LLM_CONFIG__API_KEY=your-actual-key

# 4. Start everything
docker compose -f docker/docker-compose.yml up --build
```

That's it. The following services come up:

| Service | Access | Purpose |
|---|---|---|
| API | `http://localhost:8000` | FastAPI backend (RAG queries, document management) |
| Frontend | `http://localhost:3000` | Reference React UI |
| Redis | `localhost:6379` | Job queue + cache backend |
| Worker | (background) | Async document ingestion |

### Verifying the system

```bash
# Health check
curl http://localhost:8000/v1/ready

# Query the API
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?", "session_id": "test-1"}'

# Upload a document
curl -X POST http://localhost:8000/v1/documents \
  -F "file=@/path/to/document.pdf"

# Load the frontend
open http://localhost:3000
```

---

## Architecture

```
                  ┌─────────────┐
                  │  Frontend   │  Nginx serving static React build
                  │  :3000      │
                  └──────┬──────┘
                         │  HTTP /v1/*
                         ▼
                  ┌─────────────┐
           ┌─────►│   API       │  FastAPI (uvicorn)
           │      │  :8000      │
           │      └──────┬──────┘
           │             │
    ┌──────┴──────┐     │ RQ jobs
    │   Redis     │◄────┘         ┌─────────────┐
    │  :6379      │──────────────►│   Worker    │
    └─────────────┘  queue/       │  (async)    │
                      results     └─────────────┘
```

The API, worker, and frontend are separate containers and can be scaled independently:

```bash
docker compose -f docker/docker-compose.yml up --scale worker=3
```

---

## Environment Variables

All configuration is driven by `.env` (see `.env.example` at the repo root). Key variables:

| Variable | Default | Description |
|---|---|---|
| `LLM_CONFIG__API_KEY` | — | **Required.** Your Gemini API key |
| `LLM_CONFIG__MODEL` | `gemini-2.0-flash-lite` | Gemini model name |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `ASYNC_INGESTION` | `true` | Enable async ingestion via RQ worker |
| `CORS_ALLOWED_ORIGINS` | `["http://localhost:3000"]` | Allowed frontend origins |
| `VECTOR_STORE_CONFIG__INDEX_PATH` | `index_store/faiss_index` | FAISS index location |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |

See `ragframework/config.py` for the complete list of settings.

---

## Production Considerations

### Streaming needs longer idle timeouts

The `/v1/query` endpoint uses Server-Sent Events (SSE) to stream RAG responses token by token. SSE connections remain open for the duration of a query response — typically seconds to tens of seconds.

If you place a load balancer or reverse proxy in front of the API, **ensure idle timeout is set to at least 60 seconds** (preferably 120s). Most cloud load balancers default to 60s or less, which will terminate SSE mid-stream. This includes:

- AWS ALB/NLB idle timeout settings
- Nginx `proxy_read_timeout`
- Traefik/S3, HAProxy timeout configurations
- Kubernetes ingress controller timeouts

A prematurely terminated SSE connection causes partial answers with no error signal — a very confusing failure mode on first deployment.

### TLS is a reverse-proxy / deployment concern

The RAG Framework **does not terminate TLS** (HTTPS) by default. Running without TLS in front of the API is acceptable for local development but **unsupported for any deployment that transmits data over a network**.

Deployments should terminate TLS at one of:

- A reverse proxy (Nginx, Caddy, Traefik) in front of the API
- A cloud load balancer with TLS termination (ALB, NLB with TLS)
- A Kubernetes ingress with a TLS certificate

The framework serves plain HTTP on port `8000`, and this is by design — it lets the adopter choose their TLS termination strategy without the framework dictating one.

### Data persistence

Two Docker volumes persist data across restarts:

- **`faiss_index`** — The FAISS vector index file
- **`uploads`** — Uploaded PDFs before ingestion

### Resource requirements

- **API / Worker**: ~1 GB RAM (mostly from the embedding model loaded in memory)
- **Redis**: ~256 MB RAM for typical usage
- **Frontend**: Minimal (static files served by Nginx)

---

## Scaling

Since the API, worker, and frontend are separate images, they scale independently:

```bash
# More ingestion capacity
docker compose up --scale worker=5

# More query capacity (API is stateless)
docker compose up --scale api=3

# More frontend capacity
docker compose up --scale frontend=2
```

Note: When scaling the API, ensure your load balancer / reverse proxy handles distribution. The FAISS index is file-based and shared via a volume — for truly stateless horizontal scaling, swap FAISS for a networked vector database (pgvector, Qdrant, etc.) via the connector registry.

---

## Deploying to your own infrastructure

The Docker images produced here can be pointed at any container runtime:

- **ECS / Fargate** — Push images to ECR, define task definitions with the same env vars
- **Kubernetes** — Deploy as Deployments + Service + ConfigMap (no Helm charts needed — a simple `kubectl apply` is sufficient)
- **Single VM** — Pull images and run with `docker run` or a systemd unit

In every case the pattern is the same: configure via environment variables, provide a Redis instance, mount persistent volumes for the index and uploads, and put TLS termination in front.
