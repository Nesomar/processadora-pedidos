"""Teste de PUT /pedidos/{order_id} — editar pedido existente (US3)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

ORDER_ID = "11111111-1111-1111-1111-111111111111"
CORRELATION_ID = "22222222-2222-2222-2222-222222222222"

EDIT_PAYLOAD = {
    "customer_id": "CUST00001",
    "customer_name": "Maria Silva",
    "customer_document": "12345678901",
    "items": [{"product_id": 1, "quantity": 3}],
}


def _order_dict(status: str) -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "order_id": ORDER_ID,
        "customer_id": "CUST00001",
        "customer_name": "Maria Silva",
        "customer_document": "12345678901",
        "channel": "HTTP",
        "items": [{"product_id": 1, "quantity": 2}],
        "status": status,
        "correlation_id": CORRELATION_ID,
        "created_at": now,
        "updated_at": now,
        "version": 0,
    }


def test_editar_pedido_accepts_valid_edit(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_sqs_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict(status="RECEIVED")

    response = client.put(f"/pedidos/{ORDER_ID}", json=EDIT_PAYLOAD)

    assert response.status_code == 202
    body = response.json()
    assert body["order_id"] == ORDER_ID
    assert body["correlation_id"] == CORRELATION_ID
    fake_sqs_client.send.assert_called_once()


def test_editar_pedido_returns_404_when_order_not_found(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_sqs_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = None

    response = client.put("/pedidos/does-not-exist", json=EDIT_PAYLOAD)

    assert response.status_code == 404
    fake_sqs_client.send.assert_not_called()


def test_editar_pedido_returns_409_when_status_not_editable(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_sqs_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict(status="COMPLETED")

    response = client.put(f"/pedidos/{ORDER_ID}", json=EDIT_PAYLOAD)

    assert response.status_code == 409
    fake_sqs_client.send.assert_not_called()


def test_editar_pedido_returns_502_when_publish_fails(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_sqs_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict(status="RECEIVED")
    fake_sqs_client.send.side_effect = RuntimeError("fila indisponível")

    response = client.put(f"/pedidos/{ORDER_ID}", json=EDIT_PAYLOAD)

    assert response.status_code == 502
