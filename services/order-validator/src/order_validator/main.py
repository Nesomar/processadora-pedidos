"""Composition root do order-validator."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
from pedidos_shared import Settings, SqsClient, get_logger

from order_validator.adapters.catalogo_produtos import CatalogoCache
from order_validator.adapters.worker_loop import Handler, run_consumer
from order_validator.config import get_settings
from order_validator.handlers.validar_pedido import handle as handle_validar_pedido

logger = get_logger("order_validator")
HEALTH_PORT = 8081


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


def _handler(settings: Settings, client: httpx.Client, cache: CatalogoCache) -> Handler:
    def _run(envelope, inner_settings):
        handle_validar_pedido(envelope, inner_settings, client=client, cache=cache)

    return _run


def _start_consumer(settings: Settings) -> None:
    if settings.validar_pedido_queue_url is None:
        raise ValueError("VALIDAR_PEDIDO_QUEUE_URL nao configurada")
    sqs = SqsClient(settings)
    client = httpx.Client()
    cache = CatalogoCache()
    threading.Thread(
        target=run_consumer,
        args=(sqs, settings.validar_pedido_queue_url, _handler(settings, client, cache), settings),
        daemon=True,
        name="validar_pedido",
    ).start()
    logger.info("consumidor 'validar_pedido' iniciado")


def main() -> None:
    settings = get_settings()
    _start_health_server()
    _start_consumer(settings)
    logger.info("order-validator pronto")
    threading.Event().wait()


if __name__ == "__main__":
    main()
