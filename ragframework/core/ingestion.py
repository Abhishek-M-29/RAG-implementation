import hashlib
import logging
import os
import time
import uuid

from langchain_community.document_loaders import PyPDFLoader
from pypdf import PdfReader

from ragframework.cache import bump_index_fingerprint
from ragframework.observability.metrics import record_cache_hit, record_cache_miss, record_latency
from ragframework.observability.tracing import get_tracer

logger = logging.getLogger(__name__)


def get_pdf_paths_from_directory(directory_path):
    pdf_files = []
    try:
        for filename in os.listdir(directory_path):
            if filename.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(directory_path, filename))
    except FileNotFoundError:
        logger.warning("Directory not found at %s — creating it", directory_path)
        os.makedirs(directory_path, exist_ok=True)
    return pdf_files


MAX_PDF_PAGES = 10_000


def _validate_pdf_safety(file_path: str) -> None:
    """Guard against malformed PDFs and decompression-bomb attacks.

    Checks page count against a sane upper bound *before* handing the
    file to PyPDFLoader, which would otherwise attempt to decompress the
    full stream in memory.  This is not a malware scan — adopters with
    stricter security requirements should integrate a dedicated scanner
    (e.g. ClamAV) at a reverse-proxy layer before the file reaches
    this framework.
    """
    try:
        reader = PdfReader(file_path)
        num_pages = len(reader.pages)
    except Exception as exc:
        raise ValueError(f"Malformed PDF — unable to read: {exc}") from exc

    if num_pages > MAX_PDF_PAGES:
        raise ValueError(
            f"PDF has {num_pages} pages (max allowed: {MAX_PDF_PAGES}) — "
            "possible decompression bomb. Rejected for safety."
        )


def load_and_extract_text_from_pdfs(pdf_file_paths):
    extracted_docs = []
    if not pdf_file_paths:
        logger.warning("No PDF file paths provided.")
        return extracted_docs

    for pdf_path in pdf_file_paths:
        try:
            fname = os.path.basename(pdf_path)
            fsize = os.path.getsize(pdf_path)
            logger.info("Processing file", extra={"file": fname, "size": fsize})
            _validate_pdf_safety(pdf_path)
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            extracted_docs.extend(docs)
            logger.info(
                "Extracted %d pages from %s", len(docs), fname,
                extra={"file": fname, "pages": len(docs)},
            )
        except Exception as e:
            logger.error(
                "Failed to process PDF %s: %s", pdf_path, e,
                extra={"file": os.path.basename(pdf_path), "error": str(e)},
            )
    return extracted_docs


def _embedding_cache_key(chunk_text_value: str, model_name: str) -> str:
    raw = hashlib.sha256(f"{chunk_text_value}:{model_name}".encode()).hexdigest()
    return "emb:" + raw


def embed_and_index_chunks(chunks, settings, cache, vector_store, source_filename):
    import json

    from langchain_huggingface import HuggingFaceEmbeddings

    embedding_model = settings.vector_store_config.get("embedding_model")
    if embedding_model is None:
        embedding_model = HuggingFaceEmbeddings(model_name=settings.embedding_model)

    texts = []
    metadatas = []
    embedded_vectors: list[list[float] | None] = []
    uncached_indices: list[int] = []

    for chunk in chunks:
        if "id" not in chunk.metadata:
            chunk.metadata["id"] = str(uuid.uuid4())
        if "source" not in chunk.metadata:
            chunk.metadata["source"] = source_filename

        ck = _embedding_cache_key(chunk.page_content, settings.embedding_model)
        cached = cache.get(ck)
        if cached is not None:
            record_cache_hit()
            embedded_vectors.append(json.loads(cached))
        else:
            record_cache_miss()
            embedded_vectors.append(None)
            uncached_indices.append(len(texts))

        texts.append(chunk.page_content)
        metadatas.append(dict(chunk.metadata))

    embedding_time = 0.0
    if uncached_indices:
        texts_to_embed = [texts[i] for i in uncached_indices]

        tracer = get_tracer()
        t0 = time.monotonic()
        if tracer is not None:
            with tracer.start_as_current_span("embed_batch") as span:
                span.set_attribute("chunk_count", len(texts_to_embed))
                span.set_attribute("source", source_filename)
                new_vectors = embedding_model.embed_documents(texts_to_embed)
        else:
            new_vectors = embedding_model.embed_documents(texts_to_embed)
        embedding_time = time.monotonic() - t0
        record_latency("embedding", embedding_time)

        for i, vec in zip(uncached_indices, new_vectors):
            embedded_vectors[i] = vec
            ck = _embedding_cache_key(texts[i], settings.embedding_model)
            cache.set(ck, json.dumps(vec), ttl_seconds=None)

    tracer = get_tracer()
    if tracer is not None:
        with tracer.start_as_current_span("upsert") as span:
            span.set_attribute("chunk_count", len(chunks))
            span.set_attribute("source", source_filename)
            vector_store.add_embedded_documents(
                list(zip(texts, embedded_vectors)), metadatas,
            )
    else:
        vector_store.add_embedded_documents(
            list(zip(texts, embedded_vectors)), metadatas,
        )

    bump_index_fingerprint()
    logger.info(
        "Indexed %d chunks from %s",
        len(chunks), source_filename,
        extra={
            "chunk_count": len(chunks),
            "source": source_filename,
            "cached_count": len(chunks) - len(uncached_indices),
            "computed_count": len(uncached_indices),
            "embedding_time": round(embedding_time, 3),
        },
    )
