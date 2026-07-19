"""Testes de Order, OrderItem e MessageEnvelope (data-model.md)."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from pedidos_shared.models import MessageEnvelope, Order, OrderItem
from pedidos_shared.status import OrderStatus


def _make_order(**overrides: object) -> Order:
    defaults: dict[str, object] = dict(
        order_id=str(uuid4()),
        customer_id="CUST00001",
        customer_name="Maria Silva",
        customer_document="12345678901",
        channel="HTTP",
        items=[OrderItem(product_id=1, quantity=2)],
        status=OrderStatus.RECEIVED,
        correlation_id=str(uuid4()),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        version=0,
    )
    defaults.update(overrides)
    return Order(**defaults)


def test_order_item_accepts_valid_payload() -> None:
    item = OrderItem(product_id=1, quantity=5)
    assert item.quantity == 5
    assert item.unit_price is None


def test_order_item_rejects_missing_required_field() -> None:
    with pytest.raises(ValidationError):
        OrderItem(quantity=5)  # type: ignore[call-arg]


def test_order_item_line_total_uses_decimal() -> None:
    item = OrderItem(
        product_id=1,
        quantity=2,
        unit_price=Decimal("10.50"),
        discount_percentage=Decimal("0"),
        line_total=Decimal("21.00"),
    )
    assert isinstance(item.unit_price, Decimal)
    assert item.line_total == Decimal("21.00")


def test_order_accepts_valid_payload() -> None:
    order = _make_order()
    assert order.status is OrderStatus.RECEIVED
    assert order.channel == "HTTP"
    assert len(order.items) == 1


def test_order_rejects_missing_required_field() -> None:
    with pytest.raises(ValidationError):
        Order(
            customer_id="CUST00001",
            customer_name="Maria Silva",
            customer_document="12345678901",
            channel="HTTP",
            items=[OrderItem(product_id=1, quantity=1)],
            status=OrderStatus.RECEIVED,
            correlation_id=str(uuid4()),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            version=0,
        )  # type: ignore[call-arg]


def test_order_rejects_invalid_channel() -> None:
    with pytest.raises(ValidationError):
        _make_order(channel="FTP")


def test_order_version_is_int() -> None:
    order = _make_order(version=3)
    assert order.version == 3
    assert isinstance(order.version, int)


def test_message_envelope_accepts_valid_payload() -> None:
    order = _make_order()
    envelope = MessageEnvelope(
        message_id=str(uuid4()),
        correlation_id=order.correlation_id,
        order_id=order.order_id,
        occurred_at=datetime.now(UTC),
        payload={"foo": "bar"},
    )
    assert envelope.order_id == order.order_id
    assert envelope.payload == {"foo": "bar"}


def test_message_envelope_rejects_missing_required_field() -> None:
    with pytest.raises(ValidationError):
        MessageEnvelope(
            correlation_id=str(uuid4()),
            order_id=str(uuid4()),
            occurred_at=datetime.now(UTC),
            payload={},
        )  # type: ignore[call-arg]
