"""Teste de handlers/pdf_response — conclui ou marca falha no pedido (US3)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pedidos_shared import MessageEnvelope, Order, OrderItem, OrderStatus, Settings

from order_processor.adapters.orders_repository import create, get_by_id
from order_processor.handlers import pdf_response

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


def _envelope(order_id: str, success: bool) -> MessageEnvelope:
    payload = (
        {"success": True, "s3_key": f"invoices/2026/07/20/{order_id}.pdf", "error_message": None}
        if success
        else {"success": False, "s3_key": None, "error_message": "timeout no gerador de PDF"}
    )
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=order_id,
        occurred_at=datetime.now(UTC),
        payload=payload,
    )


def test_handle_success_completes_order_with_invoice_key(monkeypatch: pytest.MonkeyPatch) -> None:
    order = _order(OrderStatus.INVOICING)
    fake_dynamodb = MagicMock()
    fake_dynamodb.get_item.return_value = order.model_dump(mode="json") | {
        "PK": f"ORDER#{order.order_id}",
        "SK": "METADATA",
    }
    monkeypatch.setattr(pdf_response, "DynamoDbClient", lambda settings: fake_dynamodb)

    pdf_response.handle(_envelope(order.order_id, success=True), FAKE_SETTINGS)

    _, item = fake_dynamodb.put_item.call_args[0]
    assert item["status"] == OrderStatus.COMPLETED.value
    assert item["invoice_s3_key"] == f"invoices/2026/07/20/{order.order_id}.pdf"


def test_handle_failure_marks_order_as_failed_with_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    order = _order(OrderStatus.INVOICING)
    fake_dynamodb = MagicMock()
    fake_dynamodb.get_item.return_value = order.model_dump(mode="json") | {
        "PK": f"ORDER#{order.order_id}",
        "SK": "METADATA",
    }
    monkeypatch.setattr(pdf_response, "DynamoDbClient", lambda settings: fake_dynamodb)

    pdf_response.handle(_envelope(order.order_id, success=False), FAKE_SETTINGS)

    _, item = fake_dynamodb.put_item.call_args[0]
    assert item["status"] == OrderStatus.FAILED.value
    assert item["status_reason"] == "timeout no gerador de PDF"


def test_handle_integration_success_completes_real_order(
    dynamodb_client, settings: Settings
) -> None:
    order = _order(OrderStatus.INVOICING)
    create(dynamodb_client, settings.orders_table_name, order)

    pdf_response.handle(_envelope(order.order_id, success=True), settings)

    updated = get_by_id(dynamodb_client, settings.orders_table_name, order.order_id)
    assert updated is not None
    assert updated.status == OrderStatus.COMPLETED
    assert updated.invoice_s3_key == f"invoices/2026/07/20/{order.order_id}.pdf"
