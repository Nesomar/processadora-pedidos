"""Publicação de mensagem com log estruturado de falha (constitution IV/I.5)."""

from fastapi import HTTPException, status
from pedidos_shared import MessageEnvelope, SqsClient, get_logger

logger = get_logger("api_gateway")


def publicar_ou_502(
    sqs: SqsClient,
    queue_url: str,
    envelope: MessageEnvelope,
    detail: str,
) -> None:
    """Publica `envelope` em `queue_url`; em falha, loga (JSON, orderId/correlationId) e
    levanta `HTTPException(502)` — nunca falha silenciosamente (constitution I.5)."""
    try:
        sqs.send(queue_url, envelope)
    except Exception as error:
        logger.error(
            detail,
            extra={"order_id": envelope.order_id, "correlation_id": envelope.correlation_id},
            exc_info=True,
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from error
