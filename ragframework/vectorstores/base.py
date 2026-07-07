from abc import ABC, abstractmethod

from langchain_core.documents import Document


class BaseVectorStore(ABC):
    """Contract every vector store connector must implement.

    .. admonition:: Least-privilege credentials (networked connectors)

       When implementing a connector that talks to a remote database
       (pgvector, Qdrant, Elasticsearch, …), **do not use admin or root
       credentials**.  Create a database user scoped to the minimum set
       of operations the connector needs:

       * Read/write access to the specific table or collection used for
         vector storage.
       * No DDL privileges (CREATE TABLE, DROP INDEX, …) unless the
         connector explicitly manages schema migration.
       * No access to other databases or tenants.

       The adopter supplies credentials via the connector's ``config``
       dict (mapped from ``VECTOR_STORE_CONFIG__*`` env vars).  They
       should never be hard-coded, logged, or echoed in API responses.
       This pattern is established now so every future networked
       connector inherits the same security expectation.
    """

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
    def list_documents(self) -> dict[str, int]:
        """Return a mapping of source filename → chunk count for all indexed documents."""

    @abstractmethod
    def health_check(self) -> bool:
        """Used by the /ready endpoint (Stage 9) and by the contract tests (Stage 12)."""
