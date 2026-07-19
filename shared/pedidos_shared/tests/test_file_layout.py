"""Teste de parse_file — arquivo válido e as 5 regras de rejeição (§6)."""

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


def test_parse_file_accepts_valid_file() -> None:
    result = parse_file(_load_lines())

    assert result.file_date == "20260718"
    assert result.origin_system == "SISTEMA_LEGADO_VENDAS"
    assert result.sequence == 1
    assert result.total_orders == 1
    assert result.total_items == 2
    assert len(result.orders) == 1

    order = result.orders[0]
    assert order.operation == "SOLICITAR"
    assert order.order_id is None
    assert order.customer_id == "CUST00001"
    assert order.customer_name == "MARIA SILVA"
    assert order.customer_document == "00012345678901"  # bruto, zero-padded a 14 (§6)
    assert order.item_count == 2
    assert [item.product_id for item in order.items] == [1, 16]
    assert [item.quantity for item in order.items] == [50, 10]


def test_parse_file_rejects_line_with_wrong_length() -> None:
    lines = _load_lines()
    lines[2] = lines[2][:-10]  # linha do item 1 encurtada

    with pytest.raises(LinhaInvalidaError):
        parse_file(lines)


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


def test_parse_file_rejects_orphan_item_record() -> None:
    lines = _load_lines()
    del lines[1]  # remove o registro tipo 1, deixando os itens órfãos

    with pytest.raises(LinhaInvalidaError):
        parse_file(lines)


def test_parse_file_rejects_order_with_divergent_item_count() -> None:
    lines = _load_lines()
    pedido = lines[1]
    corrupted = pedido[:141] + "05" + pedido[143:]
    assert len(corrupted) == 200
    lines[1] = corrupted

    with pytest.raises(PedidoInvalidoError):
        parse_file(lines)


def _record(record_type: str, *fields: tuple[str, int, str]) -> str:
    line = record_type
    for text, width, align in fields:
        line += text.rjust(width, "0") if align == "R0" else text.ljust(width)
    return line.ljust(200)


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
