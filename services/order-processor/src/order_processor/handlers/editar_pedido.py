"""Consome `editar_pedido_queue` — atualiza dados e reabre o ciclo de validação (US4)."""

import uuid
from datetime import UTC, datetime

from pedidos_shared import DynamoDbClient, MessageEnvelope, Order, OrderItem, Settings, SqsClient

from order_processor.adapters.orders_repository import record_rejection, update_with_version
from order_processor.domain.mensagens import montar_payload_validacao
from order_processor.domain.transicoes import TransicaoInvalidaError, aplicar_edicao


def handle(envelope: MessageEnvelope, settings: Settings) -> None:
    payload = envelope.payload
    dynamodb = DynamoDbClient(settings)

    def _apply(order: Order) -> Order:
        novo_status = aplicar_edicao(order.status)
        return order.model_copy(
            update={
                "status": novo_status,
                "status_reason": None,
                "customer_id": payload["customer_id"],
                "customer_name": payload["customer_name"],
                "customer_document": payload["customer_document"],
                "items": [OrderItem(**item) for item in payload["items"]],
                "source_file": payload.get("source_file"),
                "source_line": payload.get("source_line"),
                "subtotal": None,
                "discount_total": None,
                "total": None,
            }
        )

    try:
        updated = update_with_version(
            dynamodb, settings.orders_table_name, envelope.order_id, _apply
        )
    except TransicaoInvalidaError as error:
        record_rejection(dynamodb, settings.orders_table_name, envelope.order_id, str(error))
        raise

    validacao = MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=updated.correlation_id,
        order_id=updated.order_id,
        occurred_at=datetime.now(UTC),
        payload=montar_payload_validacao(updated),
    )
    SqsClient(settings).send(settings.validar_pedido_queue_url, validacao)
