"""Composition root do file-consumer."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from pedidos_shared import Settings, SqsClient, get_logger

from file_consumer.adapters.worker_loop import run_consumer
from file_consumer.config import get_settings
from file_consumer.handlers.processar_notificacao import handle as handle_processar_notificacao

logger = get_logger("file_consumer")
HEALTH_PORT = 8083


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
    if settings.s3_notifications_queue_url is None:
        raise ValueError("S3_NOTIFICATIONS_QUEUE_URL nao configurada")
    sqs = SqsClient(settings)
    threading.Thread(
        target=run_consumer,
        args=(sqs, settings.s3_notifications_queue_url, handle_processar_notificacao, settings),
        daemon=True,
        name="s3_notifications",
    ).start()
    logger.info("consumidor 's3_notifications' iniciado")


def main() -> None:
    settings = get_settings()
    _start_health_server()
    _start_consumer(settings)
    logger.info("file-consumer pronto")
    threading.Event().wait()


if __name__ == "__main__":
    main()
