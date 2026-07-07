# Stage 6 of 14 — Authorization & Rate Limiting

**Source roadmap section covered:** §11 (Backend architecture — authorization & rate limiting)
**Depends on:** Stage 5 — structured logging must exist, since auth failures and rate-limit rejections need to log correctly and safely.
**Followed by:** Stage 7 — Async Ingestion Pipeline.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure, never operated as a hosted service by us.

**Connector scope for the whole build:** only **FAISS** and **Google Gemini** are implemented; every other backend is a documented extension point.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** the seven correctness fixes are already applied.

**What already exists when this stage starts:** working routers (Stage 3) with an empty `ragframework/api/deps.py` placeholder created specifically for this stage; structured logging with request-ID propagation (Stage 5), which this stage's auth/rate-limit failures will log through.

---

## 2. Why this stage exists

A framework meant to be embedded inside an adopter's own already-authenticated app should not force an auth scheme on them. This stage builds auth and rate limiting as **optional, off-by-default** features — real, working, and easy to turn on, but never imposed on an adopter who's handling authentication upstream (e.g., behind their own gateway).

---

## 3. Authorization

- **Off by default.** `Settings.auth_enabled: bool = False` (already declared in Stage 2's `Settings` model). When `False`, no auth dependency should run at all — not a no-op check that always passes, but genuinely skipped, so there's zero added latency or complexity for adopters who don't want it.
- **When enabled:** a simple API-key check implemented as a FastAPI dependency in `ragframework/api/deps.py`, checked against `Settings.api_keys` (already declared in Stage 2, typed as `list[SecretStr]`).
- **Two scopes minimum:**
  - **query** — can call `POST /v1/query`
  - **ingest** — can call the ingestion router (upload/list/delete)
  A query-scoped key must be **rejected**, not merely "technically working," on ingestion routes. This means the scope needs to be tracked per key (e.g., a mapping of key → scope(s) in config), not just a single flat list of valid keys — extend `Settings.api_keys` design if needed to carry scope information (for example, a dict of `{key: [scopes]}` rather than a bare list, while keeping backward-compatible defaults). Document this shape change clearly since it affects the `.env` format for anyone enabling auth.
- Apply the appropriate scope dependency to each router from Stage 3: `query.py`'s route requires `query` scope, `ingestion.py`'s routes require `ingest` scope, `health.py`'s routes require no auth at all (per the endpoint table established in Stage 3).

## 4. Rate limiting

- Implemented via `slowapi` (Starlette/FastAPI-native).
- **Keyed by API key when auth is enabled, by IP otherwise.** Do not key by IP when auth is enabled even as a fallback — a shared corporate IP behind auth should be rate-limited per-key, not lumped together.
- **Purpose:** two reasons, both explicit — protecting the adopter's own LLM bill from abuse, and basic DoS resistance. The framework does **not** manage billing itself; it exists purely to prevent one runaway client from generating unbounded LLM spend or request volume against the adopter's own infrastructure.
- Apply rate limits per-router, since query and ingestion have very different cost/abuse profiles (a query hits the LLM per-request; an ingestion upload is comparatively rarer but heavier) — don't use one blanket limit for both.

## 5. Multi-tenancy (documented pattern, not a default)

If an adopter wants to serve multiple isolated tenants from one deployment, the documented pattern is: add a `tenant_id` to every request and enforce it as a mandatory metadata filter at the vector store connector level. **This is documented, not built, in this stage.** Most adopters running "their own" instance won't need it, and building it as a hidden default would silently complicate every connector's `similarity_search()` for a feature most deployments never use. Write this pattern up as a short doc/comment for adopters who need it, pointing at where in `BaseVectorStore.similarity_search()` a metadata filter would need to be threaded through — but do not implement tenant filtering in the FAISS connector itself.

---

## 6. Configuration touched in this stage

| Variable | Default | Description |
|---|---|---|
| `AUTH_ENABLED` | `false` | Enable API-key auth |
| `API_KEYS` | `[]` | Accepted keys (extend format to carry scope per Section 3 if needed, documented clearly in the `.env` example) |

---

## 7. What not to do in this stage

- **Do not enable auth by default.** `auth_enabled` defaults to `False`, full stop — this is a guiding-principle-level decision, not a convenience default to revisit later.
- **Do not run any auth-related code when `auth_enabled=False`**, beyond checking that single flag. No "lightweight" always-on validation layer, even one that always passes.
- **Do not let a query-scoped key succeed against an ingestion route**, or vice versa. Test this explicitly — it's the kind of bug that looks like it works in casual testing and only surfaces as a real security gap in production.
- **Do not log the API key itself** on an auth failure or success. Log whether a key was present, whether it was valid, and which scope was required/had — never the key value (this follows directly from Stage 5's redaction rule).
- **Do not key rate limiting by IP when auth is enabled.** Key by the authenticated identity (the API key) in that case.
- **Do not build multi-tenancy as a default behavior.** It's a documented extension pattern, not a feature every deployment carries the cost of.
- **Do not implement billing, spend caps, or usage-based throttling beyond simple rate limiting.** That's explicitly out of scope — the framework prevents abuse, it doesn't manage a billing relationship.

---

## 8. Instructions to the implementing agent

1. Extend `ragframework/config.py`'s `api_keys` field (or add an adjacent field) to associate each key with one or more scopes (`query`, `ingest`), keeping a clear, documented `.env` format for the scoped shape (e.g., `API_KEYS__QUERY` / `API_KEYS__INGEST` as separate lists, or a structured JSON value — pick one and document it plainly in the example `.env`).
2. Implement `ragframework/api/deps.py`: a `require_scope(scope: str)` dependency factory that, when `Settings.auth_enabled` is `True`, extracts the API key from the request (e.g., an `Authorization: Bearer <key>` header), validates it against the configured keys for that scope, and raises an appropriate `HTTPException` (401/403) on failure; when `Settings.auth_enabled` is `False`, this dependency is a no-op that FastAPI never meaningfully invokes with real checks.
3. Apply `Depends(require_scope("query"))` to the `query.py` router's route, and `Depends(require_scope("ingest"))` to every route in `ingestion.py`. Leave `health.py` with no auth dependency.
4. Add `slowapi`'s limiter to `ragframework/api/main.py`, with a key function that reads the authenticated API key when present, falling back to client IP only when `auth_enabled=False`.
5. Configure distinct rate limits for the query router vs. the ingestion router (expose these as `Settings` fields with reasonable defaults, e.g., `query_rate_limit: str = "60/minute"`, `ingestion_rate_limit: str = "10/minute"`).
6. Write the multi-tenancy pattern as a short markdown note (for later inclusion in Stage 14's documentation) describing where a `tenant_id` metadata filter would be threaded through `BaseVectorStore.similarity_search()` — do not implement it.
7. Manually verify: with `auth_enabled=False`, confirm all routes work with no headers at all; with `auth_enabled=True`, confirm a valid `query`-scoped key succeeds on `/v1/query` and is rejected (403, not a silent pass-through) on `/v1/documents`; confirm an invalid/missing key is rejected with 401; confirm rate limiting actually triggers a 429 when exceeded, and that the limiter key differs correctly between the auth-enabled and auth-disabled cases; grep logs from a failed-auth request and confirm the API key value never appears.

---

## 9. Definition of done

- [ ] `auth_enabled` defaults to `False`; with it `False`, no auth-related overhead runs on any route.
- [ ] When enabled, `query`-scoped keys work on `/v1/query` and are rejected on all ingestion routes; `ingest`-scoped keys work the other way around.
- [ ] Invalid or missing keys are rejected with an appropriate status code when auth is enabled.
- [ ] Rate limiting is active on both the query and ingestion routers with independently configurable limits.
- [ ] Rate-limit keying uses the authenticated API key when auth is enabled, IP only otherwise.
- [ ] No API key value ever appears in a log line, including on auth failures.
- [ ] The multi-tenancy pattern is documented but not implemented in the FAISS connector.

## 10. Handoff to Stage 7

Stage 7 moves ingestion off the synchronous request path onto a job queue. The `ingest`-scoped auth dependency built in this stage must continue to protect the new `POST /v1/documents` behavior once it becomes "enqueue a job" rather than "process synchronously" — verify auth still applies correctly after Stage 7's changes rather than assuming it carries over automatically.
