import logging
import os

import redis

from ragframework.cache import get_cache, bump_index_fingerprint
from ragframework.config import Settings
from ragframework.core.chunking import chunk_text
from ragframework.core.ingestion import (
    embed_and_index_chunks,
    load_and_extract_text_from_pdfs,
)
from ragframework.observability.metrics import record_error, record_request
from ragframework.observability.tracing import get_tracer
from ragframework.vectorstores.registry import get_vector_store

logger = logging.getLogger(__name__)


def process_ingestion_job(file_path: str, source_filename: str, request_id: str = ""):
    """RQ worker task — runs in a separate process.

    Reads Settings() from environment so the worker uses the same connector
    registry (get_vector_store, get_cache) as the API process.  Never
    constructs a FaissStore or GoogleGenAIProvider directly.
    """
    settings = Settings()
    extra = {"file": source_filename, "request_id": request_id}

    logger.info("Worker picked up ingestion job", extra=extra)
    record_request("ingestion")

    tracer = get_tracer()

    try:
        if tracer is not None:
            with tracer.start_as_current_span("extract_text") as span:
                span.set_attribute("source", source_filename)
                span.set_attribute("request_id", request_id)
                docs = load_and_extract_text_from_pdfs([file_path])
        else:
            docs = load_and_extract_text_from_pdfs([file_path])

        if not docs:
            raise RuntimeError(
                f"No text could be extracted from {source_filename} — "
                "the file may be empty, corrupt, or not a valid PDF"
            )

        if tracer is not None:
            with tracer.start_as_current_span("chunk") as span:
                span.set_attribute("source", source_filename)
                span.set_attribute("chunk_size", settings.chunk_size)
                span.set_attribute("chunk_overlap", settings.chunk_overlap)
                chunks = chunk_text(docs, settings.chunk_size, settings.chunk_overlap)
        else:
            chunks = chunk_text(docs, settings.chunk_size, settings.chunk_overlap)

        cache = get_cache(settings)
        vector_store = get_vector_store(settings)

        embed_and_index_chunks(
            chunks, settings, cache, vector_store, source_filename=source_filename,
        )

        redis_client = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.object_storage_timeout_seconds,
            socket_timeout=settings.object_storage_timeout_seconds,
        )
        bump_index_fingerprint(redis_client=redis_client)
        redis_client.connection_pool.disconnect()

        logger.info(
            "Ingestion job completed successfully",
            extra={**extra, "chunk_count": len(chunks)},
        )
    except Exception:
        logger.exception("Ingestion job failed", extra=extra)
        record_error("ingestion", "job_failure")
        raise
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug("Cleaned up temp file", extra={"file": file_path})
