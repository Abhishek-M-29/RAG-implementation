import hashlib
import logging
import re
import time

logger = logging.getLogger(__name__)


def query_hash(query: str) -> str:
    normalized = re.sub(r"\s+", " ", query.strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()


def search_faiss_index(query_text, vectorstore, top_k=5):
    if not query_text or vectorstore is None:
        logger.warning("Query text or vectorstore is None.")
        return []

    qhash = query_hash(query_text)
    try:
        logger.info(
            "Searching for top %d results", top_k,
            extra={"query_hash": qhash, "top_k": top_k},
        )
        t0 = time.monotonic()
        docs = vectorstore.similarity_search(query_text, k=top_k)
        latency = time.monotonic() - t0
        logger.info(
            "Search completed. Found %d documents.",
            len(docs),
            extra={
                "query_hash": qhash,
                "top_k": top_k,
                "result_count": len(docs),
                "latency": round(latency, 3),
            },
        )
        return docs
    except Exception as e:
        logger.error(
            "Error during search: %s", e,
            extra={"query_hash": qhash, "error": str(e)},
        )
        return []
