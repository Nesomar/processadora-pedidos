"""Loop de consumo genérico: idempotência + dispatch + ack seletivo (research.md #2, #4)."""

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

from order_processor.domain.transicoes import TransicaoInvalidaError

logger = get_logger("order_processor")

Handler = Callable[[MessageEnvelope, Settings], None]

CONSUMER_NAME = "order-processor"


def process_once(sqs: SqsClient, queue_url: str, handler: Handler, settings: Settings) -> int:
    """Processa as mensagens disponíveis agora; devolve quantas foram recebidas.

    Mensagem já marcada como processada é confirmada e descartada silenciosamente (log `info`,
    docs/01-dominio-e-contratos.md §3). `mark_message_processed` só é chamado DEPOIS do handler
    concluir (sucesso ou rejeição de negócio) — nunca antes: se marcasse antes e o handler falhasse
    por erro técnico, a redelivery do SQS veria a mensagem já marcada e a descartaria sem nunca
    reprocessar de verdade, anulando o redrive nativo (constitution I.5). `TransicaoInvalidaError`
    (erro de negócio — ex.: editar pedido em estado que não permite) é confirmada: reter a
    mensagem pro redrive não ajudaria, o estado do pedido não muda sozinho. Qualquer outra exceção
    é tratada como falha técnica — a mensagem NÃO é confirmada nem marcada, ficando disponível pro
    redrive.
    """
    received = sqs.receive_with_receipt(queue_url)

    for envelope, receipt_handle in received:
        log_context = {"order_id": envelope.order_id, "correlation_id": envelope.correlation_id}

        if is_message_processed(envelope.message_id, CONSUMER_NAME, settings):
            logger.info("mensagem já processada, descartando", extra=log_context)
            sqs.delete(queue_url, receipt_handle)
            continue

        try:
            handler(envelope, settings)
        except TransicaoInvalidaError as error:
            logger.warning(
                "mensagem rejeitada como erro de negócio",
                extra=log_context | {"motivo": str(error)},
            )
        except Exception:
            logger.error("falha técnica ao processar mensagem", extra=log_context, exc_info=True)
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
    """Loop infinito — roda numa thread dedicada por fila (research.md #1)."""
    while True:
        received_count = process_once(sqs, queue_url, handler, settings)
        if received_count == 0:
            time.sleep(poll_interval_seconds)
