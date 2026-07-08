"""Query endpoint — SSE streaming with retry, timeouts, and token-budget guard."""

import hashlib
import json
import logging
import re
import time
from collections.abc import Iterator
from contextlib import nullcontext

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableLambda

from ragframework.api.deps import limiter, require_scope
from ragframework.api.schemas import QueryRequest, SourceChunk
from ragframework.cache import get_cache, index_fingerprint
from ragframework.config import Settings, get_settings
from ragframework.core.generation import build_rag_chain
from ragframework.core.retrieval import query_hash
from ragframework.llms.registry import get_llm
from ragframework.memory import get_memory
from ragframework.observability.metrics import (
    record_cache_hit,
    record_cache_miss,
    record_error,
    record_latency,
    record_request,
    record_tokens,
)
from ragframework.observability.tracing import get_tracer
from ragframework.vectorstores.registry import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])

_query_rate_limit = get_settings().query_rate_limit


SSE_MEDIA_TYPE = "text/event-stream"


def _sse_token(content: str) -> str:
    return f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"


def _sse_metadata(sources: list[dict], cached: bool) -> str:
    return f"data: {json.dumps({'type': 'metadata', 'sources': sources, 'cached': cached})}\n\n"


def _sse_error(detail: str) -> str:
    return f"data: {json.dumps({'type': 'error', 'detail': detail})}\n\n"


def _normalize_query(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _query_cache_key(query: str, top_k: int, fingerprint: int) -> str:
    normalized = _normalize_query(query)
    raw = json.dumps({"q": normalized, "k": top_k, "f": fingerprint}, sort_keys=True)
    return "query:" + hashlib.sha256(raw.encode()).hexdigest()


def _check_token_budget(
    query: str,
    raw_docs: list,
    settings: Settings,
) -> None:
    context_chars = sum(len(d.page_content) for d in raw_docs)
    overhead_chars = 500
    total_chars = len(query) + context_chars + overhead_chars
    estimated_tokens = int(total_chars / 4)

    if estimated_tokens > settings.max_tokens_per_request:
        logger.warning(
            "Token budget exceeded",
            extra={
                "estimated_tokens": estimated_tokens,
                "max_tokens": settings.max_tokens_per_request,
                "context_chars": context_chars,
                "query_chars": len(query),
            },
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"Estimated token count ({estimated_tokens}) exceeds the "
                f"configured maximum ({settings.max_tokens_per_request}). "
                f"Try a shorter query or reduce top_k."
            ),
        )

    logger.debug(
        "Token budget check passed",
        extra={"estimated_tokens": estimated_tokens, "max_tokens": settings.max_tokens_per_request},
    )


def _cached_stream(data: dict) -> Iterator[str]:
    yield _sse_token(data.get("answer", ""))
    yield _sse_metadata(data.get("sources", []), cached=True)


def _generation_stream(
    chain,
    query: str,
    session_id: str,
    qhash: str,
    cache_key: str,
    cache,
    sources: list[dict],
    settings: Settings,
    llm,
) -> Iterator[str]:
    """Yield SSE events while streaming from the LLM chain, then cache."""
    answer_parts = []
    t0 = time.monotonic()
    tracer = get_tracer()

    try:
        if tracer is not None:
            with tracer.start_as_current_span("llm_generate") as span:
                span.set_attribute("query.hash", qhash)
                span.set_attribute("source_count", len(sources))
                for chunk in chain.stream(
                    {"input": query},
                    config={"configurable": {"session_id": session_id}},
                ):
                    token = chunk.get("answer", "")
                    if token:
                        yield _sse_token(token)
                        answer_parts.append(token)
        else:
            for chunk in chain.stream(
                {"input": query},
                config={"configurable": {"session_id": session_id}},
            ):
                token = chunk.get("answer", "")
                if token:
                    yield _sse_token(token)
                    answer_parts.append(token)
    except Exception:
        logger.exception("Generation stream failed", extra={"query_hash": qhash})
        record_error("generation", "stream_failure")
        yield _sse_error("Generation failed — see server logs for details.")
        return

    generation_latency = time.monotonic() - t0
    answer_text = "".join(answer_parts)

    cache.set(
        cache_key,
        json.dumps({"answer": answer_text, "sources": sources}),
        ttl_seconds=settings.query_cache_ttl,
    )

    model_name = getattr(llm, "model", "unknown")
    logger.info(
        "Generation completed",
        extra={
            "query_hash": qhash,
            "model": model_name,
            "source_count": len(sources),
            "latency": round(generation_latency, 3),
            "cached": False,
        },
    )

    record_latency("generation", generation_latency)

    answer_tokens = len(answer_text) // 4
    record_tokens("out", answer_tokens, model_name)

    yield _sse_metadata(sources, cached=False)


