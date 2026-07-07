# Stage 2 of 14 — Connector Implementations (FAISS, Gemini) & Configuration

**Source roadmap sections covered:** §6.3 (Connectors shipped now), §6.5 (Registry / factory), §7 (Configuration)
**Depends on:** Stage 1 — `BaseVectorStore` and `BaseLLMProvider` contracts must exist and be stable.
**Followed by:** Stage 3 — Backend API Routing & Schemas.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure.

**Connector scope for the whole build:** only two concrete connectors are ever implemented — **FAISS** (vector store) and **Google Gemini** (LLM). Everything else is a documented extension point, not something you build now, in this stage or any other.

**Guiding principles (apply throughout):** bring your own backend; interface first, implementation second; sane defaults, everything swappable; observability and reliability built in from day one; the framework is not a hosted service.

**Baseline assumption:** the seven correctness fixes are already applied to the original codebase, including: chunk size/overlap no longer disagreeing between `main.py` and `chunking.py`, the FAISS `allow_dangerous_deserialization=True` flag already documented as an accepted constraint, and the embedding/LLM singletons already guarded rather than unlocked globals. This stage is where the chunk-size fix and the singleton fix get their permanent home — see Section 5.

**Stage 1 recap (what already exists when this stage starts):** `ragframework/vectorstores/base.py` defines `BaseVectorStore`; `ragframework/llms/base.py` defines `BaseLLMProvider`; the full package skeleton exists with stub files for `faiss_store.py`, `google_genai.py`, and both `registry.py` files.

---

## 2. Why this stage exists

Stage 1 built the *shape* of the connector layer. This stage fills it with the two real, working connectors, wires them into a factory/registry so the rest of the framework can request "the configured vector store" or "the configured LLM" without knowing which one that is, and introduces the `Settings` model that drives that configuration end to end. By the end of this stage, the existing POC's actual retrieval and generation behavior is fully reproduced — just now behind the connector contracts instead of hardcoded.

---

## 3. FAISS vector store connector

Create `ragframework/vectorstores/faiss_store.py`, wrapping LangChain's `FAISS` vectorstore, ported directly from the current `src/embedding.py` logic:

- **`from_config(config)`** — loads or initializes a FAISS index at the path given in `config["index_path"]`. This is where the `allow_dangerous_deserialization=True` flag lives — carry it forward exactly as documented in the correctness-fixes baseline: it is safe only because this connector fully controls the index files it loads, and that constraint must stay documented in the docstring here, not just in a roadmap that adopters may never read.
- **`add_documents(documents)`** — calls `FAISS.add_documents` if an index already exists in memory, or `FAISS.from_documents` on first write. Returns the assigned chunk IDs.
- **`similarity_search(query, k=5)`** — a direct passthrough to the underlying FAISS similarity search. This logic does not change from the current `src/retrieval.py` — do not "improve" the search logic in this stage, just move it behind the contract.
- **`delete(ids)`** — **FAISS has no native delete-by-id.** Implement this by rebuilding the index from the remaining documents: read all documents out of the docstore, filter out the deleted IDs, rebuild the index from what's left. Document this clearly, in the code and in any adopter-facing docs: **deletes are O(n) on FAISS, not O(1).** This is a known, accepted cost of the local FAISS connector — it is exactly the limitation a future pgvector/Qdrant connector would remove, and is one more reason those are natural next connectors, not something to work around here.
- **`health_check()`** — confirms the index file is loadable and its `.ntotal` attribute is queryable. Keep this fast; it will be called on the readiness endpoint in Stage 9.

```python
# ragframework/vectorstores/registry.py
from .faiss_store import FaissStore

VECTOR_STORE_REGISTRY = {
    "faiss": FaissStore,
    # "pgvector": PgVectorStore,   # future — do not implement in this build
    # "qdrant": QdrantStore,       # future — do not implement in this build
}

def get_vector_store(settings) -> "BaseVectorStore":
    connector = VECTOR_STORE_REGISTRY.get(settings.vector_store)
    if connector is None:
        raise ValueError(
            f"Unknown vector_store '{settings.vector_store}'. "
            f"Available: {list(VECTOR_STORE_REGISTRY)}"
        )
    return connector.from_config(settings.vector_store_config)
```

---

## 4. Google Gemini LLM connector

Create `ragframework/llms/google_genai.py`, wrapping `ChatGoogleGenerativeAI`, ported directly from the current `src/generation.py`:

