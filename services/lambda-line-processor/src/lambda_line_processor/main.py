"""Composition root do lambda-line-processor."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from pedidos_shared import Settings, SqsClient, get_logger

from lambda_line_processor.adapters.worker_loop import run_consumer
from lambda_line_processor.config import get_settings
from lambda_line_processor.handlers.processar_linha import handle as handle_processar_linha

logger = get_logger("lambda_line_processor")
HEALTH_PORT = 8084


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"status": "ok"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


def _start_health_server() -> None:
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def _start_consumer(settings: Settings) -> None:
    if settings.pedido_lines_queue_url is None:
        raise ValueError("PEDIDO_LINES_QUEUE_URL nao configurada")
    sqs = SqsClient(settings)
    threading.Thread(
        target=run_consumer,
        args=(sqs, settings.pedido_lines_queue_url, handle_processar_linha, settings),
        daemon=True,
        name="pedido_lines",
    ).start()
    logger.info("consumidor 'pedido_lines' iniciado")


def main() -> None:
    settings = get_settings()
    _start_health_server()
    _start_consumer(settings)
    logger.info("lambda-line-processor pronto")
    threading.Event().wait()


if __name__ == "__main__":
    main()
