"""Teste de handlers/editar_pedido — reabre o ciclo de validação em estado editável (US4)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pedidos_shared import MessageEnvelope, Order, OrderItem, OrderStatus, Settings, SqsClient

from order_processor.adapters.orders_repository import create, get_by_id
from order_processor.domain.transicoes import TransicaoInvalidaError
from order_processor.handlers import editar_pedido

FAKE_SETTINGS = Settings(
    aws_endpoint_url="http://localhost:4566",
    aws_region="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    processed_messages_table_name="processed_messages",
    orders_table_name="orders",
    validar_pedido_queue_url="http://localhost:4566/000000000000/validar_pedido_queue",
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


def _envelope(order_id: str) -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=order_id,
        occurred_at=datetime.now(UTC),
        payload={
            "customer_id": "CUST00001",
            "customer_name": "Maria Silva",
            "customer_document": "12345678901",
            "channel": "HTTP",
            "items": [{"product_id": 1, "quantity": 5}],
            "source_file": None,
            "source_line": None,
        },
    )


def test_handle_accepted_updates_and_republishes_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = _order(OrderStatus.RECEIVED)
    fake_dynamodb = MagicMock()
    fake_dynamodb.get_item.return_value = order.model_dump(mode="json") | {
        "PK": f"ORDER#{order.order_id}",
        "SK": "METADATA",
    }
    fake_sqs = MagicMock()
    monkeypatch.setattr(editar_pedido, "DynamoDbClient", lambda settings: fake_dynamodb)
    monkeypatch.setattr(editar_pedido, "SqsClient", lambda settings: fake_sqs)

    editar_pedido.handle(_envelope(order.order_id), FAKE_SETTINGS)

    _, item = fake_dynamodb.put_item.call_args[0]
    assert item["status"] == OrderStatus.VALIDATING.value
    assert item["items"][0]["quantity"] == 5

    fake_sqs.send.assert_called_once()
    queue_url, _ = fake_sqs.send.call_args[0]
    assert queue_url == FAKE_SETTINGS.validar_pedido_queue_url


def test_handle_rejected_for_non_editable_status(monkeypatch: pytest.MonkeyPatch) -> None:
    order = _order(OrderStatus.COMPLETED)
    fake_dynamodb = MagicMock()
    fake_dynamodb.get_item.return_value = order.model_dump(mode="json") | {
        "PK": f"ORDER#{order.order_id}",
        "SK": "METADATA",
    }
    fake_sqs = MagicMock()
    monkeypatch.setattr(editar_pedido, "DynamoDbClient", lambda settings: fake_dynamodb)
    monkeypatch.setattr(editar_pedido, "SqsClient", lambda settings: fake_sqs)

    with pytest.raises(TransicaoInvalidaError):
        editar_pedido.handle(_envelope(order.order_id), FAKE_SETTINGS)

    fake_dynamodb.put_item.assert_called_once()
    _, item = fake_dynamodb.put_item.call_args[0]
    assert item["status"] == OrderStatus.COMPLETED.value
    assert "não pode ser editado" in item["status_reason"]
    fake_sqs.send.assert_not_called()


def test_handle_integration_reopens_cycle_for_real_order(
    dynamodb_client, sqs_client, settings: Settings
) -> None:
    order = _order(OrderStatus.REJECTED)
    create(dynamodb_client, settings.orders_table_name, order)

    editar_pedido.handle(_envelope(order.order_id), settings)

    updated = get_by_id(dynamodb_client, settings.orders_table_name, order.order_id)
    assert updated is not None
    assert updated.status == OrderStatus.VALIDATING

    received = SqsClient(settings).receive(settings.validar_pedido_queue_url)
    assert any(msg.order_id == order.order_id for msg in received)
