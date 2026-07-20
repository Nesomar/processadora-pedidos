"""Teste de handlers/cancelar_pedido — encerra o pedido como cancelado (US5)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pedidos_shared import MessageEnvelope, Order, OrderItem, OrderStatus, Settings

from order_processor.adapters.orders_repository import create, get_by_id
from order_processor.domain.transicoes import TransicaoInvalidaError
from order_processor.handlers import cancelar_pedido

FAKE_SETTINGS = Settings(
    aws_endpoint_url="http://localhost:4566",
    aws_region="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    processed_messages_table_name="processed_messages",
    orders_table_name="orders",
)


def _order(status: OrderStatus) -> Order:
    now = datetime.now(UTC)
    status_reason = (
        "motivo de teste" if status in (OrderStatus.REJECTED, OrderStatus.FAILED) else None
    )
    return Order(
        order_id=str(uuid.uuid4()),
        customer_id="CUST00001",
        customer_name="Maria Silva",
        customer_document="12345678901",
        channel="HTTP",
        items=[OrderItem(product_id=1, quantity=2)],
        status=status,
        status_reason=status_reason,
        correlation_id=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
        version=0,
    )


def _envelope(order_id: str, reason: str = "Cliente desistiu da compra") -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=order_id,
        occurred_at=datetime.now(UTC),
        payload={"reason": reason},
    )


def test_handle_accepted_cancels_order_with_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    order = _order(OrderStatus.RECEIVED)
    fake_dynamodb = MagicMock()
    fake_dynamodb.get_item.return_value = order.model_dump(mode="json") | {
        "PK": f"ORDER#{order.order_id}",
        "SK": "METADATA",
    }
    monkeypatch.setattr(cancelar_pedido, "DynamoDbClient", lambda settings: fake_dynamodb)

    cancelar_pedido.handle(_envelope(order.order_id), FAKE_SETTINGS)

    _, item = fake_dynamodb.put_item.call_args[0]
    assert item["status"] == OrderStatus.CANCELLED.value
    assert item["status_reason"] == "Cliente desistiu da compra"


def test_handle_rejected_for_non_cancellable_status(monkeypatch: pytest.MonkeyPatch) -> None:
    order = _order(OrderStatus.COMPLETED)
    fake_dynamodb = MagicMock()
    fake_dynamodb.get_item.return_value = order.model_dump(mode="json") | {
        "PK": f"ORDER#{order.order_id}",
        "SK": "METADATA",
    }
    monkeypatch.setattr(cancelar_pedido, "DynamoDbClient", lambda settings: fake_dynamodb)

    with pytest.raises(TransicaoInvalidaError):
        cancelar_pedido.handle(_envelope(order.order_id), FAKE_SETTINGS)

    fake_dynamodb.put_item.assert_called_once()
    _, item = fake_dynamodb.put_item.call_args[0]
    assert item["status"] == OrderStatus.COMPLETED.value
    assert "não pode ser cancelado" in item["status_reason"]


def test_handle_integration_cancels_real_order(dynamodb_client, settings: Settings) -> None:
    order = _order(OrderStatus.PROCESSING)
    create(dynamodb_client, settings.orders_table_name, order)

    cancelar_pedido.handle(_envelope(order.order_id), settings)

    updated = get_by_id(dynamodb_client, settings.orders_table_name, order.order_id)
    assert updated is not None
    assert updated.status == OrderStatus.CANCELLED
    assert updated.status_reason == "Cliente desistiu da compra"
