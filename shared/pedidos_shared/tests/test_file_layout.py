"""Teste de parse_file — arquivo válido e as regras de rejeição/tolerância (§6)."""

from pathlib import Path

import pytest

from pedidos_shared.file_layout import (
    ArquivoInvalidoError,
    LinhaInvalidaError,
    PedidoInvalidoError,
    parse_file,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "exemplo.txt"


def _load_lines() -> list[str]:
    return FIXTURE_PATH.read_text(encoding="utf-8").splitlines()


def _record(record_type: str, *fields: tuple[str, int, str]) -> str:
    line = record_type
    for text, width, align in fields:
        line += text.rjust(width, "0") if align == "R0" else text.ljust(width)
    return line.ljust(200)


def _order_record(operation: str, order_id: str, customer_id: str, item_count: int) -> str:
    return _record(
        "1",
        (operation, 10, "L"),
        (order_id, 36, "L"),
        (customer_id, 20, "L"),
        (f"CLIENTE {customer_id}", 60, "L"),
        ("11111111111", 14, "R0"),
        (str(item_count), 2, "R0"),
    )


def _item_record(product_id: int, quantity: int) -> str:
    return _record("2", (str(product_id), 8, "R0"), (str(quantity), 8, "R0"))


def test_parse_file_accepts_valid_file() -> None:
    result = parse_file(_load_lines())

    assert result.file_date == "20260718"
    assert result.origin_system == "SISTEMA_LEGADO_VENDAS"
    assert result.sequence == 1
    assert result.total_orders == 1
    assert result.total_items == 2
    assert len(result.orders) == 1
    assert result.errors == []

    order = result.orders[0]
    assert order.operation == "SOLICITAR"
    assert order.order_id is None
    assert order.customer_id == "CUST00001"
    assert order.customer_name == "MARIA SILVA"
    assert order.customer_document == "00012345678901"  # bruto, zero-padded a 14 (§6)
    assert order.item_count == 2
    assert [item.product_id for item in order.items] == [1, 16]
    assert [item.quantity for item in order.items] == [50, 10]


def test_parse_file_rejects_missing_header() -> None:
    lines = _load_lines()
    lines[0] = "5" + lines[0][1:]  # record_type inválido no lugar do header

    with pytest.raises(ArquivoInvalidoError):
        parse_file(lines)


def test_parse_file_rejects_missing_trailer() -> None:
    lines = _load_lines()
    del lines[-1]

    with pytest.raises(ArquivoInvalidoError):
        parse_file(lines)


def test_parse_file_rejects_divergent_trailer_counters() -> None:
    lines = _load_lines()
    trailer = lines[-1]
    corrupted = trailer[0:1] + "00000001" + "00000099" + trailer[17:]
    assert len(corrupted) == 200
    lines[-1] = corrupted

    with pytest.raises(ArquivoInvalidoError):
        parse_file(lines)


def test_parse_file_rejects_whole_file_when_order_record_missing_breaks_trailer_count() -> None:
    """Remover o registro tipo 1 inteiro faz a contagem bruta de pedidos não bater com o
    rodapé — isso ainda invalida o arquivo inteiro (diferente de um item órfão isolado, ver
    test_parse_file_tolerates_orphan_item_when_trailer_counts_still_match)."""
    lines = _load_lines()
    del lines[1]  # remove o registro tipo 1, deixando os itens órfãos

    with pytest.raises(ArquivoInvalidoError):
        parse_file(lines)


def test_parse_file_tolerates_line_with_wrong_length_and_rejects_only_that_order() -> None:
    lines = _load_lines()
    lines[2] = lines[2][:-10]  # linha do item 1 encurtada, mas ainda começa com "2"

    result = parse_file(lines)

    assert result.orders == []
    assert len(result.errors) == 2
    assert isinstance(result.errors[0], LinhaInvalidaError)
    assert isinstance(result.errors[1], PedidoInvalidoError)


def test_parse_file_tolerates_orphan_item_when_trailer_counts_still_match() -> None:
    header = _record("0", ("20260720", 8, "L"), ("TESTE", 30, "L"), ("1", 6, "R0"))
    orphan_item = _item_record(99, 1)
    order_1 = _order_record("SOLICITAR", "", "CUST00001", item_count=1)
    item_1 = _item_record(1, 10)
    order_2 = _order_record("SOLICITAR", "", "CUST00002", item_count=1)
    item_2 = _item_record(2, 20)
    trailer = _record("9", ("2", 8, "R0"), ("3", 8, "R0"))

    result = parse_file([header, orphan_item, order_1, item_1, order_2, item_2, trailer])

    assert [order.customer_id for order in result.orders] == ["CUST00001", "CUST00002"]
    assert len(result.errors) == 1
    assert isinstance(result.errors[0], LinhaInvalidaError)


def test_parse_file_rejects_order_with_divergent_item_count_but_keeps_other_orders() -> None:
    header = _record("0", ("20260720", 8, "L"), ("TESTE", 30, "L"), ("1", 6, "R0"))
    order_ok_1, item_ok_1 = (
        _order_record("SOLICITAR", "", "CUST00001", item_count=1),
        _item_record(1, 1),
    )
    order_bad = _order_record("SOLICITAR", "", "CUST00002", item_count=2)
    item_bad = _item_record(2, 1)
    order_ok_2, item_ok_2 = (
        _order_record("SOLICITAR", "", "CUST00003", item_count=1),
        _item_record(3, 1),
    )
    order_ok_3, item_ok_3 = (
        _order_record("SOLICITAR", "", "CUST00004", item_count=1),
        _item_record(4, 1),
    )
    trailer = _record("9", ("4", 8, "R0"), ("4", 8, "R0"))

    result = parse_file(
        [
            header,
            order_ok_1,
            item_ok_1,
            order_bad,
            item_bad,
            order_ok_2,
            item_ok_2,
            order_ok_3,
            item_ok_3,
            trailer,
        ]
    )

    assert [order.customer_id for order in result.orders] == ["CUST00001", "CUST00003", "CUST00004"]
    assert len(result.errors) == 1
    assert isinstance(result.errors[0], PedidoInvalidoError)


def test_parse_file_parses_editar_operation_with_cnpj_and_order_id() -> None:
    header = _record("0", ("20260719", 8, "L"), ("SISTEMA_LEGADO_VENDAS", 30, "L"), ("2", 6, "R0"))
    pedido = _record(
        "1",
        ("EDITAR", 10, "L"),
        ("11111111-1111-1111-1111-111111111111", 36, "L"),
        ("CUST00002", 20, "L"),
        ("EMPRESA LTDA", 60, "L"),
        ("12345678000199", 14, "R0"),
        ("1", 2, "R0"),
    )
    item = _record("2", ("5", 8, "R0"), ("3", 8, "R0"))
    trailer = _record("9", ("1", 8, "R0"), ("1", 8, "R0"))

    result = parse_file([header, pedido, item, trailer])

    order = result.orders[0]
    assert order.operation == "EDITAR"
    assert order.order_id == "11111111-1111-1111-1111-111111111111"
    assert order.customer_document == "12345678000199"  # CNPJ de 14 dígitos, sem padding
