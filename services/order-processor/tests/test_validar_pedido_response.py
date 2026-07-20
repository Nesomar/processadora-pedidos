"""Teste de handlers/validar_pedido_response — aprova (dispara PDF) ou rejeita (US2)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pedidos_shared import MessageEnvelope, Order, OrderItem, OrderStatus, Settings, SqsClient

from order_processor.adapters.orders_repository import create, get_by_id
from order_processor.handlers import validar_pedido_response

FAKE_SETTINGS = Settings(
    aws_endpoint_url="http://localhost:4566",
    aws_region="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    processed_messages_table_name="processed_messages",
    orders_table_name="orders",
    pdf_request_queue_url="http://localhost:4566/000000000000/pdf_request_queue",
)


def _order(status: OrderStatus) -> Order:
    now = datetime.now(UTC)
    return Order(
        order_id=str(uuid.uuid4()),
        customer_id="CUST00001",
        customer_name="Maria Silva",
        customer_document="12345678901",
        channel="HTTP",
        items=[OrderItem(product_id=1, quantity=50)],
        status=status,
        correlation_id=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
        version=0,
    )


def _envelope(order_id: str, approved: bool) -> MessageEnvelope:
    if approved:
        payload = {
            "approved": True,
            "errors": [],
            "enriched_items": [
                {
                    "product_id": 1,
                    "quantity": 50,
                    "unit_price": "9.99",
                    "discount_percentage": "10.48",
                    "line_total": "447.05",
                    "product_title": "Essence Mascara",
                    "product_sku": "BEA-001",
                }
            ],
            "subtotal": "499.50",
            "discount_total": "52.45",
            "total": "447.05",
        }
    else:
        payload = {
            "approved": False,
            "errors": [
                {
                    "code": "BELOW_MINIMUM_ORDER_QUANTITY",
                    "product_id": 1,
                    "message": "Quantidade abaixo do mínimo",
                }
            ],
            "enriched_items": None,
            "subtotal": None,
            "discount_total": None,
            "total": None,
        }
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=order_id,
        occurred_at=datetime.now(UTC),
        payload=payload,
    )


def test_handle_approved_updates_order_and_publishes_pdf_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = _order(OrderStatus.VALIDATING)
    fake_dynamodb = MagicMock()
    fake_dynamodb.get_item.return_value = order.model_dump(mode="json") | {
        "PK": f"ORDER#{order.order_id}",
        "SK": "METADATA",
    }
    fake_sqs = MagicMock()
    monkeypatch.setattr(validar_pedido_response, "DynamoDbClient", lambda settings: fake_dynamodb)
    monkeypatch.setattr(validar_pedido_response, "SqsClient", lambda settings: fake_sqs)

    validar_pedido_response.handle(_envelope(order.order_id, approved=True), FAKE_SETTINGS)

    fake_dynamodb.put_item.assert_called_once()
    _, item = fake_dynamodb.put_item.call_args[0]
    assert item["status"] == OrderStatus.INVOICING.value
    assert item["subtotal"] == "499.50"
    assert item["items"][0]["unit_price"] == "9.99"

    fake_sqs.send.assert_called_once()
    queue_url, pdf_envelope = fake_sqs.send.call_args[0]
    assert queue_url == FAKE_SETTINGS.pdf_request_queue_url
    assert pdf_envelope.order_id == order.order_id


def test_handle_rejected_updates_order_with_reason_and_does_not_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = _order(OrderStatus.VALIDATING)
    fake_dynamodb = MagicMock()
    fake_dynamodb.get_item.return_value = order.model_dump(mode="json") | {
        "PK": f"ORDER#{order.order_id}",
        "SK": "METADATA",
    }
    fake_sqs = MagicMock()
    monkeypatch.setattr(validar_pedido_response, "DynamoDbClient", lambda settings: fake_dynamodb)
    monkeypatch.setattr(validar_pedido_response, "SqsClient", lambda settings: fake_sqs)

    validar_pedido_response.handle(_envelope(order.order_id, approved=False), FAKE_SETTINGS)

    fake_dynamodb.put_item.assert_called_once()
    _, item = fake_dynamodb.put_item.call_args[0]
    assert item["status"] == OrderStatus.REJECTED.value
    assert "abaixo do mínimo" in item["status_reason"]

    fake_sqs.send.assert_not_called()


def test_handle_integration_approved_transitions_to_invoicing_and_publishes_real_pdf_request(
    dynamodb_client, sqs_client, settings: Settings
) -> None:
    order = _order(OrderStatus.VALIDATING)
    create(dynamodb_client, settings.orders_table_name, order)

    validar_pedido_response.handle(_envelope(order.order_id, approved=True), settings)

    updated = get_by_id(dynamodb_client, settings.orders_table_name, order.order_id)
    assert updated is not None
    assert updated.status == OrderStatus.INVOICING

    received = SqsClient(settings).receive(settings.pdf_request_queue_url)
    assert any(msg.order_id == order.order_id for msg in received)
