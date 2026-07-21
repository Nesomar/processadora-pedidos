"""US4 — editar um pedido reflete os novos dados e reinicia o ciclo (SC-001).

Cria o pedido com documento invalido (chega a REJECTED de forma rapida e confiavel), edita com um
documento valido, e confirma que o novo ciclo de validacao usa os dados corrigidos -- prova que a
edicao realmente reflete e reprocessa, nao so aceita a requisicao sem efeito.

Importante: o status REJECTED do ciclo original ainda esta la no instante da edicao -- o poll pos
edicao precisa esperar a `version` do registro avancar (nao so "algum status terminal"), senao
observaria o REJECTED antigo antes do reprocessamento realmente acontecer.
"""

import uuid

from _poll import poll_until

_TERMINAL_STATUSES = {"COMPLETED", "REJECTED", "FAILED"}


def _poll_terminal(api_gateway, order_id: str, apos_version: int = -1) -> dict:
    def _consultar() -> dict | None:
        resposta = api_gateway.get(f"/pedidos/{order_id}")
        if resposta.status_code != 200:
            return None
        pedido = resposta.json()
        if pedido["version"] <= apos_version:
            return None
        return pedido if pedido["status"] in _TERMINAL_STATUSES else None

    return poll_until(
        _consultar, description=f"pedido {order_id} chegar a estado final"
    )


def test_editing_order_reflects_new_data_and_reprocesses(api_gateway) -> None:
    payload = {
        "customer_id": f"CUST{uuid.uuid4().hex[:8]}",
        "customer_name": "Cliente E2E",
        "customer_document": "11111111111",  # invalido de proposito -- reprova rapido
        "channel": "HTTP",
        "items": [{"product_id": 1, "quantity": 50}],
    }
    order_id = api_gateway.post("/pedidos", json=payload).json()["order_id"]

    rejeitado = _poll_terminal(api_gateway, order_id)
    assert rejeitado["status"] == "REJECTED"

    edicao = {**payload, "customer_document": "52998224725"}  # agora valido
    edit_response = api_gateway.put(f"/pedidos/{order_id}", json=edicao)
    assert edit_response.status_code == 202

    pedido = _poll_terminal(api_gateway, order_id, apos_version=rejeitado["version"])

    assert pedido["status"] == "COMPLETED", pedido.get("status_reason")
    assert pedido["invoice_s3_key"]
