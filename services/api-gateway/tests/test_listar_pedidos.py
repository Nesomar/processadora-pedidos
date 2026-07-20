"""Teste de GET /pedidos?customerId=X — lista pedidos de um cliente (US6)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from pedidos_shared import DynamoDbClient


def _order_dict(order_id: str) -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "order_id": order_id,
        "customer_id": "CUST00001",
        "customer_name": "Maria Silva",
        "customer_document": "12345678901",
        "channel": "HTTP",
        "items": [{"product_id": 1, "quantity": 2}],
        "status": "RECEIVED",
        "correlation_id": "22222222-2222-2222-2222-222222222222",
        "created_at": now,
        "updated_at": now,
        "version": 0,
    }


def test_listar_pedidos_returns_orders_most_recent_first(
    client: TestClient, fake_dynamodb_client: MagicMock
) -> None:
    table = MagicMock()
    table.query.return_value = {
        "Items": [
            _order_dict("22222222-2222-2222-2222-222222222222"),
            _order_dict("11111111-1111-1111-1111-111111111111"),
        ]
    }
    fake_dynamodb_client.table.return_value = table

    response = client.get("/pedidos", params={"customerId": "CUST00001"})

    assert response.status_code == 200
    body = response.json()
    assert [p["order_id"] for p in body["pedidos"]] == [
        "22222222-2222-2222-2222-222222222222",
        "11111111-1111-1111-1111-111111111111",
    ]
    assert all(p["customer_document"] == "*******8901" for p in body["pedidos"])

    _, kwargs = table.query.call_args
    assert kwargs["IndexName"] == "GSI1"
    assert kwargs["ScanIndexForward"] is False


def test_listar_pedidos_returns_empty_list_when_no_orders(
    client: TestClient, fake_dynamodb_client: MagicMock
) -> None:
    table = MagicMock()
    table.query.return_value = {"Items": []}
    fake_dynamodb_client.table.return_value = table

    response = client.get("/pedidos", params={"customerId": "CUST00002"})

    assert response.status_code == 200
    assert response.json() == {"pedidos": []}


def test_listar_pedidos_integration_reads_seeded_orders(integration_client: TestClient) -> None:
    from api_gateway.config import get_settings

    settings = get_settings()
    dynamodb = DynamoDbClient(settings)
    customer_id = f"CUST{uuid.uuid4().hex[:8]}"
    order_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    item = {
        **_order_dict(order_id),
        "customer_id": customer_id,
        "PK": f"ORDER#{order_id}",
        "SK": "METADATA",
        "GSI1PK": f"CUSTOMER#{customer_id}",
        "GSI1SK": f"{now}#{order_id}",
    }
    dynamodb.put_item(settings.orders_table_name, item)

    response = integration_client.get("/pedidos", params={"customerId": customer_id})

    assert response.status_code == 200
    body = response.json()
    assert [p["order_id"] for p in body["pedidos"]] == [order_id]
    assert body["pedidos"][0]["customer_document"] == "*******8901"
