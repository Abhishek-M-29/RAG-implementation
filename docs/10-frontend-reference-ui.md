# Stage 10 of 14 — Frontend: Reference UI

**Source roadmap section covered:** §15 (Frontend, all subsections 15.1–15.7)
**Depends on:** Stage 9 — the full backend API surface (`/v1/query` streaming, `/v1/documents`, `/v1/ready`) must be complete, since the frontend consumes it as-is with no further backend changes.
**Followed by:** Stage 11 — Security Hardening.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure, never operated as a hosted service by us.

**Connector scope for the whole build:** only **FAISS** and **Google Gemini** are implemented; every other backend is a documented extension point. The frontend never displays or assumes anything beyond what the configured connectors report about themselves.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; **the framework is not a hosted service — this applies to the frontend just as much as the backend.** Like the backend, the reference frontend is something adopters run themselves, not a hosted product.

**Baseline assumption:** the seven correctness fixes are already applied to the backend this frontend talks to.

**What already exists when this stage starts:** a complete `/v1/query` (streaming via SSE, per Stage 8), `/v1/documents` (async job-queue-backed, per Stage 7), `/v1/documents/{job_id}` (real status, per Stage 7), `DELETE /v1/documents/{id}`, `/v1/health` and `/v1/ready` (per Stage 9), and optional API-key auth (per Stage 6).

---

## 2. Why this stage exists

Every prior stage built and hardened a backend with no consumer. This stage builds the reference web UI, in `frontend/` (already scaffolded as an empty directory in Stage 1), that talks to that backend API. It is scoped deliberately small: three pages, no server-side rendering, no framework beyond what's needed for an internal query/admin tool.

---

## 3. Tech stack

**React + TypeScript + Vite** for a fast dev loop and a simple static build output; **Tailwind** for styling. This is a deliberate SPA choice — there's no need for server-side rendering for an internal query/admin tool. If an adopter later wants public SEO-facing pages, that's a reason to swap in Next.js — note this as a future option in the frontend's own README, but do not build it now.

## 4. Pages and components

| Page | Purpose | Key components |
|---|---|---|
| **Chat / query** | Ask questions, see streamed answers with sources | Message list, input box, streaming answer renderer, expandable "sources" panel per answer (chunk snippet + source filename + page number) |
| **Document management** | Upload, monitor, and delete indexed documents | Upload dropzone (PDF), document table (name, indexed date, chunk count, status), delete action, job-status polling for in-progress uploads |
| **Settings / status** | Show current connector configuration and health | Read-only display of configured `vector_store` / `llm_provider` (never the raw API key — see Section 7), health indicator dots sourced from `/v1/ready` |

Build exactly these three pages. Do not add a fourth page (e.g., an analytics dashboard, a user-management page) in this stage — that's outside the scope this roadmap defines for the reference frontend, and the framework explicitly leaves dashboards to the adopter's own observability stack (Stage 9, Section 9).

## 5. API integration and streaming

- A thin API client module wraps all backend calls (`fetch`/`axios`), **one function per endpoint**, typed against the same request/response shapes as `ragframework/api/schemas.py`. Keep these types hand-synced with the backend schemas for now (no codegen pipeline needed at this scope) — but keep them in one file so drift is easy to spot and fix.
- Streamed answers are consumed via `EventSource` (Server-Sent Events) or a `fetch` + `ReadableStream` reader, rendering tokens as they arrive rather than waiting for the full response. This must match the exact event sequence Stage 8 defined: a stream of token events followed by a trailing event carrying `sources` and `cached`. Do not assume the full `QueryResponse` arrives as a single JSON payload — it doesn't, by design, since Stage 8.
- Standard retry/backoff on network failure for non-streaming calls (document list, delete, job-status polling); a **visible error state** (not a silent failure) when the backend is unreachable. A blank screen or an infinite spinner when the backend is down is a bug, not an acceptable degradation.

## 6. State management

React Context (or a lightweight store like Zustand if state grows) for: current chat session and history, the document list, and connector/health status. No need for Redux at this scope — the state surface is small and mostly server-derived. Do not introduce Redux or another heavier state library "for future scale" — that's speculative complexity this roadmap explicitly doesn't call for.

The chat session's `session_id` (required by `QueryRequest` since Stage 3) should be generated client-side once per chat session and held in this state layer — never hardcoded, never omitted.

## 7. Auth on the frontend

If `auth_enabled` is set on the backend (Stage 6), the frontend needs a place to hold the API key/session token for the duration of the session. Store it in memory (React state) or an `httpOnly` secure cookie set by a lightweight backend session endpoint — **not** `localStorage`/`sessionStorage`, which are readable by any injected script and are the standard XSS exfiltration target. The settings page (Section 4) only ever displays which connector is configured, never the key itself — this mirrors the backend's own redaction rule from Stage 5 (never log secrets) applied to the UI layer (never display secrets).

## 8. Frontend deployment

