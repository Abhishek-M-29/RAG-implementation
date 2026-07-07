# Stage 1 of 14 — Foundation: Repository Restructure & Connector Contracts

**Source roadmap sections covered:** §5 (Repository layout), §6.1 (Vector store contract), §6.2 (LLM provider contract), §6.4 (Extension points — not built yet)
**Depends on:** nothing — this is the first build stage.
**Followed by:** Stage 2 — Connector Implementations (FAISS, Gemini) & Configuration.

---

## 1. Project context

**Project:** RAG-implementation → `ragframework`

We are turning a working local RAG proof-of-concept into a distributable framework where adopters bring their own vector database and their own LLM API key. The framework supplies RAG orchestration, backend service scaffolding, a reference frontend, and observability — all runnable on the adopter's own infrastructure. It is never operated as a hosted service by us.

**Connector scope for the whole build:** only two concrete connectors are ever implemented — **FAISS** (vector store) and **Google Gemini** (LLM). Everything else (pgvector, Qdrant, Pinecone, Weaviate, OpenAI, Anthropic, etc.) is a documented extension point, not something you build now.

**Guiding principles (apply throughout):**

1. Bring your own backend — never assume a specific vector DB or LLM vendor beyond the two shipped connectors.
2. Interface first, implementation second — every backend concern is an abstract contract before it's a concrete class.
3. Sane defaults, everything swappable.
4. Observability and reliability are built in from day one, not bolted on later.
5. The framework is not a hosted service — it ships scaffolding the adopter runs themselves.

**Baseline assumption:** the seven correctness fixes from the original codebase audit (silent PDF-load failures, global session ID, unlocked singletons, mismatched chunk-size defaults, committed index artifacts, dead code) are already fixed. This stage does not need to re-fix them, but it does need to **not reintroduce them** while moving files around — see Section 6 ("What not to do") below.

---

## 2. Why this stage exists

This is the foundation everything else depends on. Two things happen here, and only these two things:

1. The repository is restructured from the current flat POC layout into the framework's package layout.
2. The two abstract contracts — `BaseVectorStore` and `BaseLLMProvider` — are written. These contracts are the entire mechanism behind the "bring your own vector DB and API key" promise. Get them right once; every other piece of the framework (core RAG logic, the API layer, the CLI) only ever talks to these contracts, never to FAISS or Gemini directly.

**Do not port the actual FAISS or Gemini logic in this stage.** That's Stage 2. This stage only produces the *shape* everything else will be built against — empty/abstract contracts and an empty directory skeleton. Writing the concrete connectors before the contract exists (or writing them somewhere other than behind the contract) is exactly the mistake this two-stage split is designed to prevent.

---

## 3. Target repository structure

Build the full skeleton now, even though many files will just contain `pass`, a docstring, or nothing until later stages fill them in. This lets every subsequent stage document reference exact, stable file paths.

```
ragframework/
├── pyproject.toml
├── README.md
├── .gitignore                     # excludes index_store/, .env, __pycache__
├── ragframework/
│   ├── __init__.py
│   ├── config.py                  # Settings model — built in Stage 2
│   ├── core/
│   │   ├── ingestion.py           # unchanged from POC (correctness fixes already applied)
│   │   ├── chunking.py            # unchanged, dead code already removed
│   │   ├── retrieval.py           # unchanged — already connector-agnostic
│   │   └── generation.py          # will be rebuilt against the LLM connector interface in Stage 2
│   ├── vectorstores/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseVectorStore contract — THIS STAGE
│   │   ├── faiss_store.py         # concrete connector — Stage 2 (empty/stub for now)
│   │   └── registry.py            # factory / dispatch — Stage 2 (empty/stub for now)
│   ├── llms/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseLLMProvider contract — THIS STAGE
│   │   ├── google_genai.py        # concrete connector — Stage 2 (empty/stub for now)
│   │   └── registry.py            # factory / dispatch — Stage 2 (empty/stub for now)
│   ├── cache/                     # populated in Stage 4
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── memory_cache.py
│   │   └── redis_cache.py
│   ├── memory/                    # populated in Stage 4
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── in_memory.py
│   │   └── redis_memory.py
│   ├── observability/             # populated in Stages 5 and 9
│   │   ├── __init__.py
│   │   ├── logging.py
│   │   ├── tracing.py
│   │   └── metrics.py
│   ├── api/                       # populated in Stage 3 onward
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── deps.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── query.py
│   │   │   ├── ingestion.py
│   │   │   └── health.py
│   │   └── schemas.py
│   └── cli.py                     # index / query / clear / info / serve
├── frontend/                      # populated in Stage 10
│   ├── package.json
│   └── src/
├── docker/                        # populated in Stage 13
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── examples/
│   └── configs/                   # example .env per connector combination — Stage 2 onward
└── tests/                         # populated in Stage 12
    ├── contract/
    ├── unit/
    └── integration/
```

