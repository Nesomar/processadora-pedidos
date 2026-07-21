"""US1 — fluxo online feliz: POST /pedidos ate COMPLETED com nota fiscal (SC-001)."""

import uuid

from _poll import poll_until

_TERMINAL_STATUSES = {"COMPLETED", "REJECTED", "FAILED"}


def test_online_order_reaches_completed_with_invoice(api_gateway) -> None:
    payload = {
        "customer_id": f"CUST{uuid.uuid4().hex[:8]}",
        "customer_name": "Cliente E2E",
        "customer_document": "52998224725",
        "channel": "HTTP",
        "items": [{"product_id": 1, "quantity": 50}],
    }

    response = api_gateway.post("/pedidos", json=payload)
    assert response.status_code == 202
    order_id = response.json()["order_id"]

    def _consultar() -> dict | None:
        resposta = api_gateway.get(f"/pedidos/{order_id}")
        if resposta.status_code != 200:
            return None
        pedido = resposta.json()
        return pedido if pedido["status"] in _TERMINAL_STATUSES else None

    pedido = poll_until(
        _consultar, description=f"pedido {order_id} chegar a estado final"
    )

    assert pedido["status"] == "COMPLETED", pedido.get("status_reason")
    assert pedido["invoice_s3_key"]
    assert pedido["total"] is not None
    assert pedido["items"][0]["unit_price"] is not None
