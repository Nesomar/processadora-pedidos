"""Teste de POST /pedidos — criar pedido (US1) e canal BATCH (US2)."""

import time
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

VALID_PAYLOAD = {
    "customer_id": "CUST00001",
    "customer_name": "Maria Silva",
    "customer_document": "12345678901",
    "items": [{"product_id": 1, "quantity": 50}],
}


def test_solicitar_pedido_accepts_valid_payload(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    response = client.post("/pedidos", json=VALID_PAYLOAD)

    assert response.status_code == 202
    body = response.json()
    assert "order_id" in body
    assert "correlation_id" in body

    fake_sqs_client.send.assert_called_once()
    queue_url, envelope = fake_sqs_client.send.call_args[0]
    assert queue_url == "http://localhost:4566/000000000000/solicitar_pedido_queue"
    assert envelope.order_id == body["order_id"]
    assert envelope.correlation_id == body["correlation_id"]


def test_solicitar_pedido_rejects_invalid_payload(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    response = client.post("/pedidos", json={**VALID_PAYLOAD, "items": []})

    assert response.status_code == 400
    assert "order_id" not in response.json()
    fake_sqs_client.send.assert_not_called()


def test_solicitar_pedido_returns_502_when_publish_fails(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    fake_sqs_client.send.side_effect = RuntimeError("fila indisponível")

    response = client.post("/pedidos", json=VALID_PAYLOAD)

    assert response.status_code == 502
    assert "order_id" not in response.json()


def test_solicitar_pedido_accepts_batch_channel(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    payload = {
        **VALID_PAYLOAD,
        "channel": "BATCH",
        "source_file": "pedidos_20260719.txt",
        "source_line": 42,
    }

    response = client.post("/pedidos", json=payload)

    assert response.status_code == 202
    _, envelope = fake_sqs_client.send.call_args[0]
    assert envelope.payload["channel"] == "BATCH"
    assert envelope.payload["source_file"] == "pedidos_20260719.txt"
    assert envelope.payload["source_line"] == 42


def test_solicitar_pedido_integration_publishes_real_message_under_one_second(
    integration_client: TestClient,
) -> None:
    start = time.monotonic()
    response = integration_client.post("/pedidos", json=VALID_PAYLOAD)
    elapsed = time.monotonic() - start

    assert response.status_code == 202
    assert elapsed < 1.0

    from pedidos_shared import SqsClient

    from api_gateway.config import get_settings

    settings = get_settings()
    sqs = SqsClient(settings)
    messages = sqs.receive(settings.solicitar_pedido_queue_url)
    order_id = response.json()["order_id"]
    assert any(m.order_id == order_id for m in messages)
