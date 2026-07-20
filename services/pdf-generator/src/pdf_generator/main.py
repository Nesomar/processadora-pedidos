"""Composition root do pdf-generator."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from pedidos_shared import Settings, SqsClient, get_logger

from pdf_generator.adapters.worker_loop import run_consumer
from pdf_generator.config import get_settings
from pdf_generator.handlers.gerar_pdf import handle as handle_gerar_pdf

logger = get_logger("pdf_generator")
HEALTH_PORT = 8082


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
    if settings.pdf_request_queue_url is None:
        raise ValueError("PDF_REQUEST_QUEUE_URL nao configurada")
    sqs = SqsClient(settings)
    threading.Thread(
        target=run_consumer,
        args=(sqs, settings.pdf_request_queue_url, handle_gerar_pdf, settings),
        daemon=True,
        name="pdf_request",
    ).start()
    logger.info("consumidor 'pdf_request' iniciado")


def main() -> None:
    settings = get_settings()
    _start_health_server()
    _start_consumer(settings)
    logger.info("pdf-generator pronto")
    threading.Event().wait()


if __name__ == "__main__":
    main()
