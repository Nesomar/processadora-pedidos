"""US5 — cancelar um pedido existente o leva a CANCELLED (SC-001)."""

import uuid

from _poll import poll_until

_TERMINAL_STATUSES = {"COMPLETED", "REJECTED", "FAILED", "CANCELLED"}


def test_cancelling_order_reaches_cancelled(api_gateway) -> None:
    payload = {
        "customer_id": f"CUST{uuid.uuid4().hex[:8]}",
        "customer_name": "Cliente E2E",
        "customer_document": "52998224725",
        "channel": "HTTP",
        "items": [{"product_id": 1, "quantity": 50}],
    }
    order_id = api_gateway.post("/pedidos", json=payload).json()["order_id"]

    # POST /pedidos so publica o comando -- o registro so existe apos o Order Processor
    # consumir solicitar_pedido_queue (processamento assincrono).
    poll_until(
        lambda: api_gateway.get(f"/pedidos/{order_id}").status_code == 200,
        description=f"pedido {order_id} existir apos criacao",
    )

    cancel_response = api_gateway.post(
        f"/pedidos/{order_id}/cancelamento", json={"reason": "Teste e2e"}
    )
    assert cancel_response.status_code == 202

    def _consultar() -> dict | None:
        resposta = api_gateway.get(f"/pedidos/{order_id}")
        if resposta.status_code != 200:
            return None
        pedido = resposta.json()
        return pedido if pedido["status"] in _TERMINAL_STATUSES else None

    pedido = poll_until(
        _consultar, description=f"pedido {order_id} chegar a estado final"
    )

    assert pedido["status"] == "CANCELLED"
