"""Teste de GET /pedidos/{order_id} — consulta um pedido específico (US5, FR-008)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pedidos_shared import DynamoDbClient

ORDER_ID = "11111111-1111-1111-1111-111111111111"


def _order_dict(status: str = "RECEIVED") -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "order_id": ORDER_ID,
        "customer_id": "CUST00001",
        "customer_name": "Maria Silva",
        "customer_document": "12345678901",
        "channel": "HTTP",
        "items": [{"product_id": 1, "quantity": 2}],
        "status": status,
        "correlation_id": "22222222-2222-2222-2222-222222222222",
        "created_at": now,
        "updated_at": now,
        "version": 0,
    }


def test_consultar_pedido_returns_masked_document(
    client: TestClient, fake_dynamodb_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict()

    response = client.get(f"/pedidos/{ORDER_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["order_id"] == ORDER_ID
    assert body["customer_document"] == "*******8901"
    assert body["status"] == "RECEIVED"


def test_consultar_pedido_returns_404_when_not_found(
    client: TestClient, fake_dynamodb_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = None

    response = client.get("/pedidos/does-not-exist")

    assert response.status_code == 404


def test_consultar_pedido_integration_reads_seeded_order(integration_client: TestClient) -> None:
    from api_gateway.config import get_settings

    settings = get_settings()
    dynamodb = DynamoDbClient(settings)
    order_id = str(uuid.uuid4())
    item = {
        **_order_dict(),
        "order_id": order_id,
        "PK": f"ORDER#{order_id}",
        "SK": "METADATA",
    }
    dynamodb.put_item(settings.orders_table_name, item)

    response = integration_client.get(f"/pedidos/{order_id}")

    assert response.status_code == 200
    assert response.json()["customer_document"] == "*******8901"
