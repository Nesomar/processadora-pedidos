"""Consome `cancelar_pedido_queue` — encerra o pedido como cancelado (US5)."""

from pedidos_shared import DynamoDbClient, MessageEnvelope, Order, Settings

from order_processor.adapters.orders_repository import record_rejection, update_with_version
from order_processor.domain.transicoes import TransicaoInvalidaError, aplicar_cancelamento


def handle(envelope: MessageEnvelope, settings: Settings) -> None:
    payload = envelope.payload
    dynamodb = DynamoDbClient(settings)

    def _apply(order: Order) -> Order:
        novo_status = aplicar_cancelamento(order.status)
        return order.model_copy(update={"status": novo_status, "status_reason": payload["reason"]})

    try:
        update_with_version(dynamodb, settings.orders_table_name, envelope.order_id, _apply)
    except TransicaoInvalidaError as error:
        record_rejection(dynamodb, settings.orders_table_name, envelope.order_id, str(error))
        raise