- Reads the model name and API key **from adopter-supplied config**, not from a fixed `.env` lookup. The current code's `os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")` becomes `config["api_key"]`. This is the single most important line in this connector — it's what makes "bring your own API key" actually true instead of aspirational.
- Retries, timeouts, and streaming are **not** implemented here — they belong to Stage 8 (Reliability), which builds them once at this same connector layer so every current and future LLM connector inherits them automatically. Leave clear extension seams (e.g., a place `.stream()` will be exposed through) but do not implement retry/backoff logic in this stage.

```python
# ragframework/llms/registry.py
from .google_genai import GoogleGenAIProvider

LLM_PROVIDER_REGISTRY = {
    "google_genai": GoogleGenAIProvider,
    # "openai": OpenAIProvider,       # future — do not implement in this build
    # "anthropic": AnthropicProvider, # future — do not implement in this build
}

def get_llm(settings) -> "BaseChatModel":
    connector = LLM_PROVIDER_REGISTRY.get(settings.llm_provider)
    if connector is None:
        raise ValueError(
            f"Unknown llm_provider '{settings.llm_provider}'. "
            f"Available: {list(LLM_PROVIDER_REGISTRY)}"
        )
    return connector.from_config(settings.llm_config)
```

This registry pair — about 30 lines total across both files — is the entire "bring your own vector DB and API key" promise. Everything upstream (the API layer in Stage 3, the CLI, the ingestion worker in Stage 7) only ever calls `get_vector_store(settings)` and `get_llm(settings)`. No other framework code should ever import `FaissStore` or `GoogleGenAIProvider` by name outside of these two registry files and their own tests.

---

## 5. The `Settings` model

Create `ragframework/config.py`:

```python
# ragframework/config.py
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    # Connector selection
    vector_store: Literal["faiss"] = "faiss"
    vector_store_config: dict = {"index_path": "index_store/faiss_index"}

    llm_provider: Literal["google_genai"] = "google_genai"
    llm_config: dict = {}          # {"api_key": ..., "model": "gemini-3.1-flash-lite"}

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 100

    # Retrieval
    top_k: int = 5

    # Cross-cutting backends (Stages 4, 5, 6)
    cache_backend: Literal["memory", "redis"] = "memory"
    memory_backend: Literal["memory", "redis"] = "memory"
    redis_url: str | None = None

    # Auth
    auth_enabled: bool = False
    api_keys: list[SecretStr] = []

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
```

Example `.env` for the default local combination:

```ini
VECTOR_STORE=faiss
VECTOR_STORE_CONFIG__INDEX_PATH=index_store/faiss_index

LLM_PROVIDER=google_genai
LLM_CONFIG__API_KEY=your-gemini-key
LLM_CONFIG__MODEL=gemini-3.1-flash-lite

CACHE_BACKEND=memory
MEMORY_BACKEND=memory
AUTH_ENABLED=false
```

The `Literal["faiss"]` / `Literal["google_genai"]` typing is deliberate — it makes the current connector scope explicit in the type system itself, not just in documentation. Widening these to include a future connector is a one-line change per connector added, at the point that connector is actually built (not now).

**This is where correctness fix #5 permanently lives.** `chunk_size` and `chunk_overlap` now have exactly one source of truth — this `Settings` model. `main.py`/`cli.py` and `core/chunking.py` must both read from `Settings`, not from separate local defaults. If you find a hardcoded `1000`/`100` or `2500`/`250` anywhere else in the codebase after this stage, that is a regression of the fix, not a stylistic choice — remove it.

### Environment variables introduced in this stage

| Variable | Default | Description |
|---|---|---|
| `VECTOR_STORE` | `faiss` | Selected vector store connector |
| `VECTOR_STORE_CONFIG__INDEX_PATH` | `index_store/faiss_index` | FAISS index location |
| `LLM_PROVIDER` | `google_genai` | Selected LLM connector |
| `LLM_CONFIG__API_KEY` | — | Adopter's own Gemini API key |
| `LLM_CONFIG__MODEL` | `gemini-3.1-flash-lite` | Gemini model name |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `100` | Overlap between chunks |
| `TOP_K` | `5` | Retrieved chunks per query |

