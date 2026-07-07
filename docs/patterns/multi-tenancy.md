# Multi-Tenancy Pattern

**Status:** Documented pattern — not implemented by default.

If you need to serve multiple isolated tenants from a single deployment, add a
`tenant_id` to every request and enforce it as a mandatory metadata filter at
the vector store connector level.

## Extension point

The filter would be threaded through `BaseVectorStore.similarity_search()`
(`ragframework/vectorstores/base.py:18`). Currently the signature is:

```python
def similarity_search(self, query: str, k: int = 5) -> list[Document]:
```

A tenant-aware override would add a `filter` dict:

```python
def similarity_search(self, query: str, k: int = 5, filter: dict | None = None) -> list[Document]:
```

The call site in the RAG chain (e.g., `ragframework/api/routers/query.py`)
would extract `tenant_id` from the authenticated request context and pass it
as a metadata filter. The FAISS connector already delegates to LangChain's
`similarity_search`, which natively accepts a `filter` parameter.

## What this doc does not do

- No default `tenant_id` extraction middleware is added — most deployments
  don't need it, and every connector would silently carry the overhead.
- No schema migration — adopters implement tenant-awareness in their own
  connector subclass.
- No routing logic — the adopter decides how `tenant_id` reaches the request
  (JWT claim, header, path prefix, etc.).
