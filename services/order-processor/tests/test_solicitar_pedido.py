"""Teste de handlers/solicitar_pedido — cria pedido e dispara validação (US1)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pedidos_shared import MessageEnvelope, OrderStatus, Settings, SqsClient

from order_processor.adapters.orders_repository import get_by_id
from order_processor.handlers import solicitar_pedido

FAKE_SETTINGS = Settings(
    aws_endpoint_url="http://localhost:4566",
    aws_region="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    processed_messages_table_name="processed_messages",
    orders_table_name="orders",
    validar_pedido_queue_url="http://localhost:4566/000000000000/validar_pedido_queue",
)


def _envelope() -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid4()),
        correlation_id=str(uuid4()),
        order_id=str(uuid4()),
        occurred_at=datetime.now(UTC),
        payload={
            "customer_id": "CUST00001",
            "customer_name": "Maria Silva",
            "customer_document": "12345678901",
            "channel": "HTTP",
            "items": [{"product_id": 1, "quantity": 50}],
            "source_file": None,
            "source_line": None,
        },
    )


def test_handle_creates_order_and_publishes_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_dynamodb = MagicMock()
    fake_sqs = MagicMock()
    monkeypatch.setattr(solicitar_pedido, "DynamoDbClient", lambda settings: fake_dynamodb)
    monkeypatch.setattr(solicitar_pedido, "SqsClient", lambda settings: fake_sqs)
    envelope = _envelope()

    solicitar_pedido.handle(envelope, FAKE_SETTINGS)

    fake_dynamodb.put_item.assert_called_once()
    table_name, item = fake_dynamodb.put_item.call_args[0]
    assert table_name == "orders"
    assert item["order_id"] == envelope.order_id
    assert item["status"] == OrderStatus.VALIDATING.value
    assert item["PK"] == f"ORDER#{envelope.order_id}"

    fake_sqs.send.assert_called_once()
    queue_url, validacao_envelope = fake_sqs.send.call_args[0]
    assert queue_url == FAKE_SETTINGS.validar_pedido_queue_url
    assert validacao_envelope.order_id == envelope.order_id
    assert validacao_envelope.correlation_id == envelope.correlation_id
    assert validacao_envelope.payload == {
        "customer_document": "12345678901",
        "items": [{"product_id": 1, "quantity": 50}],
    }


def test_handle_integration_creates_order_and_publishes_real_message(
    dynamodb_client, sqs_client, settings: Settings
) -> None:
    envelope = _envelope()

    solicitar_pedido.handle(envelope, settings)

    order = get_by_id(dynamodb_client, settings.orders_table_name, envelope.order_id)
    assert order is not None
    assert order.status == OrderStatus.VALIDATING

    received = SqsClient(settings).receive(settings.validar_pedido_queue_url)
    assert any(msg.order_id == envelope.order_id for msg in received)
