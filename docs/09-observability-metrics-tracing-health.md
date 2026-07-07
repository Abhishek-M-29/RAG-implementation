# Stage 9 of 14 — Observability: Metrics, Tracing & Health

**Source roadmap section covered:** §14 (Observability, all subsections 14.1–14.7)
**Depends on:** Stage 8 — reliability instrumentation points (retries, timeouts, streaming) must exist, since this stage traces and measures them.
**Followed by:** Stage 10 — Frontend.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure, never operated as a hosted service by us.

**Connector scope for the whole build:** only **FAISS** and **Google Gemini** are implemented; every other backend is a documented extension point.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** the seven correctness fixes are already applied.

**What already exists when this stage starts:** structured logging with request-ID propagation (Stage 5); retries, timeouts, and streaming at the connector layer (Stage 8); `/v1/health` and `/v1/ready` exist as stubs (Stage 3) that this stage completes; `health_check()` is implemented on the FAISS connector (Stage 2).

---

## 2. Why this stage exists

Observability is a **distinct concern from logging** (Stage 5) — logging tells you what happened to one request; observability tells you the health and behavior of the whole system over time. This stage instruments the system so an adopter can answer questions like "is this instance healthy," "what's our p99 latency," and "why was this specific query slow" without guessing.

---

## 3. Instrumentation approach: OpenTelemetry