@router.post("/v1/query")
@limiter.limit(_query_rate_limit)
def query_endpoint(
    request: Request,
    body: QueryRequest,
    settings: Settings = Depends(get_settings),
    _auth: None = Depends(require_scope("query")),
):
    record_request("query")
    top_k = body.top_k if body.top_k is not None else settings.top_k
    qhash = query_hash(body.query)

    cache = get_cache(settings)
    if settings.async_ingestion and settings.redis_url:
        import redis
        _rc = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.object_storage_timeout_seconds,
            socket_timeout=settings.object_storage_timeout_seconds,
        )
        try:
            fingerprint = index_fingerprint(redis_client=_rc)
        finally:
            _rc.connection_pool.disconnect()
    else:
        fingerprint = index_fingerprint()
    ck = _query_cache_key(body.query, top_k, fingerprint)

    cached_raw = cache.get(ck)
    if cached_raw is not None:
        record_cache_hit()
        logger.info(
            "Query cache hit",
            extra={"query_hash": qhash, "top_k": top_k, "cached": True},
        )
        data = json.loads(cached_raw)
        return StreamingResponse(
            _cached_stream(data),
            media_type=SSE_MEDIA_TYPE,
        )

    record_cache_miss()
    logger.info(
        "Query cache miss",
        extra={"query_hash": qhash, "top_k": top_k, "cached": False},
    )

    vector_store = get_vector_store(settings)
    llm = get_llm(settings)

    tracer = get_tracer()
    t_embed = time.monotonic()
    ctx = tracer.start_as_current_span("embed_query") if tracer else nullcontext()
    with ctx as span:
        if span is not None and tracer:
            span.set_attribute("query.hash", qhash)
            span.set_attribute("top_k", top_k)
        raw_docs = vector_store.similarity_search(body.query, k=top_k)
    embed_latency = time.monotonic() - t_embed
    record_latency("embedding", embed_latency)

    _check_token_budget(body.query, raw_docs, settings)

    context_chars = sum(len(d.page_content) for d in raw_docs)
    input_estimate = (len(body.query) + context_chars + 500) // 4
    record_tokens("in", input_estimate, getattr(llm, "model", "unknown"))

    sources = []
    for doc in raw_docs:
        meta = doc.metadata or {}
        sources.append(
            SourceChunk(
                text=doc.page_content,
                source=meta.get("source", ""),
                page=meta.get("page"),
            ).model_dump()
        )

    memory = get_memory(settings)
    retriever = RunnableLambda(lambda _: raw_docs)

    ctx = tracer.start_as_current_span("build_prompt") if tracer else nullcontext()
    with ctx as span:
        if span is not None and tracer:
            span.set_attribute("query.hash", qhash)
            span.set_attribute("source_count", len(sources))
        chain = build_rag_chain(llm, retriever, get_session_history=memory.get_history)

    return StreamingResponse(
        _generation_stream(
            chain, body.query, body.session_id,
            qhash, ck, cache, sources, settings, llm,
        ),
        media_type=SSE_MEDIA_TYPE,
    )
