# Stage 11 of 14 — Security Hardening

**Source roadmap section covered:** §16 (Security hardening)
**Depends on:** Stage 10 — the frontend must exist so CORS can be configured against its real origin, and the document-upload flow exists for this stage's file-validation work to protect.
**Followed by:** Stage 12 — Testing Strategy.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure, never operated as a hosted service by us.

**Connector scope for the whole build:** only **FAISS** and **Google Gemini** are implemented; every other backend is a documented extension point.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** the seven correctness fixes are already applied — most relevantly here, fix #3: `FAISS.load_local(..., allow_dangerous_deserialization=True)` is retained but documented as an accepted, connector-specific constraint. This stage doesn't remove that constraint (removing it entirely requires a different vector store connector, out of scope for this build) — it makes sure that constraint is the *only* place this risk category exists, and that nothing else in the system compounds it.

**What already exists when this stage starts:** a complete backend (Stages 2–9) and reference frontend (Stage 10); structured logging with redaction rules (Stage 5); optional auth (Stage 6); a document-upload flow via the async ingestion pipeline (Stage 7).

---

## 2. Why this stage exists

This stage is a hardening pass across the whole system built so far, not new feature work. It closes off the concrete attack surfaces the roadmap identifies: malicious uploads, secret leakage, unencrypted transport, overly permissive CORS, and over-privileged credentials.

## 3. File validation on upload

