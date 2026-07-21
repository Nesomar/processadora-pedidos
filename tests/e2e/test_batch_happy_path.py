"""US3 — arquivo posicional valido cria pedido via batch (File Consumer -> Lambda Line
Processor -> API Gateway -> Order Processor), SC-001."""

import uuid

from _file_builder import montar_arquivo_valido
from _poll import poll_until


def test_valid_file_upload_creates_batch_order(
    api_gateway, s3_client, settings
) -> None:
    customer_id = f"CUST{uuid.uuid4().hex[:8]}"
    key = f"uploads/e2e-{uuid.uuid4().hex[:8]}.txt"
    conteudo = montar_arquivo_valido(customer_id, product_id=1, quantity=50)

    s3_client.put_object(settings.pedidos_bucket_name, key, conteudo)

    def _consultar() -> list | None:
        resposta = api_gateway.get("/pedidos", params={"customerId": customer_id})
        if resposta.status_code != 200:
            return None
        pedidos = resposta.json()["pedidos"]
        return pedidos or None

    pedidos = poll_until(
        _consultar, description=f"pedido do arquivo {key} ser criado para {customer_id}"
    )

    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido["channel"] == "BATCH"
    assert pedido["source_file"] == key
    assert pedido["source_line"] == 2
