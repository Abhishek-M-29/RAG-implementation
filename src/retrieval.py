from src.log_utils import get_logger

logger = get_logger(__name__)


def search_faiss_index(query_text, vectorstore, top_k=5):
    if not query_text or vectorstore is None:
        logger.error("Query text or vectorstore is None.")
        return []
    try:
        logger.info("Searching for top %d results...", top_k)
        docs = vectorstore.similarity_search(query_text, k=top_k)
        logger.info("Search completed. Found %d documents.", len(docs))
        return docs
    except Exception as e:
        logger.error("Error during search: %s", e)
        return []
