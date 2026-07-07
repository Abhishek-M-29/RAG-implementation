# Stage 13 of 14 — Deployment & CI/CD

**Source roadmap section covered:** §18 (Deployment & CI/CD)
**Depends on:** Stage 12 — the full test suite must exist so CI has something real to gate on.
**Followed by:** Stage 14 — Documentation, Versioning & Distribution.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure. **This principle is the entire reason this stage's scope is bounded the way it is: we build the deployment artifacts, the adopter runs them.**

**Connector scope for the whole build:** only **FAISS** and **Google Gemini** are implemented; every other backend is a documented extension point.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** the seven correctness fixes are already applied.

**What already exists when this stage starts:** a complete, tested backend (Stages 1–9, 11), frontend (Stage 10), and test suite (Stage 12); `docker/` exists with empty stub Dockerfiles from Stage 1's restructure.

---

## 2. Why this stage exists

Everything built so far runs on a developer's machine via `uvicorn`/`vite dev`. This stage produces the artifacts an adopter actually deploys: container images per service, a local reference `docker-compose.yml`, and a CI pipeline that gates image builds on the Stage 12 test suite passing. **Nothing about production deployment beyond providing these artifacts and documenting how to use them is in scope** — automating the adopter's actual cloud deployment is explicitly excluded by the guiding principles.

## 3. Docker images — one per service, scaled independently

Separate images for:

- **API** (`docker/Dockerfile.api`) — the FastAPI app from Stage 3 onward.
- **Ingestion worker** (`docker/Dockerfile.worker`) — the Celery/RQ worker from Stage 7.
- **Frontend** (`docker/Dockerfile.frontend`) — the static build from Stage 10.

They scale independently because query traffic, ingestion queue depth, and static asset serving have entirely different load profiles — an adopter under heavy query load doesn't need more ingestion workers, and vice versa. Do not combine these into a single image "for simplicity" — that would remove the adopter's ability to scale them independently, which is the entire reason they're separated.

## 4. docker-compose reference deployment

`docker/docker-compose.yml` wires up: API + worker + frontend + Redis (used for cache/queue, per Stages 4 and 7) + a volume for the local FAISS index. `docker compose up` with a filled-in `.env` (per Stage 2's example configs) should be a **complete local reference deployment** — someone cloning the repo, filling in their Gemini API key, and running `docker compose up` should get a fully working system with zero other setup.

Explicitly verify the compose file honors every settings flag introduced across the build: `async_ingestion` (Stage 7, so the worker and Redis are actually exercised by default), `cors_allowed_origins` (Stage 11, pointed at wherever the compose-launched frontend actually serves from), and the connector `.env` values from Stage 2.

## 5. CI pipeline (GitHub Actions)

Pipeline stages, in order, each gating the next:

1. **Lint**
2. **Type-check**
3. **Contract + unit + integration tests** (the full Stage 12 suite)
4. **Build images** (the three Dockerfiles from Section 3)
5. **(Optionally) push to a registry**

If any stage fails, the pipeline stops — do not build and push images from a commit that failed tests. If Stage 12 determined that some tests require a real Gemini test API key, wire that key in as a CI secret now, scoped as narrowly as the CI platform allows, and never printed to CI logs (the same redaction discipline from Stage 5 applies to CI output, not just application logs).

## 6. Adopter-side deployment is documented, not automated

Point the same Docker images at the adopter's own infrastructure — ECS/Fargate, Kubernetes, a single VM, whatever they run — with their own `.env`. This is written as a **guide** (finalized in Stage 14's documentation pass), not automated by the framework. Do not build Terraform modules, Helm charts, or cloud-specific deployment scripts as part of this stage — that would mean picking a cloud provider on the adopter's behalf, which directly contradicts "bring your own infrastructure."

Carry forward two deployment notes flagged in earlier stages so they land in the right place here:

- **Streaming needs longer idle timeouts.** Flagged in Stage 3/8 — if the adopter puts a load balancer in front with sticky-session or idle-timeout settings, the SSE-streamed `/v1/query` responses need longer idle timeouts than typical REST calls. Call this out explicitly in the deployment guide as a common first-deployment gotcha.
- **TLS is a reverse-proxy/deployment concern.** Flagged in Stage 3/11 — the framework doesn't terminate TLS itself; the deployment guide must be explicit that running without TLS in front of the API is unsupported beyond local development.

---

## 7. What not to do in this stage

- **Do not combine the API, worker, and frontend into a single Docker image.** They must scale independently.
- **Do not build cloud-provider-specific infrastructure-as-code** (Terraform, CloudFormation, Helm charts targeting a specific managed Kubernetes). Document the deployment pattern generically; let the adopter translate it to their own infrastructure.
- **Do not let CI push images built from a commit where any test stage failed.**
- **Do not print CI secrets (e.g., a Gemini test key) to build logs.** Use the CI platform's secret-masking mechanisms.
- **Do not make `docker compose up` require anything beyond filling in `.env`.** No manual database migration step, no separate manual Redis setup — compose should bring up everything needed, including Redis, from a single command.
- **Do not silently drop the streaming-idle-timeout and TLS-is-external notes.** They must appear explicitly in the deployment guide, not just live as tribal knowledge in this stage document.

---

## 8. Instructions to the implementing agent

1. Write `docker/Dockerfile.api` building the FastAPI app with all dependencies from Stages 1–11.
2. Write `docker/Dockerfile.worker` building the Celery/RQ worker from Stage 7, sharing the core `ragframework` package but with a distinct entrypoint.
3. Write `docker/Dockerfile.frontend` running `vite build` and serving the static output via Nginx, with the backend API base URL injected as a build-time or runtime variable (per Stage 10, Section 8).
4. Write `docker/docker-compose.yml` wiring API + worker + frontend + Redis + a FAISS index volume, reading configuration from a `.env` file at the compose file's location, using the example `.env` structure from Stage 2 as the template for a new top-level `.env.example`.
5. Write the GitHub Actions workflow (e.g., `.github/workflows/ci.yml`) implementing the five-stage pipeline from Section 5, wiring any required test secrets (per Stage 12's decision on real vs. mocked Gemini calls) via the CI platform's secret store.
6. Write the initial draft of the adopter-side deployment guide content (final polish and placement happens in Stage 14), explicitly including the streaming-idle-timeout and TLS-is-external notes from Section 6.
7. Manually verify: clone the repo fresh, fill in only `.env` with a real Gemini API key, run `docker compose up`, and confirm a full working system comes up with zero additional manual steps — query the API, upload a document, watch it get indexed, and load the frontend, all through the compose-launched services; deliberately break a test and confirm the CI pipeline stops before the image-build stage; confirm no secret value appears in CI logs.

---

## 9. Definition of done

- [ ] Three separate Dockerfiles exist (API, worker, frontend), each buildable independently.
- [ ] `docker-compose.yml` brings up a complete working system (API, worker, frontend, Redis, FAISS volume) from a single `docker compose up` plus a filled-in `.env`.
- [ ] The CI pipeline runs lint → type-check → the full Stage 12 test suite → image builds, in that order, stopping on any failure.
- [ ] No test secret (e.g., a Gemini test key) is ever printed to CI logs.
- [ ] The deployment guide draft explicitly documents the streaming-idle-timeout and TLS-is-external-to-the-framework notes.
- [ ] No cloud-provider-specific infrastructure-as-code exists in the repository.

## 10. Handoff to Stage 14

Stage 14 finalizes all documentation, including the deployment guide drafted here, into the README and per-connector setup guide, and handles packaging/versioning/publishing. It needs the `.env.example` and compose file from this stage as the basis for the quickstart instructions.
