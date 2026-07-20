"""Consome `solicitar_pedido_queue` — cria o pedido e dispara validação (US1)."""

import uuid
from datetime import UTC, datetime

from pedidos_shared import DynamoDbClient, MessageEnvelope, Order, OrderItem, Settings, SqsClient

from order_processor.adapters.orders_repository import create
from order_processor.domain.mensagens import montar_payload_validacao
from order_processor.domain.transicoes import aplicar_solicitacao


def handle(envelope: MessageEnvelope, settings: Settings) -> None:
    payload = envelope.payload

    order = Order(
        order_id=envelope.order_id,
        customer_id=payload["customer_id"],
        customer_name=payload["customer_name"],
        customer_document=payload["customer_document"],
        channel=payload["channel"],
        items=[OrderItem(**item) for item in payload["items"]],
        status=aplicar_solicitacao(),
        correlation_id=envelope.correlation_id,
        source_file=payload.get("source_file"),
        source_line=payload.get("source_line"),
        created_at=envelope.occurred_at,
        updated_at=envelope.occurred_at,
        version=0,
    )

    create(DynamoDbClient(settings), settings.orders_table_name, order)

    validacao = MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=order.correlation_id,
        order_id=order.order_id,
        occurred_at=datetime.now(UTC),
        payload=montar_payload_validacao(order),
    )
    SqsClient(settings).send(settings.validar_pedido_queue_url, validacao)
