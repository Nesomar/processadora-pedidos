"""Teste de idempotência (US6, FR-010) — reprocessar a mesma mensagem não duplica efeito."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pedidos_shared import MessageEnvelope, Order, OrderItem, OrderStatus, Settings

from order_processor.adapters import worker_loop
from order_processor.handlers import (
    cancelar_pedido,
    editar_pedido,
    pdf_response,
    solicitar_pedido,
    validar_pedido_response,
)

QUEUE_URL = "http://localhost:4566/000000000000/alguma_fila"


def _existing_order_dict(order_id: str, status: OrderStatus) -> dict:
    now = datetime.now(UTC)
    order = Order(
        order_id=order_id,
        customer_id="CUST00001",
        customer_name="Maria Silva",
        customer_document="12345678901",
        channel="HTTP",
        items=[OrderItem(product_id=1, quantity=2)],
        status=status,
        correlation_id=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
        version=0,
    )
    return order.model_dump(mode="json") | {"PK": f"ORDER#{order_id}", "SK": "METADATA"}


def _solicitar_envelope() -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=str(uuid.uuid4()),
        occurred_at=datetime.now(UTC),
        payload={
            "customer_id": "CUST00001",
            "customer_name": "Maria Silva",
            "customer_document": "12345678901",
            "channel": "HTTP",
            "items": [{"product_id": 1, "quantity": 2}],
            "source_file": None,
            "source_line": None,
        },
    )


def _editar_envelope(order_id: str) -> MessageEnvelope:
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
            "items": [{"product_id": 1, "quantity": 3}],
            "source_file": None,
            "source_line": None,
        },
    )


def _cancelar_envelope(order_id: str) -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=order_id,
        occurred_at=datetime.now(UTC),
        payload={"reason": "motivo"},
    )


def _validar_response_envelope(order_id: str) -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=order_id,
        occurred_at=datetime.now(UTC),
        payload={
            "approved": False,
            "errors": [{"code": "X", "product_id": 1, "message": "motivo"}],
            "enriched_items": None,
            "subtotal": None,
            "discount_total": None,
            "total": None,
        },
    )


def _pdf_response_envelope(order_id: str) -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=order_id,
        occurred_at=datetime.now(UTC),
        payload={"success": False, "s3_key": None, "error_message": "falha"},
    )


@pytest.mark.parametrize(
    ("module", "make_envelope", "existing_status"),
    [
        (solicitar_pedido, lambda oid: _solicitar_envelope(), None),
        (editar_pedido, _editar_envelope, OrderStatus.RECEIVED),
        (cancelar_pedido, _cancelar_envelope, OrderStatus.RECEIVED),
        (validar_pedido_response, _validar_response_envelope, OrderStatus.VALIDATING),
        (pdf_response, _pdf_response_envelope, OrderStatus.INVOICING),
    ],
    ids=[
        "solicitar_pedido",
        "editar_pedido",
        "cancelar_pedido",
        "validar_pedido_response",
        "pdf_response",
    ],
)
def test_reprocessing_same_message_calls_handler_only_once(
    module, make_envelope, existing_status, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id = str(uuid.uuid4())
    envelope = make_envelope(order_id)

    fake_dynamodb = MagicMock()
    if existing_status is not None:
        fake_dynamodb.get_item.return_value = _existing_order_dict(order_id, existing_status)
    fake_sqs_business = MagicMock()
    monkeypatch.setattr(module, "DynamoDbClient", lambda s: fake_dynamodb)
    if hasattr(module, "SqsClient"):
        monkeypatch.setattr(module, "SqsClient", lambda s: fake_sqs_business)

    spy_handler = MagicMock(wraps=module.handle)
    queue_sqs = MagicMock()
    queue_sqs.receive_with_receipt.return_value = [(envelope, "receipt-1")]

    worker_loop.process_once(queue_sqs, QUEUE_URL, spy_handler, settings)
    worker_loop.process_once(queue_sqs, QUEUE_URL, spy_handler, settings)

    assert spy_handler.call_count == 1
    assert queue_sqs.delete.call_count == 2


def test_reprocessing_integration_same_message_twice_does_not_duplicate_order(
    dynamodb_client, sqs_client, settings: Settings
) -> None:
    envelope = _solicitar_envelope()

    sqs_client.send(settings.solicitar_pedido_queue_url, envelope)
    worker_loop.process_once(
        sqs_client, settings.solicitar_pedido_queue_url, solicitar_pedido.handle, settings
    )

    sqs_client.send(settings.solicitar_pedido_queue_url, envelope)
    worker_loop.process_once(
        sqs_client, settings.solicitar_pedido_queue_url, solicitar_pedido.handle, settings
    )

    from order_processor.adapters.orders_repository import get_by_id

    order = get_by_id(dynamodb_client, settings.orders_table_name, envelope.order_id)
    assert order is not None
    assert order.version == 0  # criado uma única vez, nunca atualizado

    validacoes = sqs_client.receive(settings.validar_pedido_queue_url)
    matching = [msg for msg in validacoes if msg.order_id == envelope.order_id]
    assert len(matching) == 1
