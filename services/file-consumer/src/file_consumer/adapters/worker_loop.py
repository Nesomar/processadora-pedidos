"""Loop de consumo SQS cru (sem MessageEnvelope) com idempotencia por MessageId nativo."""

import time
from collections.abc import Callable

from pedidos_shared import (
    Settings,
    SqsClient,
    get_logger,
    is_message_processed,
    mark_message_processed,
)

logger = get_logger("file_consumer")

Handler = Callable[[dict, Settings], None]
CONSUMER_NAME = "file-consumer"


def process_once(sqs: SqsClient, queue_url: str, handler: Handler, settings: Settings) -> int:
    received = sqs.receive_raw_with_receipt(queue_url)

    for body, receipt_handle, message_id in received:
        log_context = {"message_id": message_id}
        if is_message_processed(message_id, CONSUMER_NAME, settings):
            logger.info("notificacao ja processada, descartando", extra=log_context)
            sqs.delete(queue_url, receipt_handle)
            continue

        try:
            handler(body, settings)
        except Exception:
            logger.error("falha tecnica ao processar notificacao", extra=log_context, exc_info=True)
            continue

        mark_message_processed(message_id, CONSUMER_NAME, settings)
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
