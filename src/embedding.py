import os
import shutil
import threading
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from src.log_utils import get_logger

logger = get_logger(__name__)

_embedding_model = None
_embedding_lock = threading.Lock()


def _get_embedding_model(model_name="sentence-transformers/all-MiniLM-L6-v2"):
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                _embedding_model = HuggingFaceEmbeddings(model_name=model_name)
    return _embedding_model


def build_and_save_faiss_index(documents, index_path="index_store/faiss_index"):
    if not documents:
        return None
    try:
        model = _get_embedding_model()
        vectorstore = FAISS.from_documents(documents, model)
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        vectorstore.save_local(index_path)
        logger.info("Built and saved FAISS index to %s", index_path)
        return vectorstore
    except Exception as e:
        logger.error("Error building FAISS index: %s", e)
        return None


def add_to_faiss_index(documents, index_path="index_store/faiss_index"):
    if not documents:
        return None
    existing = load_faiss_index(index_path)
    if existing is None:
        return build_and_save_faiss_index(documents, index_path)
    try:
        existing.add_documents(documents)
        existing.save_local(index_path)
        logger.info("Added %d documents to existing index", len(documents))
        return existing
    except Exception as e:
        logger.error("Error during add_documents: %s", e)
        logger.info("Falling back to merge approach...")
        try:
            all_docs = []
            for doc_id in existing.index_to_docstore_id.values():
                doc = existing.docstore.search(doc_id)
                if doc is not None:
                    all_docs.append(doc)
            all_docs.extend(documents)
            logger.info("Merging %d total documents into new index...", len(all_docs))
            return build_and_save_faiss_index(all_docs, index_path)
        except Exception as e2:
            logger.error("Merge also failed: %s", e2)
            return None


def load_faiss_index(index_path="index_store/faiss_index", trusted_source=True):
    if not os.path.exists(index_path):
        return None
    try:
        model = _get_embedding_model()
        if not trusted_source:
            logger.warning(
                "Attempting to load FAISS index from an untrusted source. "
                "The index pickle file is deserialized with pickle, which can be unsafe."
            )
        vectorstore = FAISS.load_local(index_path, model, allow_dangerous_deserialization=trusted_source)
        logger.info("Loaded FAISS index from %s", index_path)
        return vectorstore
    except Exception as e:
        logger.error("Error loading FAISS index: %s", e)
        return None


def clear_faiss_index(index_path="index_store/faiss_index"):
    if os.path.exists(index_path):
        shutil.rmtree(index_path)
        logger.info("Index cleared from %s", index_path)
    else:
        logger.warning("No index found at %s", index_path)
