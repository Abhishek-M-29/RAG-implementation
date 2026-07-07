# Contributing

## Adding a new connector

RAG Framework ships with FAISS (vector store) and Google Gemini (LLM), but the
architecture is designed so that **adding a new backend means writing one class
and registering it** — no core code changes.

### Adding a vector store connector

1. **Create the module** — `ragframework/vectorstores/my_store.py`

   ```python
   import logging
   from ragframework.vectorstores.base import BaseVectorStore

   logger = logging.getLogger(__name__)

   class MyStore(BaseVectorStore):
       @classmethod
       def from_config(cls, config: dict) -> "MyStore":
           ...

       def add_documents(self, documents: list) -> list[str]:
           ...

       def similarity_search(self, query: str, k: int = 5) -> list:
           ...

       def delete(self, ids: list[str]) -> None:
           ...

       def health_check(self) -> bool:
           ...
   ```

2. **Register it** — add to `ragframework/vectorstores/registry.py`:

   ```python
   from ragframework.vectorstores.my_store import MyStore

   VECTOR_STORE_REGISTRY = {
       "faiss": FaissStore,
       "my_store": MyStore,   # <-- new entry
   }
   ```

3. **Add optional dependencies** — if your connector needs extra packages
   (e.g., a database driver), add them as an extras group in `pyproject.toml`:

   ```toml
   [project.optional-dependencies]
   my-store = ["my-vendor-sdk>=1.0"]
   ```

   Users will install with `pip install ragframework[my-store]`.

4. **Document it** — create a per-connector guide in `docs/connectors/my-store.md`
   following the template structure used by `docs/connectors/faiss-gemini.md`:
   connector selection env vars → connector-specific config fields → known
   limitations → worked example.

### Adding an LLM provider

The same pattern applies for `ragframework/llms/`:

1. Create `ragframework/llms/my_provider.py` implementing `BaseLLMProvider`
2. Register in `ragframework/llms/registry.py`
3. Add extras group in `pyproject.toml` if vendor SDK dependencies are needed
4. Document the new provider

```python
from ragframework.llms.base import BaseLLMProvider

class MyProvider(BaseLLMProvider):
    @classmethod
    def from_config(cls, config: dict) -> BaseChatModel:
        ...
```

## Semantic versioning

This project follows [Semantic Versioning 2.0.0](https://semver.org/).

### What constitutes a breaking change (major version bump)

Any change to `BaseVectorStore` or `BaseLLMProvider` that alters:

- **Method signatures** — adding a required parameter, removing a parameter,
  changing a parameter type
- **Required methods** — adding a new `@abstractmethod` without a default
  implementation on the ABC itself
- **`from_config()` semantics** — changing what config keys are expected or
  how config values are interpreted

Even a change that appears to "just add an optional parameter" to an abstract
method needs scrutiny — a parameter added to an abstract method with no default
value breaks every existing concrete implementation.

### What is a minor version bump

- Adding a new non-breaking method to an ABC (with a default implementation)
- Adding a new connector (since it implements existing contracts unchanged)
- Adding new API endpoints, configuration options, or backend infrastructure

### What is a patch version bump

- Bug fixes
- Documentation improvements
- Internal refactoring that does not change public contracts or behavior

## Development setup

```bash
git clone https://github.com/Abhishek-M-29/RAG-implementation.git
cd RAG-implementation
pip install -e ".[dev]"
cp .env.example .env
# Edit .env — set LLM_CONFIG__API_KEY
```

## Running tests

```bash
# All tests
pytest tests/ -v

# Contract tests (parametrized over registered connectors)
pytest tests/contract/ -v

# Unit tests
pytest tests/unit/ -v

# Integration tests (some require Redis for async paths)
pytest tests/integration/ -v
```

## CI pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs:

1. `ruff` lint on `ragframework/`
2. `pyright` typecheck on `ragframework/`
3. `oxlint` lint on `frontend/`
4. `tsc` typecheck on `frontend/`
5. `pytest` on `tests/`
6. Docker image build (on push to `main`)