Static build (`vite build`) served via Nginx or a CDN (S3 + CloudFront if the adopter is on AWS), or as a third container in the same `docker-compose.yml` as the backend (`docker/Dockerfile.frontend`, scaffolded in Stage 1, filled in fully in Stage 13). The backend API base URL is a **build-time or runtime environment variable, not hardcoded** — an adopter deploying this frontend against their own backend instance must be able to point it at the right URL without a code change.

Backend CORS config must explicitly allow the frontend's origin — flag this now as a common first-run failure point, worth calling out explicitly in the quickstart docs that Stage 14 will write. (CORS configuration itself belongs to Stage 11's security hardening pass on the backend — this stage's job is to note the dependency, not to configure the backend.)

## 9. Frontend observability

Lighter touch than backend observability, and explicitly a secondary concern relative to Stage 9's backend observability story — call it out as such rather than over-building it: basic client-side error tracking (e.g., Sentry's browser SDK, optional/off by default) and standard web vitals if the adopter cares about perceived performance. Do not build a custom frontend telemetry pipeline; if error tracking is included, it should be a well-known, optional, off-by-default integration point, not framework-maintained infrastructure.

---

## 10. What not to do in this stage

- **Do not use `localStorage` or `sessionStorage` for any API key or session token.** Use in-memory React state or an `httpOnly` cookie set by the backend.
- **Do not build more than the three pages specified in Section 4.**
- **Do not introduce Next.js, Redux, or other heavier tooling** than what's specified — React + TypeScript + Vite + Tailwind + Context/Zustand is the full stack for this stage.
- **Do not hardcode the backend API base URL.** It must be a build-time or runtime environment variable.
- **Do not assume `/v1/query` returns a single JSON blob.** Consume the SSE token stream plus trailing metadata event exactly as Stage 8 defined it.
- **Do not display the raw API key anywhere in the UI**, including the settings page — only display which connector is configured.
- **Do not fail silently when the backend is unreachable.** Show a visible, clear error state.
- **Do not build a custom frontend analytics/telemetry pipeline.** If included at all, use an existing optional SDK, off by default.
- **Do not generate or hardcode `session_id` server-side or as a fixed constant** — it's generated client-side per chat session, same discipline the backend has enforced on it since Stage 3.

---

## 11. Instructions to the implementing agent

1. Scaffold the Vite + React + TypeScript project inside `frontend/` (already an empty directory from Stage 1), with Tailwind configured.
2. Build the API client module: one typed function per backend endpoint (`postQuery` with SSE handling, `uploadDocument`, `listDocuments`, `getDocumentStatus`, `deleteDocument`, `getReadyStatus`), reading the backend base URL from a build-time/runtime env variable.
3. Build the Chat/query page: message list, input box, an SSE consumer that renders tokens as they stream in, and an expandable sources panel populated from the trailing metadata event.
4. Build the Document management page: upload dropzone restricted to PDF, a table of indexed documents, a delete action wired to `DELETE /v1/documents/{id}`, and status polling against `GET /v1/documents/{job_id}` for in-progress uploads.
5. Build the Settings/status page: read-only display of `vector_store`/`llm_provider` (fetch from a lightweight status field the backend exposes — do not fetch or display raw config), and health indicator dots sourced from `/v1/ready`.
6. Implement state management via React Context (or Zustand) for chat session/history, document list, and connector/health status. Generate `session_id` client-side once per chat session.
7. Implement the auth token holder as in-memory React state (or wire an `httpOnly` cookie flow if the backend exposes one) — never `localStorage`/`sessionStorage`.
8. Add a visible error state component used consistently whenever any API call fails, including backend-unreachable scenarios.
9. Optionally wire an off-by-default Sentry browser SDK integration point and basic web vitals reporting, clearly documented as optional in the frontend's own README.
10. Manually verify: run the frontend against a locally running backend from Stage 9 with `auth_enabled=False`, confirm all three pages work end to end (ask a question and see it stream with sources, upload a PDF and watch its status progress to done, see health indicators reflect `/v1/ready`); repeat with `auth_enabled=True` and confirm the API key is held only in memory and never appears in browser storage (verify via devtools); disconnect the backend and confirm each page shows a clear error state rather than hanging or going blank.

---

## 12. Definition of done

- [ ] All three pages (Chat, Document management, Settings/status) exist and function against the live backend API.
- [ ] Streaming answers render token-by-token via SSE, with sources populated from the trailing metadata event.
- [ ] `session_id` is generated client-side per session and included on every query.
- [ ] No API key or session token is ever written to `localStorage`/`sessionStorage`.
- [ ] The backend base URL is configurable at build time or runtime, never hardcoded.
- [ ] Every page shows a visible error state on backend failure — no silent failures or infinite spinners.
- [ ] The settings page never displays a raw API key.
- [ ] No page beyond the three specified exists.

## 13. Handoff to Stage 11

Stage 11 hardens security across the whole system, including CORS configuration on the backend that this frontend's origin must be explicitly allow-listed under (flagged as a dependency in Section 8), and file-upload validation that the Document management page's upload flow will need to surface errors from cleanly.
