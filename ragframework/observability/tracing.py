import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = logging.getLogger(__name__)

_tracer: trace.Tracer | None = None


def setup_tracing(
    service_name: str = "ragframework",
    otel_exporter_endpoint: str | None = None,
) -> trace.Tracer:
    global _tracer

    provider = TracerProvider()

    if otel_exporter_endpoint:
        exporter = OTLPSpanExporter(endpoint=otel_exporter_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info(
            "OTel tracing enabled",
            extra={"endpoint": otel_exporter_endpoint},
        )
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("OTel tracing configured with console exporter (no endpoint set)")

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    return _tracer


def get_tracer() -> trace.Tracer | None:
    return _tracer
