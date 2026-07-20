"""Loop de consumo SQS com idempotencia e ack seletivo."""

import time
from collections.abc import Callable

from pedidos_shared import (
    MessageEnvelope,
    Settings,
    SqsClient,
    get_logger,
    is_message_processed,
    mark_message_processed,
)

logger = get_logger("order_validator")

Handler = Callable[[MessageEnvelope, Settings], None]
CONSUMER_NAME = "order-validator"


def process_once(sqs: SqsClient, queue_url: str, handler: Handler, settings: Settings) -> int:
    received = sqs.receive_with_receipt(queue_url)

    for envelope, receipt_handle in received:
        log_context = {"order_id": envelope.order_id, "correlation_id": envelope.correlation_id}
        if is_message_processed(envelope.message_id, CONSUMER_NAME, settings):
            logger.info("mensagem ja processada, descartando", extra=log_context)
            sqs.delete(queue_url, receipt_handle)
            continue

        try:
            handler(envelope, settings)
        except Exception:
            logger.error("falha tecnica ao validar pedido", extra=log_context, exc_info=True)
            continue

        mark_message_processed(envelope.message_id, CONSUMER_NAME, settings)
        sqs.delete(queue_url, receipt_handle)

    return len(received)


def run_consumer(
    sqs: SqsClient,
    queue_url: str,
    handler: Handler,
    settings: Settings,
    poll_interval_seconds: float = 1.0,
) -> None:
    while True:
        received_count = process_once(sqs, queue_url, handler, settings)
        if received_count == 0:
            time.sleep(poll_interval_seconds)