Notes on this layout:

- `core/` holds the parts of the RAG pipeline that don't change regardless of which connectors are plugged in: ingestion, chunking, retrieval orchestration, and the generation chain shape.
- `vectorstores/` and `llms/` are structurally identical: a `base.py` contract, one or more concrete implementations, and a `registry.py` that maps a config string to a class.
- Everything under `cache/`, `memory/`, `observability/`, `api/`, `frontend/`, `docker/`, and `tests/` is scaffolded as empty/stub now purely so the directory tree is stable — do not write their logic yet. Populating them out of order creates merge conflicts with the stage documents that own them.

---

## 4. The vector store contract

Create `ragframework/vectorstores/base.py`:

```python
# ragframework/vectorstores/base.py
from abc import ABC, abstractmethod
from langchain_core.documents import Document

class BaseVectorStore(ABC):
    """Contract every vector store connector must implement."""

    @classmethod
    @abstractmethod
    def from_config(cls, config: dict) -> "BaseVectorStore":
        """Construct and connect using adopter-supplied config (path, url, credentials)."""

    @abstractmethod
    def add_documents(self, documents: list[Document]) -> list[str]:
        """Embed and upsert documents. Returns the assigned chunk IDs."""

    @abstractmethod
    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        """Return the top-k most similar chunks to the query."""

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """Remove specific chunks by ID — required for re-indexing updated documents."""

    @abstractmethod
    def health_check(self) -> bool:
        """Used by the /ready endpoint (Stage 9) and by the contract tests (Stage 12)."""
```

Important design decisions baked into this contract — do not "simplify" them away:

- **`delete()` is mandatory**, even though FAISS itself has no native delete-by-id. Stage 2 shows how the FAISS connector satisfies this (by rebuilding the index from the remaining documents). The contract doesn't get a weaker version just because the first connector is inconvenient to implement it against — that would leak a FAISS limitation into the interface that every future connector (pgvector, Qdrant) would then be stuck accommodating.
- **`from_config()` is a classmethod, not `__init__`.** This is what lets the registry (Stage 2) construct any connector uniformly from a plain `dict` pulled out of `Settings`, without the registry needing to know each connector's constructor signature.
- **`health_check()` returns a plain `bool`.** Keep it cheap and synchronous-safe — it's called on the readiness path (Stage 9), which should be fast.

## 5. The LLM provider contract

Create `ragframework/llms/base.py`:

```python
# ragframework/llms/base.py
from abc import ABC, abstractmethod
from langchain_core.language_models.chat_models import BaseChatModel

class BaseLLMProvider(ABC):
    """Contract every LLM connector must implement."""

    @classmethod
    @abstractmethod
    def from_config(cls, config: dict) -> BaseChatModel:
        """Return a ready-to-use LangChain chat model using the adopter's own API key."""
```

Why this contract is deliberately thin: LangChain chat models already share a consistent interface (`.invoke()`, `.stream()`). The connector's only job is turning framework config into a correctly constructed chat model — it does not need to wrap generation logic itself. `core/generation.py` (rebuilt in Stage 2) works against `BaseChatModel` and never needs to know which provider produced it. Do not add extra abstract methods here "for symmetry" with `BaseVectorStore` — the two contracts are intentionally different shapes because they solve different problems.

---

## 6. What not to do in this stage