Enforce max upload size, verify actual content type (not just the `.pdf` extension check the original POC's `collect_pdf_paths` performed), reject malformed/decompression-bomb-style PDFs, and optionally run a malware scan before processing. This applies to the upload handling built in Stage 7's ingestion pipeline — add validation **before** the file is written to object storage or enqueued, not after a worker has already started processing it.

Be specific about what "verify actual content type" means in practice: check the file's magic bytes/signature, not just its extension or client-supplied `Content-Type` header — a file renamed to `.pdf` with different actual content should be rejected at this stage, before it reaches `PyPDFLoader` in the ingestion worker.

## 4. Secrets never touch logs or responses

Enforced by two mechanisms already built in earlier stages, and confirmed (not re-implemented) here:

- The Stage 5 logging redaction rule (never log API keys or credentials).
- The Stage 10 settings-status endpoint never echoing raw keys.

This stage's job is to **audit** both of these end to end across the full system as it now stands — including any new log lines or response fields added in Stages 6 through 10 that might not have existed when the original rules were written. Grep the full codebase for any place a `Settings` object, a connector `config` dict, or an `api_keys` value might reach a log call or an HTTP response without going through the established redaction pattern.

## 5. TLS and CORS

- **TLS everywhere** at the reverse proxy layer (documented in Stage 3, fully specified in Stage 13's deployment guide) — the framework itself doesn't terminate TLS, but this stage confirms the deployment documentation is explicit that running without TLS in front of the API is not a supported configuration for anything beyond local development.
- **CORS locked down** to known frontend origins, not `*`. Add `Settings.cors_allowed_origins: list[str] = []` and wire FastAPI's CORS middleware to it in `ragframework/api/main.py`. An empty list should mean "no cross-origin requests allowed," not "allow everything" — the framework must never default to `*`.

## 6. Least-privilege credentials

For whatever infrastructure the adopter points connectors at, the documentation (extended in Stage 14) should recommend a vector-store-connector-scoped database user, not an admin credential — even though the only connector shipped now (FAISS) is a local file, not a networked database with its own credential model. Write this as forward-looking guidance for adopters and for whoever builds the next connector (pgvector, Qdrant), so the credential-scoping expectation is established now rather than retrofitted later.

## 7. No pickle-based deserialization risk beyond what's documented

The FAISS connector's `allow_dangerous_deserialization=True` (correctness fix #3) is an **accepted, documented constraint of that specific connector** — not something this stage tries to eliminate. A future pgvector/Qdrant connector removes this risk category entirely, which is one more reason those are natural next connectors to add. This stage's job regarding fix #3 is narrow and specific: confirm the documentation calling out this constraint is accurate, current, and visible to adopters (it will be finalized in Stage 14's per-connector setup guide) — not to attempt a workaround that isn't warranted by anything else in this roadmap.

---

## 8. What not to do in this stage

- **Do not default `cors_allowed_origins` to `["*"]` or leave CORS unconfigured (which FastAPI may otherwise leave permissive by omission).** An empty list must mean no cross-origin access.
- **Do not validate uploaded files by extension or client-supplied MIME type alone.** Check actual file signature/magic bytes.
- **Do not attempt to remove or "fix" the FAISS `allow_dangerous_deserialization=True` constraint in this stage.** It's an accepted, documented property of the FAISS connector specifically — removing it is a different connector's job, not a hardening task for this one.
- **Do not implement TLS termination inside the FastAPI application.** That remains a reverse-proxy/deployment concern.
- **Do not add credential-scoping code for a database connector that doesn't exist yet.** Document the least-privilege expectation for future connector authors; don't build speculative infrastructure for pgvector/Qdrant now.
- **Do not skip auditing code added in Stages 6–10 for secret leakage** just because the redaction rule was established back in Stage 5 — new code paths since then need the same scrutiny applied to them explicitly.

---

## 9. Instructions to the implementing agent

1. Add file-signature validation (e.g., checking magic bytes for PDF) to the upload handling in `ragframework/api/routers/ingestion.py`, rejecting mismatches before the file reaches object storage.
2. Add a configurable max upload size (`Settings.max_upload_size_bytes`) and reject oversized uploads at the same point.
3. Add basic malformed-PDF/decompression-bomb protection (e.g., a page-count or expanded-size sanity check) before handing the file to `PyPDFLoader` in the Stage 7 worker. Document malware scanning as an optional adopter-side integration point rather than building a scanner into the framework.
4. Add `Settings.cors_allowed_origins: list[str] = []` and wire FastAPI's `CORSMiddleware` in `ragframework/api/main.py`, defaulting to no cross-origin access.
5. Audit every log call added since Stage 5 (across Stages 6–10) for potential secret exposure — specifically auth failure logs (Stage 6), job error details (Stage 7), and any new debug-level output.
6. Audit every API response schema and the frontend's settings/status display for accidental secret exposure — specifically the connector-status fields added in Stage 3/10.
7. Write (or hand to Stage 14 as input) the least-privilege credential guidance for future networked vector store connectors.
8. Confirm the FAISS connector's `allow_dangerous_deserialization=True` docstring (Stage 2) accurately reflects the accepted-constraint framing and is unchanged by this stage.
9. Manually verify: attempt to upload a non-PDF file renamed with a `.pdf` extension and confirm rejection; attempt to upload a file exceeding the configured max size and confirm rejection; issue a cross-origin request from an unlisted origin and confirm it's blocked by CORS; issue one from the frontend's actual configured origin and confirm it succeeds; grep the full log output of a complete query + ingestion + auth-failure cycle for any API key substring and confirm zero matches.

---

## 10. Definition of done

- [ ] Uploaded files are validated by actual content signature, not extension or client-supplied MIME type.
- [ ] A configurable max upload size is enforced.
- [ ] Malformed/decompression-bomb-style PDFs are rejected before reaching the ingestion worker's parser.
- [ ] CORS defaults to no cross-origin access and is configurable to an explicit allowlist including the frontend's real origin.
- [ ] A full audit confirms no API key or credential appears in any log line or API/frontend response across the entire system as built through Stage 10.
- [ ] Documentation calling out the FAISS `allow_dangerous_deserialization=True` constraint is accurate and will carry forward into Stage 14's docs.
- [ ] Least-privilege credential guidance for future networked connectors is written.
- [ ] No TLS termination logic exists inside the FastAPI application itself.

## 11. Handoff to Stage 12

Stage 12 writes the contract test suite that parametrizes over every registered connector. It should include tests confirming the security properties established in this stage don't regress — e.g., a contract-adjacent test verifying `delete()` behavior doesn't reintroduce a deserialization risk, and integration tests confirming CORS and upload validation behave as configured.
