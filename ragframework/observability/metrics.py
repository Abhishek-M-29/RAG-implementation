import logging
import threading

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader

logger = logging.getLogger(__name__)

_meter: metrics.Meter | None = None

_request_counter: metrics.Counter | None = None
_latency_histogram: metrics.Histogram | None = None
_cache_hit_counter: metrics.Counter | None = None
_cache_miss_counter: metrics.Counter | None = None
_tokens_counter: metrics.Counter | None = None
_error_counter: metrics.Counter | None = None
_retry_attempt_counter: metrics.Counter | None = None
_queue_depth_gauge: metrics.UpDownCounter | None = None


def setup_metrics(
    service_name: str = "ragframework",
    otel_exporter_endpoint: str | None = None,
) -> metrics.Meter:
    global _meter, _request_counter, _latency_histogram
    global _cache_hit_counter, _cache_miss_counter
    global _tokens_counter, _error_counter, _retry_attempt_counter, _queue_depth_gauge

    if otel_exporter_endpoint:
        exporter = OTLPMetricExporter(endpoint=otel_exporter_endpoint)
        reader = PeriodicExportingMetricReader(exporter)
        provider = MeterProvider(metric_readers=[reader])
        logger.info(
            "OTel metrics enabled",
            extra={"endpoint": otel_exporter_endpoint},
        )
    else:
        reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
        provider = MeterProvider(metric_readers=[reader])
        logger.info("OTel metrics configured with console exporter (no endpoint set)")

    metrics.set_meter_provider(provider)
    _meter = metrics.get_meter(service_name)
    assert _meter is not None

    _request_counter = _meter.create_counter(
        "rag.request.total",
        description="Total request count",
        unit="1",
    )
    _latency_histogram = _meter.create_histogram(
        "rag.latency.seconds",
        description="Request latency by stage",
        unit="s",
    )
    _cache_hit_counter = _meter.create_counter(
        "rag.cache.hit_total",
        description="Cache hit count",
        unit="1",
    )
    _cache_miss_counter = _meter.create_counter(
        "rag.cache.miss_total",
        description="Cache miss count",
        unit="1",
    )
    _tokens_counter = _meter.create_counter(
        "rag.tokens.total",
        description="Token count (in/out) by LLM provider",
        unit="1",
    )
    _error_counter = _meter.create_counter(
        "rag.errors.total",
        description="Error count by stage",
        unit="1",
    )
    _retry_attempt_counter = _meter.create_counter(
        "rag.retry.attempts",
        description="Retry attempt count",
        unit="1",
    )
    _queue_depth_gauge = _meter.create_up_down_counter(
        "rag.ingestion.queue_depth",
        description="Current ingestion queue depth",
        unit="1",
    )

    return _meter


def record_request(stage: str) -> None:
    if _request_counter is not None:
        _request_counter.add(1, {"stage": stage})


def record_latency(stage: str, seconds: float) -> None:
    if _latency_histogram is not None:
        _latency_histogram.record(seconds, {"stage": stage})


def record_cache_hit() -> None:
    if _cache_hit_counter is not None:
        _cache_hit_counter.add(1)


def record_cache_miss() -> None:
    if _cache_miss_counter is not None:
        _cache_miss_counter.add(1)


def record_tokens(direction: str, count: int, model: str) -> None:
    if _tokens_counter is not None:
        _tokens_counter.add(count, {"direction": direction, "model": model})


def record_error(stage: str, error_type: str = "unknown") -> None:
    if _error_counter is not None:
        _error_counter.add(1, {"stage": stage, "error.type": error_type})


def record_retry_attempt(stage: str) -> None:
    if _retry_attempt_counter is not None:
        _retry_attempt_counter.add(1, {"stage": stage})


_last_queue_depth: int = 0
_queue_depth_lock = threading.Lock()


def _get_last_queue_depth() -> int:
    global _last_queue_depth
    return _last_queue_depth


def _set_last_queue_depth(depth: int) -> None:
    global _last_queue_depth
    _last_queue_depth = depth


def record_queue_depth(depth: int) -> None:
    if _queue_depth_gauge is not None:
        with _queue_depth_lock:
            delta = depth - _get_last_queue_depth()
            _set_last_queue_depth(depth)
        _queue_depth_gauge.add(delta)
