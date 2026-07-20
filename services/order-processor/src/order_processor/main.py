"""Composition root: sobe as threads de consumo das filas + thread /health (constitution IV)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from pedidos_shared import Settings, SqsClient, get_logger

from order_processor.adapters.worker_loop import Handler, run_consumer
from order_processor.config import get_settings
from order_processor.handlers.cancelar_pedido import handle as handle_cancelar_pedido
from order_processor.handlers.editar_pedido import handle as handle_editar_pedido
from order_processor.handlers.pdf_response import handle as handle_pdf_response
from order_processor.handlers.solicitar_pedido import handle as handle_solicitar_pedido
from order_processor.handlers.validar_pedido_response import (
    handle as handle_validar_pedido_response,
)

logger = get_logger("order_processor")

HEALTH_PORT = 8080


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 — nome exigido pela stdlib
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"status": "ok"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — assinatura da stdlib
        pass  # health-check não polui o log estruturado (constitution IV)


def _start_health_server() -> None:
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), _HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def _consumers(settings: Settings) -> list[tuple[str, str, Handler]]:
    """Mapeamento fila→nome→handler — cada User Story acrescenta uma entrada aqui conforme o
    handler correspondente é implementado (registro incremental)."""
    return [
        (settings.solicitar_pedido_queue_url, "solicitar_pedido", handle_solicitar_pedido),
        (
            settings.validar_pedido_response_queue_url,
            "validar_pedido_response",
            handle_validar_pedido_response,
        ),
        (settings.pdf_response_queue_url, "pdf_response", handle_pdf_response),
        (settings.editar_pedido_queue_url, "editar_pedido", handle_editar_pedido),
        (settings.cancelar_pedido_queue_url, "cancelar_pedido", handle_cancelar_pedido),
    ]


def _start_consumers(settings: Settings) -> None:
    sqs = SqsClient(settings)
    for queue_url, name, handler in _consumers(settings):
        threading.Thread(
            target=run_consumer, args=(sqs, queue_url, handler, settings), daemon=True, name=name
        ).start()
        logger.info(f"consumidor '{name}' iniciado")


def main() -> None:
    settings = get_settings()
    _start_health_server()
    _start_consumers(settings)
    logger.info("order-processor pronto")
    threading.Event().wait()  # mantém o processo principal vivo


if __name__ == "__main__":
    main()