- **Do not write FAISS or Gemini logic yet.** `faiss_store.py` and `google_genai.py` should exist as near-empty stub files (or not exist at all if your team prefers to create them file-by-file in Stage 2). Writing connector logic against a contract you're still iterating on causes rework.
- **Do not let `core/` import anything from `vectorstores/faiss_store.py` or `llms/google_genai.py` directly**, even temporarily "to keep things working during the migration." If `core/retrieval.py` or `core/generation.py` needs a store or a model during this transitional stage, it should take one as a parameter typed against the abstract base, not import a concrete class.
- **Do not reintroduce the bugs the correctness-fixes pass already closed** while moving files. Specifically: don't recreate a module-level global session object in `core/`; don't recreate an unlocked lazy-singleton pattern for a model client; don't recommit `index_store/` artifacts (confirm `.gitignore` survives the restructure).
- **Do not delete `core/ingestion.py`, `core/chunking.py`, or `core/retrieval.py` logic.** They move location (from `src/` to `ragframework/core/`) but their internals are unchanged — they were already connector-agnostic or already fixed.
- **Do not add a third connector, a partial pgvector stub, or any "just in case" extension code.** Extension points are documented as comments in the registry (Stage 2), not scaffolded as dead code now.
- **Do not put concrete config values (paths, model names, API keys) into these contract files.** Contracts take a `dict` and know nothing about what's inside it.

---

## 7. Instructions to the implementing agent

Work in this exact order:

1. Create the new `ragframework/` package directory structure exactly as shown in Section 3, including all `__init__.py` files (empty is fine).
2. Move `src/ingestion.py` → `ragframework/core/ingestion.py`, `src/chunking.py` → `ragframework/core/chunking.py`, and the retrieval logic currently in the POC into `ragframework/core/retrieval.py`. Update imports only — do not change logic.
3. Do **not** move `src/generation.py` yet as-is; it will be rebuilt in Stage 2 against `BaseLLMProvider`. For this stage, you may leave a placeholder `ragframework/core/generation.py` with a docstring noting it will be completed in Stage 2.
4. Delete the old `main.py` CLI entry point's logic from the repo root; its replacement (`ragframework/cli.py`) is built out incrementally starting in later stages. A stub with `index`, `query`, `clear`, `info`, `serve` subcommands that currently raise `NotImplementedError` is acceptable here.
5. Confirm (or create) `.gitignore` excludes `index_store/`, `.env`, and `__pycache__`, and confirm no binary index artifacts are tracked by git after the move.
6. Write `ragframework/vectorstores/base.py` exactly as specified in Section 4.
7. Write `ragframework/llms/base.py` exactly as specified in Section 5.
8. Create empty stub files for `ragframework/vectorstores/faiss_store.py`, `ragframework/vectorstores/registry.py`, `ragframework/llms/google_genai.py`, `ragframework/llms/registry.py` — each with a one-line docstring pointing to Stage 2.
9. Create empty package directories (with `__init__.py` only) for `cache/`, `memory/`, `observability/`, `api/` (including `api/routers/`), matching Section 3.
10. Create empty `tests/contract/`, `tests/unit/`, `tests/integration/` directories.
11. Confirm the package imports cleanly: `python -c "import ragframework"` should succeed with no errors, and `python -c "from ragframework.vectorstores.base import BaseVectorStore; from ragframework.llms.base import BaseLLMProvider"` should succeed.
12. Confirm the two ABCs actually enforce abstractness: attempting to instantiate `BaseVectorStore()` or `BaseLLMProvider()` directly should raise `TypeError` (Python's ABC machinery does this automatically as long as `@abstractmethod` is used correctly — write a quick throwaway check, don't just assume).

---

## 8. Definition of done

- [ ] Repository matches the structure in Section 3, including empty stub/package files where noted.
- [ ] `ragframework/vectorstores/base.py` contains `BaseVectorStore` with all five members from Section 4, unmodified in signature.
- [ ] `ragframework/llms/base.py` contains `BaseLLMProvider` with the single classmethod from Section 5, unmodified in signature.
- [ ] `core/ingestion.py`, `core/chunking.py`, `core/retrieval.py` are moved with logic intact and no new imports of concrete connector classes.
- [ ] No binary index artifacts are tracked in git; `.gitignore` is correct.
- [ ] Dead code from the original `chunking.py` / `utils.py` (the unused save/load JSON helpers) is confirmed absent, not just unreferenced.
- [ ] `python -c "import ragframework"` succeeds.
- [ ] Instantiating either ABC directly raises `TypeError`.

## 9. Handoff to Stage 2

Stage 2 will fill in `vectorstores/faiss_store.py`, `vectorstores/registry.py`, `llms/google_genai.py`, `llms/registry.py`, rebuild `core/generation.py` against `BaseChatModel`, and introduce the `Settings` model in `ragframework/config.py`. It assumes the contracts from this stage are stable and will not be modified — if Stage 2 discovers the contract needs a change, that change must be made deliberately and documented, not patched around in the concrete connector.
