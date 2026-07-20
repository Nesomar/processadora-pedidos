from pedidos_shared.file_layout import ParsedItem, ParsedOrder

from file_consumer.domain.mensagens import montar_linha_pedido


def test_montar_linha_pedido_solicitar_has_null_order_id_and_batch_channel() -> None:
    order = ParsedOrder(
        operation="SOLICITAR",
        order_id=None,
        customer_id="CUST00001",
        customer_name="MARIA SILVA",
        customer_document="00012345678901",
        item_count=1,
        line_number=2,
        raw_line="1SOLICITAR...",
        items=[ParsedItem(product_id=1, quantity=50)],
    )

    message = montar_linha_pedido("arquivo.txt", order)

    assert message["source_file"] == "arquivo.txt"
    assert message["line_number"] == 2
    assert message["operation"] == "SOLICITAR"
    assert message["raw_line"] == "1SOLICITAR..."
    assert message["order_id"] is None
    assert message["parsed"] == {
        "customer_id": "CUST00001",
        "customer_name": "MARIA SILVA",
        "customer_document": "00012345678901",
        "channel": "BATCH",
        "items": [{"product_id": 1, "quantity": 50}],
        "source_file": "arquivo.txt",
        "source_line": 2,
    }


def test_montar_linha_pedido_editar_keeps_order_id() -> None:
    order = ParsedOrder(
        operation="EDITAR",
        order_id="11111111-1111-1111-1111-111111111111",
        customer_id="CUST00002",
        customer_name="EMPRESA LTDA",
        customer_document="12345678000199",
        item_count=1,
        line_number=5,
        raw_line="1EDITAR...",
        items=[ParsedItem(product_id=5, quantity=3)],
    )

    message = montar_linha_pedido("arquivo.txt", order)

    assert message["order_id"] == "11111111-1111-1111-1111-111111111111"
    assert message["parsed"]["channel"] == "BATCH"
    assert message["parsed"]["items"] == [{"product_id": 5, "quantity": 3}]


def test_montar_linha_pedido_cancelar_uses_fixed_reason_and_ignores_items() -> None:
    order = ParsedOrder(
        operation="CANCELAR",
        order_id="22222222-2222-2222-2222-222222222222",
        customer_id="CUST00003",
        customer_name="CLIENTE TRES",
        customer_document="33333333333",
        item_count=1,
        line_number=9,
        raw_line="1CANCELAR...",
        items=[ParsedItem(product_id=9, quantity=1)],
    )

    message = montar_linha_pedido("arquivo.txt", order)

    assert message["order_id"] == "22222222-2222-2222-2222-222222222222"
    assert message["parsed"] == {"reason": "Cancelamento via arquivo batch"}