(`CACHE_BACKEND`, `MEMORY_BACKEND`, `REDIS_URL`, `AUTH_ENABLED`, `API_KEYS` are declared on the same `Settings` model now, for a single source of truth, but are only *used* starting in Stages 4 and 6 respectively — don't wire behavior to them yet.)

---

## 6. Rebuilding `core/generation.py`

With `BaseLLMProvider` supplying a ready `BaseChatModel`, rebuild `ragframework/core/generation.py`'s LCEL chain to accept that model as a parameter rather than constructing `ChatGoogleGenerativeAI` itself. The chain's actual prompt/response logic is otherwise unchanged from the POC — this is a dependency-injection change, not a behavior change. `core/generation.py` must never import from `ragframework/llms/google_genai.py` directly; it only ever receives a `BaseChatModel` produced by `get_llm(settings)`.

---

## 7. What not to do in this stage

- **Do not implement a second vector store or LLM connector.** No pgvector stub, no OpenAI stub, no "just to test the registry pattern" placeholder class. The registries' commented-out lines are documentation, not a to-do list for this stage.
- **Do not implement retries, timeouts, or streaming in the Gemini connector.** That's Stage 8's job, done once at the connector layer so it's inherited automatically — implementing a partial version here creates something Stage 8 has to unwind.
- **Do not read API keys from `os.getenv()` anywhere inside the connector classes.** All configuration must flow through `Settings` → the registry's `from_config(config)` call. A connector that falls back to reading environment variables directly defeats the purpose of the `Settings` model and breaks the "adopter's own key" guarantee if two adopters' environments differ.
- **Do not let the FAISS connector's `delete()` silently do nothing or raise `NotImplementedError`.** The contract requires it to work; O(n) rebuild is the accepted cost, not an excuse to skip it.
- **Do not hardcode `chunk_size`/`chunk_overlap`/`top_k` anywhere outside `Settings`.** Every call site should read these off the settings object (or a value explicitly passed down from it), never a local literal.
- **Do not put real API keys in `.env.example`, tests, or example configs.** Use obvious placeholders like `your-gemini-key`.

---

## 8. Instructions to the implementing agent

1. Confirm Stage 1's contracts (`BaseVectorStore`, `BaseLLMProvider`) exist unmodified.
2. Write `ragframework/config.py` exactly as specified in Section 5.
3. Write `ragframework/vectorstores/faiss_store.py` implementing all five `BaseVectorStore` methods as described in Section 3, porting logic from the current `src/embedding.py` and `src/retrieval.py` — do not rewrite the retrieval algorithm, only relocate and adapt it to the contract.
4. Write `ragframework/vectorstores/registry.py` exactly as specified in Section 3.
5. Write `ragframework/llms/google_genai.py` implementing `BaseLLMProvider.from_config`, porting logic from `src/generation.py`, reading `api_key` and `model` from the `config` dict.
6. Write `ragframework/llms/registry.py` exactly as specified in Section 4.
7. Rebuild `ragframework/core/generation.py` per Section 6 so it takes a `BaseChatModel` parameter instead of constructing one.
8. Update `ragframework/core/chunking.py` (and any CLI code) to read `chunk_size`/`chunk_overlap`/`top_k` from a `Settings` instance rather than local defaults.
9. Create `examples/configs/.env.faiss-gemini` with the example `.env` content from Section 5 (placeholder API key only).
10. Manually verify end-to-end: instantiate `Settings()`, call `get_vector_store(settings)` and `get_llm(settings)`, run a small `add_documents` → `similarity_search` round trip against a scratch FAISS index, and confirm `delete()` actually shrinks the result set on a subsequent search. Full automated contract tests come in Stage 12, but do not skip this manual check now — mistakes here are much cheaper to catch before the API layer is built on top of them.

---

## 9. Definition of done

- [ ] `ragframework/vectorstores/faiss_store.py` implements all five `BaseVectorStore` methods, including a working `delete()` via index rebuild.
- [ ] `ragframework/llms/google_genai.py` implements `BaseLLMProvider.from_config`, reading `api_key`/`model` only from the passed `config` dict.
- [ ] `ragframework/vectorstores/registry.py` and `ragframework/llms/registry.py` exist and raise a clear `ValueError` for unknown connector names.
- [ ] `ragframework/config.py` defines `Settings` exactly as in Section 5, including the `Literal` typing on `vector_store`/`llm_provider`.
- [ ] `chunk_size`, `chunk_overlap`, and `top_k` are sourced from `Settings` everywhere in the codebase — no competing local defaults remain.
- [ ] `core/generation.py` accepts a `BaseChatModel` and contains no import of `ChatGoogleGenerativeAI` or `google_genai.py`.
- [ ] A manual add → search → delete → search round trip against FAISS behaves correctly.
- [ ] No API key appears in any committed file.

## 10. Handoff to Stage 3

Stage 3 builds the FastAPI application and its routers on top of `get_vector_store(settings)` and `get_llm(settings)`. It assumes both registries are fully functional and that `Settings` can be constructed from environment variables without any additional wiring. The query and ingestion endpoints built in Stage 3 will call retrieval/generation synchronously and without caching, auth, or a job queue — those layer on in Stages 4, 6, and 7 respectively.
