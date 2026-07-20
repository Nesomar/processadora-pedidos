"""Teste de orders_repository — único escritor de `orders` (contrato regra 3 de pedidos_shared)."""

import uuid
from datetime import UTC, datetime

import pytest
from pedidos_shared import Order, OrderItem, OrderStatus

from order_processor.adapters.orders_repository import (
    ConflitoDeConcorrenciaError,
    create,
    get_by_id,
    update_with_version,
)


def _new_order(order_id: str) -> Order:
    now = datetime.now(UTC)
    return Order(
        order_id=order_id,
        customer_id="CUST00001",
        customer_name="Maria Silva",
        customer_document="12345678901",
        channel="HTTP",
        items=[OrderItem(product_id=1, quantity=2)],
        status=OrderStatus.PROCESSING,
        correlation_id=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
        version=0,
    )


def test_create_and_get_by_id(dynamodb_client, table_name: str) -> None:
    order_id = str(uuid.uuid4())
    order = _new_order(order_id)

    create(dynamodb_client, table_name, order)
    fetched = get_by_id(dynamodb_client, table_name, order_id)

    assert fetched is not None
    assert fetched.order_id == order_id
    assert fetched.status == OrderStatus.PROCESSING
    assert fetched.version == 0


def test_get_by_id_returns_none_when_not_found(dynamodb_client, table_name: str) -> None:
    assert get_by_id(dynamodb_client, table_name, str(uuid.uuid4())) is None


def test_create_rejects_duplicate_order_id(dynamodb_client, table_name: str) -> None:
    order_id = str(uuid.uuid4())
    order = _new_order(order_id)

    create(dynamodb_client, table_name, order)
    with pytest.raises(Exception):  # noqa: B017 — ClientError do boto3, condição já existe
        create(dynamodb_client, table_name, order)


def test_update_with_version_applies_change_and_bumps_version(
    dynamodb_client, table_name: str
) -> None:
    order_id = str(uuid.uuid4())
    create(dynamodb_client, table_name, _new_order(order_id))

    updated = update_with_version(
        dynamodb_client,
        table_name,
        order_id,
        lambda order: order.model_copy(update={"status": OrderStatus.VALIDATING}),
    )

    assert updated.status == OrderStatus.VALIDATING
    assert updated.version == 1

    fetched = get_by_id(dynamodb_client, table_name, order_id)
    assert fetched is not None
    assert fetched.status == OrderStatus.VALIDATING
    assert fetched.version == 1


def test_update_with_version_raises_when_order_not_found(dynamodb_client, table_name: str) -> None:
    with pytest.raises(ValueError):
        update_with_version(dynamodb_client, table_name, str(uuid.uuid4()), lambda order: order)


def test_update_with_version_retries_and_raises_after_exhausted_attempts(
    dynamodb_client, table_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from botocore.exceptions import ClientError

    order_id = str(uuid.uuid4())
    create(dynamodb_client, table_name, _new_order(order_id))

    def _always_conflicts(*args, **kwargs):
        raise ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "conflict"}},
            "PutItem",
        )

    monkeypatch.setattr(dynamodb_client, "put_item", _always_conflicts)

    with pytest.raises(ConflitoDeConcorrenciaError):
        update_with_version(dynamodb_client, table_name, order_id, lambda order: order)
