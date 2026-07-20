"""Teste de POST /pedidos/{order_id}/cancelamento — cancelar pedido existente (US4)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

ORDER_ID = "11111111-1111-1111-1111-111111111111"
CORRELATION_ID = "22222222-2222-2222-2222-222222222222"


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


def test_cancelar_pedido_accepts_with_reason(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_sqs_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict(status="RECEIVED")

    response = client.post(
        f"/pedidos/{ORDER_ID}/cancelamento", json={"reason": "Cliente desistiu da compra"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["order_id"] == ORDER_ID
    assert body["correlation_id"] == CORRELATION_ID
    fake_sqs_client.send.assert_called_once()


def test_cancelar_pedido_rejects_missing_reason(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_sqs_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict(status="RECEIVED")

    response = client.post(f"/pedidos/{ORDER_ID}/cancelamento", json={})

    assert response.status_code == 400
    fake_sqs_client.send.assert_not_called()


def test_cancelar_pedido_returns_404_when_order_not_found(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_sqs_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = None

    response = client.post("/pedidos/does-not-exist/cancelamento", json={"reason": "motivo"})

    assert response.status_code == 404
    fake_sqs_client.send.assert_not_called()


def test_cancelar_pedido_returns_409_when_status_not_cancellable(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_sqs_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict(status="COMPLETED")

    response = client.post(f"/pedidos/{ORDER_ID}/cancelamento", json={"reason": "motivo"})

    assert response.status_code == 409
    fake_sqs_client.send.assert_not_called()


def test_cancelar_pedido_returns_502_when_publish_fails(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_sqs_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict(status="RECEIVED")
    fake_sqs_client.send.side_effect = RuntimeError("fila indisponível")

    response = client.post(f"/pedidos/{ORDER_ID}/cancelamento", json={"reason": "motivo"})

    assert response.status_code == 502
