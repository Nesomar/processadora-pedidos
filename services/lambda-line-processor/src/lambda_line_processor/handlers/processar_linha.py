"""Handler de pedido_lines_queue."""

import httpx
from pedidos_shared import Settings, get_logger

from lambda_line_processor.adapters.api_gateway_client import chamar
from lambda_line_processor.domain.chamada_api import ComandoInvalidoError, montar_chamada

logger = get_logger("lambda_line_processor")

_PERMANENT_STATUS_CODES = (400, 404, 409)


def handle(body: dict, settings: Settings) -> None:
    log_context = {"source_file": body.get("source_file"), "line_number": body.get("line_number")}

    try:
        method, path, request_body = montar_chamada(body)
    except ComandoInvalidoError as error:
        logger.error("comando invalido, descartando", extra={**log_context, "erro": str(error)})
        return

    with httpx.Client(base_url=settings.api_gateway_base_url) as client:
        response = chamar(client, method, path, request_body)

    if response.status_code < 300:
        return

    if response.status_code in _PERMANENT_STATUS_CODES:
        logger.error(
            "api-gateway recusou a chamada",
            extra={
                **log_context,
                "status_code": response.status_code,
                "detail": response.text,
            },
        )
        return

    raise RuntimeError(f"api-gateway respondeu {response.status_code}")
