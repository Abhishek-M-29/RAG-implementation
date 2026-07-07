import logging
import os

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from ragframework.vectorstores.base import BaseVectorStore

logger = logging.getLogger(__name__)


class FaissStore(BaseVectorStore):
    """FAISS local-file vector store connector.

    .. caution::
       This connector loads serialised FAISS indexes with
       ``allow_dangerous_deserialization=True``.  This is an **accepted,
       documented constraint of the FAISS connector specifically**:
       FAISS uses pickle under the hood, and there is no safe-load path
       for indexes persisted by a prior session.

       Future networked connectors (pgvector, Qdrant, etc.) do not share
       this risk category — they query a remote index over a wire
       protocol and never deserialise user-supplied pickles.  The
       presence of this flag on the FAISS connector alone is not a
       reason to avoid it; it is a reason to prefer a networked vector
       store for deployments with stricter security requirements.
    """

    def __init__(self, index_path: str, embedding_model):
        self._index_path = index_path
        self._embedding = embedding_model
        self._store: FAISS | None = None

    @classmethod
    def from_config(cls, config: dict) -> "FaissStore":
        index_path = config.get("index_path", "index_store/faiss_index")
        embedding_model = config.get("embedding_model", None)
        if embedding_model is None:
            model_name = config.get("model_name", "sentence-transformers/all-MiniLM-L6-v2")
            embedding_model = HuggingFaceEmbeddings(model_name=model_name)
        store = cls(index_path, embedding_model=embedding_model)
        store._load_or_init()
        return store

    def add_documents(self, documents: list[Document]) -> list[str]:
        if not documents:
            return []

        if self._store is None:
            self._store = FAISS.from_documents(documents, self._embedding)
        else:
            self._store.add_documents(documents)

        self._persist()
        ids = [doc.metadata.get("id", "") for doc in documents]
        logger.info(
            "Added %d documents to FAISS index at %s",
            len(documents), self._index_path,
            extra={"doc_count": len(documents), "index_path": self._index_path},
        )
        return ids

    def add_embedded_documents(
        self,
        text_embeddings: list[tuple[str, list[float]]],
        metadatas: list[dict],
    ) -> list[str]:
        if not text_embeddings:
            return []

        texts = [t for t, _ in text_embeddings]
        vectors = [v for _, v in text_embeddings]

        if self._store is None:
            self._store = FAISS.from_embeddings(
                list(zip(texts, vectors)),
                self._embedding,
                metadatas=metadatas,
            )
        else:
            self._store.add_embeddings(
                list(zip(texts, vectors)),
                metadatas=metadatas,
            )

        self._persist()
        ids = [m.get("id", "") for m in metadatas]
        logger.info(
            "Added %d embedded documents to FAISS index at %s",
            len(text_embeddings), self._index_path,
            extra={"doc_count": len(text_embeddings), "index_path": self._index_path},
        )
        return ids

    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        if self._store is None:
            return []
        return self._store.similarity_search(query, k=k)

    def delete(self, ids: list[str]) -> None:
        if self._store is None or not ids:
            return

        id_set = set(ids)
        existing = list(self._store.docstore._dict.values())  # type: ignore[attr-defined]
        remaining = [d for d in existing if d.metadata.get("id") not in id_set]

        if len(remaining) == len(existing):
            logger.warning("None of the provided IDs were found in the index")
            return

        if not remaining:
            self._store = None
            if os.path.exists(self._index_path):
                import shutil
                shutil.rmtree(self._index_path)
            logger.info("Deleted all documents — index cleared")
            return

        self._store = FAISS.from_documents(remaining, self._embedding)
        self._persist()
        logger.info(
            "Deleted %d documents (rebuild complete), %d remain",
            len(ids), len(remaining),
            extra={"deleted_count": len(ids), "remaining_count": len(remaining)},
        )

    def health_check(self) -> bool:
        if self._store is None:
            try:
                self._load_or_init()
            except Exception:
                pass
            if self._store is None:
                return True
        try:
            _ = self._store.index.ntotal
            return True
        except Exception:
            return False

    def _load_or_init(self) -> None:
        if os.path.exists(self._index_path):
            self._store = FAISS.load_local(
                self._index_path,
                self._embedding,
                allow_dangerous_deserialization=True,
            )
            logger.info("Loaded existing FAISS index from %s", self._index_path)
        else:
            self._store = None
            logger.info("No existing index at %s – will create on first add", self._index_path)

    def _persist(self) -> None:
        if self._store is not None:
            os.makedirs(os.path.dirname(self._index_path), exist_ok=True)
            self._store.save_local(self._index_path)
