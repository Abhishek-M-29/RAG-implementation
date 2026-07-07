# Stage 12 of 14 — Testing Strategy

**Source roadmap section covered:** §17 (Testing strategy)
**Depends on:** Stage 11 — the full system (backend, frontend, security hardening) must exist so tests exercise real, finished behavior rather than a moving target.
**Followed by:** Stage 13 — Deployment & CI/CD.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure, never operated as a hosted service by us.

**Connector scope for the whole build:** only **FAISS** and **Google Gemini** are implemented; every other backend is a documented extension point.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** the seven correctness fixes are already applied.

**What already exists when this stage starts:** the complete backend (Stages 1–9), reference frontend (Stage 10), and security hardening (Stage 11); `tests/contract/`, `tests/unit/`, `tests/integration/` exist as empty directories from Stage 1's repo restructure.

---

## 2. Why this stage exists

Because this is a multi-connector *framework*, not a single-purpose app, the highest-value tests are **contract tests** — tests that run against every registered connector through the same suite. This is what catches a connector silently violating the interface (e.g., a `delete()` that's actually a no-op) — a class of bug that ordinary unit tests, written against one specific connector's implementation details, would never catch.

## 3. Test suite structure

```
tests/
├── contract/
│   ├── test_vector_store_contract.py   # parametrized over every registered connector
│   └── test_llm_contract.py
├── unit/                               # ingestion, chunking, config parsing
└── integration/                        # full query/ingestion flow against FastAPI TestClient
```

## 4. Contract tests

```python
# tests/contract/test_vector_store_contract.py
import pytest
from ragframework.vectorstores.registry import VECTOR_STORE_REGISTRY

@pytest.mark.parametrize("name,cls", VECTOR_STORE_REGISTRY.items())
def test_add_search_delete_roundtrip(name, cls, sample_docs):
    store = cls.from_config(test_config_for(name))
    ids = store.add_documents(sample_docs)
    results = store.similarity_search("test query", k=3)
    assert results
    store.delete(ids)
    assert store.health_check()
```

Today this parametrizes over exactly one connector (FAISS); the value is that adding the pgvector/Qdrant connectors later means they're automatically exercised by the same suite with **zero new test code**. Write `test_llm_contract.py` analogously, parametrized over `LLM_PROVIDER_REGISTRY`, verifying `from_config()` returns a usable `BaseChatModel` (e.g., a minimal `.invoke()` call succeeds against a trivial prompt, using a real or appropriately mocked Gemini call depending on CI budget — see Section 6).

The contract test for the vector store must specifically assert the full lifecycle the contract promises: adding documents makes them searchable, and deleting them makes them stop being searchable (`assert results` after add, then re-run `similarity_search` after `delete` and assert the deleted content is gone — the snippet above checks `health_check()` after delete but a thorough version should also verify the deleted IDs are actually absent from a follow-up search, not just that the store is still healthy).

## 5. What stays as-is

Keep the existing `tests/test_pipeline.py` and `tests/test_cli.py` (ported into `tests/unit/` or `tests/integration/` as appropriate during the Stage 1 restructure, if not already relocated) largely as-is — they test ingestion/chunking logic that doesn't change across this entire build. Do not rewrite working tests just because their location moved.

## 6. Unit and integration scope

- **`tests/unit/`** — ingestion, chunking, and config parsing (`Settings` validation, including the fail-fast startup checks from Stage 8). These should run fast, with no network calls and no real vector store/LLM instantiation beyond what a fixture can construct cheaply.
- **`tests/integration/`** — full query/ingestion flow against FastAPI's `TestClient`, covering: a query round trip through cache (Stage 4), auth enforcement per scope (Stage 6), the async ingestion job lifecycle (Stage 7), streaming response shape (Stage 8), health/readiness (Stage 9), and CORS/upload validation (Stage 11). Decide explicitly whether integration tests hit the real Gemini API (with a test key, budget-permitting) or a mocked `BaseChatModel` — document the choice, since it affects CI cost and reliability (see Stage 13 for how this interacts with the CI pipeline).

---

## 7. What not to do in this stage

- **Do not write connector-specific test logic that isn't parametrized.** If a test is really testing "does FAISS work," ask whether it should instead be testing "does the vector store contract hold" — parametrize it so future connectors inherit the coverage for free.
- **Do not rewrite `test_pipeline.py`/`test_cli.py`'s working logic** just because they moved during the Stage 1 restructure — relocate and update imports only.
- **Do not let unit tests make real network calls** to the Gemini API or require a real FAISS index on disk — those belong in integration or contract tests with clear fixtures.
- **Do not test the contract suite against a connector that isn't registered.** The contract tests derive their parametrization from `VECTOR_STORE_REGISTRY`/`LLM_PROVIDER_REGISTRY` directly — don't hardcode a connector name that duplicates what the registry already provides, since that's exactly the kind of drift the parametrized approach is designed to avoid.
- **Do not skip testing the `delete()` round trip's actual effect on search results.** A test that only checks `health_check()` after delete would pass even if `delete()` silently did nothing.
- **Do not treat this stage's tests as optional coverage for "later."** They are the mechanism by which the next connector added to this framework (post-launch) gets verified automatically — skipping them undermines the entire "one new class and register it" extension promise from the guiding principles.

---

## 8. Instructions to the implementing agent

1. Confirm `tests/contract/`, `tests/unit/`, `tests/integration/` exist (from Stage 1) and relocate/update imports for any pre-existing `test_pipeline.py`/`test_cli.py` logic into the appropriate directory.
2. Write `tests/contract/test_vector_store_contract.py` exactly as specified in Section 4, parametrized over `VECTOR_STORE_REGISTRY`, including a follow-up search assertion after `delete()` that confirms the deleted content is actually gone.
3. Write `tests/contract/test_llm_contract.py`, parametrized over `LLM_PROVIDER_REGISTRY`, verifying `from_config()` produces a usable `BaseChatModel`.
4. Write `tests/unit/` coverage for `core/chunking.py`, `core/ingestion.py` (including the per-file error surfacing from correctness fix #1), and `Settings` parsing/validation (including the fail-fast checks from Stage 8).
5. Write `tests/integration/` coverage using FastAPI's `TestClient` for: a full query round trip with cache hit/miss assertions, auth scope enforcement (both allowed and rejected cases), the async ingestion job lifecycle from `queued` through `done`/`failed`, the SSE streaming response shape, `/v1/health` vs `/v1/ready` behavior under a simulated connector failure, and CORS/upload validation from Stage 11.
6. Decide and document whether integration/contract tests against the Gemini connector use a real test API key or a mocked `BaseChatModel`, and implement fixtures accordingly.
7. Add test fixtures (`sample_docs`, `test_config_for(name)`, etc.) in a shared `conftest.py`.
8. Run the full suite and confirm all tests pass; deliberately introduce a broken `delete()` (make it a no-op) temporarily and confirm the contract test suite catches it, then revert.

---

## 9. Definition of done

- [ ] `tests/contract/test_vector_store_contract.py` and `test_llm_contract.py` exist, parametrized over their respective registries, with zero hardcoded connector names outside the registry-driven parametrization.
- [ ] The vector store contract test verifies the full add → search → delete → search-again lifecycle, not just `health_check()`.
- [ ] Existing `test_pipeline.py`/`test_cli.py` logic is preserved, relocated, and passing.
- [ ] Unit tests cover chunking, ingestion error handling, and `Settings` validation with no real network calls.
- [ ] Integration tests cover the full query/ingestion flow, auth scopes, streaming shape, health/readiness, and CORS/upload validation via `TestClient`.
- [ ] A deliberately broken `delete()` implementation is demonstrated to fail the contract suite (then reverted).
- [ ] The Gemini test strategy (real key vs. mock) is documented.

## 10. Handoff to Stage 13

Stage 13 wires this full test suite into a CI pipeline (lint → type-check → contract + unit + integration tests → build images), gating image builds on these tests passing. It needs to know from this stage whether any tests require secrets (e.g., a real Gemini test key) so it can wire the appropriate CI secret injection.
