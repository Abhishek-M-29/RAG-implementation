"""CLI entry point."""
import argparse

from ragframework.config import Settings, validate_config
from ragframework.observability.logging import configure_logging
from ragframework.observability.tracing import setup_tracing
from ragframework.observability.metrics import setup_metrics
from ragframework.vectorstores.registry import get_vector_store
from ragframework.llms.registry import get_llm


def build_parser():
    parser = argparse.ArgumentParser(
        description="RAG Framework CLI — Index and query documents using a local knowledge base"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    index_parser = subparsers.add_parser("index", help="Index documents into the knowledge base")
    index_parser.add_argument("-d", "--dir", action="append", dest="dirs", help="Directory containing PDF files")
    index_parser.add_argument("-f", "--file", action="append", dest="files", help="Specific PDF file(s)")
    index_parser.add_argument("-a", "--append", action="store_true", help="Append to existing index instead of replacing")
    index_parser.add_argument("--chunk-size", type=int, default=1000, help="Characters per chunk")
    index_parser.add_argument("--chunk-overlap", type=int, default=100, help="Overlap between chunks")
    subparsers.add_parser("query", help="Query the knowledge base interactively")
    subparsers.add_parser("clear", help="Clear/delete the index")
    subparsers.add_parser("info", help="Show information about the current index")
    subparsers.add_parser("serve", help="Start the API server")
    worker_parser = subparsers.add_parser("worker", help="Start the RQ ingestion worker")
    worker_parser.add_argument(
        "--queues", default="ingestion",
        help="Comma-separated queue names to listen on (default: ingestion)",
    )
    return parser


def main():
    settings = Settings()
    configure_logging(settings.log_level)
    validate_config(settings)
    setup_tracing(
        service_name="ragframework",
        otel_exporter_endpoint=settings.otel_exporter_endpoint,
    )
    setup_metrics(
        service_name="ragframework",
        otel_exporter_endpoint=settings.otel_exporter_endpoint,
    )
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        uvicorn.run(
            "ragframework.api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
        )
        return
    if args.command == "worker":
        if not settings.redis_url:
            raise ValueError(
                "REDIS_URL must be set to run the async ingestion worker. "
                "Set it in your .env or configure it via environment variables."
            )
        from rq import Worker
        import redis as redis_module
        redis_conn = redis_module.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.object_storage_timeout_seconds,
            socket_timeout=settings.object_storage_timeout_seconds,
        )
        queues = [q.strip() for q in args.queues.split(",")]
        worker = Worker(queues, connection=redis_conn)
        worker.work()
        return
    actions = {
        "index": "Indexing not yet implemented — built out in Stage 2+.",
        "query": "Querying not yet implemented — built out in Stage 2+.",
        "clear": "Clear not yet implemented — built out in Stage 2+.",
        "info": "Info not yet implemented — built out in Stage 2+.",
    }
    msg = actions.get(args.command, "Unknown command.")
    raise NotImplementedError(msg)


if __name__ == "__main__":
    main()