Use **OpenTelemetry** as the instrumentation layer, not a vendor-specific SDK (e.g., not Datadog's SDK directly). This matches the framework's core principle: OTel decouples *how you instrument* from *where you send it* — an adopter points the OTel exporter at Grafana Cloud, Honeycomb, Datadog, AWS X-Ray, or a self-hosted Jaeger/Tempo, and the framework code never needs to know which. `ragframework/observability/tracing.py` and `ragframework/observability/metrics.py` set up the OTel SDK; the exporter endpoint is one config value (`Settings.otel_exporter_endpoint: str | None = None`).

## 4. Metrics

| Metric | Type | Why it matters |
|---|---|---|
| Request rate | Counter | Overall traffic |
| Latency (p50/p95/p99) per stage | Histogram | Embedding, retrieval, and generation have very different cost profiles — track separately |
| Cache hit rate | Gauge | Directly tied to both latency and LLM cost (feeds off Stage 4's cache layers) |
| Tokens in / out per request | Counter | Feeds cost tracking (Section 8 below) |
| Ingestion queue depth | Gauge | Signals whether ingestion workers (Stage 7) need to scale |
| Error rate, by stage | Counter | Where failures cluster |

Implement each of these in `ragframework/observability/metrics.py` using OTel's metrics API, and instrument the call sites already built in prior stages: cache hit/miss (Stage 4), retry/timeout outcomes (Stage 8), ingestion job transitions (Stage 7), and per-stage latency around embedding/retrieval/generation (Stage 2/3 core logic).

## 5. Tracing

Instrument spans across the full request lifecycle:

- **Query path:** `embed_query` → `vector_search` → `build_prompt` → `llm_generate`
- **Ingestion path:** `extract_text` → `chunk` → `embed_batch` → `upsert`

A single request's waterfall becomes visible in whatever backend the adopter's OTel exporter points at — this is the fastest way to answer "why was this specific query slow" without guessing. Propagate the Stage 5 request ID as a trace attribute so a support conversation can correlate a log line with a trace directly.

## 6. Health and readiness

This stage completes the `/v1/health` and `/v1/ready` stubs left in place since Stage 3:

- **`GET /v1/health`** — liveness only: is the process up. Keep this as close to a hardcoded `{"status": "ok"}` as possible; it should never call out to a connector, cache, or external service — its entire purpose is to answer "is the process alive," fast and unconditionally.
- **`GET /v1/ready`** — readiness: calls `health_check()` on the configured vector store connector (the contract method from Stage 1, implemented in Stage 2) and does a lightweight reachability check on the configured LLM connector. A load balancer or orchestrator should stop routing traffic to an instance that fails `/ready`.

Do not conflate the two. A common mistake is making `/v1/health` do the same checks as `/v1/ready` — this defeats the purpose of having two separate endpoints, since an orchestrator polling liveness at high frequency would then be hammering the vector store on every liveness check.

## 7. RAG-specific observability

General infrastructure tracing (Section 5) tells you a query was slow; it doesn't tell you *why an answer was wrong*. For that, add an **optional hook for LangSmith or Langfuse** — off by default, one config flag to enable (`Settings.rag_tracing_provider: Literal["none", "langsmith", "langfuse"] = "none"`) — that traces exactly which chunks were retrieved and what final prompt was sent to the LLM for any given answer. This is the single highest-leverage tool for debugging retrieval quality issues, and it's a distinct concern from infrastructure observability — don't conflate this hook with the OTel tracing in Section 5; they answer different questions and can both be active simultaneously.

## 8. Cost tracking

Since every generation call has a real dollar cost, token counts (in/out) are captured as a metric (Section 4's table) on every request, tagged with the LLM connector in use. **The framework does not implement billing or budget alerts itself** — it exposes the numbers so the adopter can wire their own threshold alerts on top (Prometheus alerting rules, CloudWatch alarms, etc.), consistent with "bring your own infrastructure."

## 9. Alerting and dashboards

Alerting is explicitly the adopter's responsibility — the framework's job is to expose the right signals (Section 4), not to own a notification pipeline. Ship **one reference asset** in the repo to lower the barrier: an example Grafana dashboard JSON at `examples/observability/grafana-dashboard.json`, covering the metrics in Section 4, that an adopter can import as a starting point. Do not build more than this one reference asset — a full alerting pipeline is explicitly out of scope.

---

## 10. What not to do in this stage

- **Do not use a vendor-specific SDK (Datadog, New Relic, etc.) directly in framework code.** OpenTelemetry only — the exporter target is the adopter's one config value, never a hardcoded destination.
- **Do not make `/v1/health` call any connector, cache, or external dependency.** That's `/v1/ready`'s job. Keep liveness cheap and unconditional.
- **Do not conflate RAG-specific tracing (LangSmith/Langfuse) with general OTel tracing.** They're separate, both off-by-default-or-not independently, and serve different debugging purposes.
- **Do not implement billing, spend caps, or alerting logic inside the framework.** Expose the metrics; let the adopter wire alerts on their own infrastructure.
- **Do not ship more than one example dashboard.** A full library of pre-built dashboards is scope creep for a framework that explicitly doesn't own the adopter's observability stack.
- **Do not make OTel tracing/metrics a hard dependency that breaks the app if no exporter endpoint is configured.** It should no-op gracefully (or use a local/no-op exporter) when `otel_exporter_endpoint` is unset, consistent with the "sane defaults, zero external dependencies out of the box" principle.

---

## 11. Instructions to the implementing agent

1. Add the OpenTelemetry SDK and relevant exporter packages as dependencies.
2. Create `ragframework/observability/tracing.py`: set up the OTel tracer provider, configure the exporter from `Settings.otel_exporter_endpoint` (no-op/console exporter if unset), and instrument the query-path spans (`embed_query`, `vector_search`, `build_prompt`, `llm_generate`) and ingestion-path spans (`extract_text`, `chunk`, `embed_batch`, `upsert`) at their respective call sites from prior stages.
3. Create `ragframework/observability/metrics.py`: define and record each metric from the Section 4 table at its respective call site (cache layer from Stage 4, retry/error outcomes from Stage 8, job queue depth from Stage 7, token counts from the LLM connector calls).
4. Attach the Stage 5 request ID as a trace attribute on the root span of each request.
5. Complete `ragframework/api/routers/health.py`: `/v1/health` returns a fast, unconditional `{"status": "ok"}`; `/v1/ready` calls the configured vector store's `health_check()` and does a lightweight LLM reachability check, returning a non-200 status if either fails.
6. Add `Settings.rag_tracing_provider` and the corresponding optional LangSmith/Langfuse integration hook around the retrieval/generation call sites, off by default.
7. Create `examples/observability/grafana-dashboard.json` covering the six metrics from Section 4.
8. Manually verify: with no OTel exporter configured, confirm the app still starts and runs normally (no crash, no hang); configure a local/test OTel collector and confirm spans and metrics arrive for both a query and an ingestion job; kill the configured vector store's underlying index file mid-run and confirm `/v1/ready` correctly reports not-ready while `/v1/health` still reports OK; enable the RAG tracing hook and confirm it captures retrieved chunks and the final prompt for a sample query.

---

## 12. Definition of done

- [ ] OpenTelemetry tracing and metrics are implemented with an adopter-configurable exporter endpoint, no-op-safe when unset.
- [ ] All six metrics from Section 4 are recorded at the correct call sites.
- [ ] Query-path and ingestion-path spans are implemented exactly as named in Section 5, carrying the Stage 5 request ID.
- [ ] `/v1/health` is unconditional and fast; `/v1/ready` genuinely checks vector store and LLM connector health.
- [ ] The optional LangSmith/Langfuse hook is off by default and independent of general OTel tracing.
- [ ] `examples/observability/grafana-dashboard.json` exists and covers the Section 4 metrics.
- [ ] No billing, alerting, or spend-cap logic exists inside the framework.

## 13. Handoff to Stage 10

Stage 10 builds the reference frontend, whose settings/status page displays health indicators sourced directly from `/v1/ready` (completed in this stage) and whose chat page's "sources" panel depends on the `sources` metadata delivered via the Stage 8 streaming contract. No further backend changes are required for Stage 10 to proceed — it consumes the API surface as it now stands.
