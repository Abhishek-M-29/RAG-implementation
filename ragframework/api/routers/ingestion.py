import logging
import os
import uuid

import redis
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File

from ragframework.api.deps import limiter, require_scope
from ragframework.api.schemas import (
    DeleteResponse,
    DocumentUploadResponse,
    DocumentListItem,
    DocumentListResponse,
    JobStatusResponse,
)
from ragframework.cache import bump_index_fingerprint
from ragframework.config import Settings, validate_config
from ragframework.core.chunking import chunk_text
from ragframework.core.ingestion import embed_and_index_chunks, load_and_extract_text_from_pdfs
from ragframework.observability.logging import request_id_var
from ragframework.observability.metrics import record_request, record_error, record_queue_depth
from ragframework.observability.tracing import get_tracer
from ragframework.vectorstores.registry import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

_settings = Settings()
_ingestion_rate_limit = _settings.ingestion_rate_limit


@router.post("/v1/documents", response_model=DocumentUploadResponse)
@limiter.limit(_ingestion_rate_limit)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    settings: Settings = Depends(lambda: Settings()),
    _auth: None = Depends(require_scope("ingest")),
):
    record_request("ingestion")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        record_error("ingestion", "invalid_file_type")
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = file.file.read()

    if len(content) > settings.max_upload_size_bytes:
        record_error("ingestion", "file_too_large")
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum upload size of {settings.max_upload_size_bytes} bytes",
        )

    if not content.startswith(b"%PDF"):
        record_error("ingestion", "invalid_file_signature")
        raise HTTPException(
            status_code=400,
            detail="File is not a valid PDF (invalid file signature)",
        )

    job_id = str(uuid.uuid4())
    request_id = request_id_var.get()

    os.makedirs(settings.object_storage_path, exist_ok=True)
    storage_path = os.path.join(
        settings.object_storage_path, f"{job_id}_{file.filename}",
    )
    with open(storage_path, "wb") as f:
        f.write(content)

    logger.info(
        "File received",
        extra={
            "file": file.filename, "size": len(content),
            "job_id": job_id, "request_id": request_id,
        },
    )

    if settings.async_ingestion:
        from rq import Queue
        from ragframework.workers.ingestion_worker import process_ingestion_job

        redis_client = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.object_storage_timeout_seconds,
            socket_timeout=settings.object_storage_timeout_seconds,
        )
        queue = Queue("ingestion", connection=redis_client)
        queue.enqueue(
            process_ingestion_job, storage_path, file.filename,
            request_id=request_id,
            job_id=job_id,
        )
        record_queue_depth(queue.count)
        redis_client.connection_pool.disconnect()

        logger.info(
            "Job enqueued",
            extra={
                "file": file.filename, "job_id": job_id,
                "request_id": request_id,
            },
        )
        return DocumentUploadResponse(job_id=job_id, status="queued")

    try:
        from ragframework.cache import get_cache

        tracer = get_tracer()

        if tracer is not None:
            with tracer.start_as_current_span("extract_text") as span:
                span.set_attribute("source", file.filename)
                span.set_attribute("request_id", request_id)
                docs = load_and_extract_text_from_pdfs([storage_path])
        else:
            docs = load_and_extract_text_from_pdfs([storage_path])

        if tracer is not None:
            with tracer.start_as_current_span("chunk") as span:
                span.set_attribute("source", file.filename)
                span.set_attribute("chunk_size", settings.chunk_size)
                span.set_attribute("chunk_overlap", settings.chunk_overlap)
                chunks = chunk_text(docs, settings.chunk_size, settings.chunk_overlap)
        else:
            chunks = chunk_text(docs, settings.chunk_size, settings.chunk_overlap)

        cache = get_cache(settings)
        vector_store = get_vector_store(settings)

        embed_and_index_chunks(
            chunks, settings, cache, vector_store, source_filename=file.filename,
        )

        logger.info(
            "Ingestion complete",
            extra={
                "file": file.filename, "chunk_count": len(chunks),
                "job_id": job_id, "request_id": request_id,
            },
        )
        return DocumentUploadResponse(job_id=job_id, status="queued")
    finally:
        if os.path.exists(storage_path):
            os.remove(storage_path)


@router.get("/v1/documents", response_model=DocumentListResponse)
@limiter.limit(_ingestion_rate_limit)
def list_documents(
    request: Request,
    settings: Settings = Depends(lambda: Settings()),
    _auth: None = Depends(require_scope("ingest")),
):
    return DocumentListResponse(documents=[])


@router.get("/v1/documents/{job_id}", response_model=JobStatusResponse)
@limiter.limit(_ingestion_rate_limit)
def get_job_status(
    request: Request,
    job_id: str,
    settings: Settings = Depends(lambda: Settings()),
    _auth: None = Depends(require_scope("ingest")),
):
    if not settings.async_ingestion:
        return JobStatusResponse(job_id=job_id, status="done")

    from rq.job import Job

    redis_client = redis.from_url(
        settings.redis_url,
        socket_connect_timeout=settings.object_storage_timeout_seconds,
        socket_timeout=settings.object_storage_timeout_seconds,
    )
    try:
        job = Job.fetch(job_id, connection=redis_client)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    finally:
        redis_client.connection_pool.disconnect()

    status_map = {
        "queued": "queued",
        "started": "processing",
        "deferred": "queued",
        "finished": "done",
        "failed": "failed",
        "scheduled": "queued",
    }
    status = status_map.get(job.get_status(), "queued")
    error = None
    if status == "failed":
        error = str(job.exc_info) if job.exc_info else "Unknown error"

    return JobStatusResponse(job_id=job_id, status=status, error=error)


@router.delete("/v1/documents/{id}", response_model=DeleteResponse)
@limiter.limit(_ingestion_rate_limit)
def delete_document(
    request: Request,
    id: str,
    settings: Settings = Depends(lambda: Settings()),
    _auth: None = Depends(require_scope("ingest")),
):
    vector_store = get_vector_store(settings)
    vector_store.delete([id])
    bump_index_fingerprint()
    logger.info("Document deleted", extra={"document_id": id})
    return DeleteResponse(status="deleted", id=id)
