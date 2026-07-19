"""Parser do layout posicional fixo (docs/01-dominio-e-contratos.md §6)."""

from dataclasses import dataclass, field

_LINE_LENGTH = 200


class ArquivoInvalidoError(Exception):
    """Header/trailer ausente ou inválido; contadores do trailer divergentes."""


class LinhaInvalidaError(Exception):
    """Linha com tamanho diferente de 200; registro tipo `2` sem tipo `1` antecedente."""


class PedidoInvalidoError(Exception):
    """`item_count` do pedido diverge da quantidade real de registros tipo `2`."""


@dataclass
class ParsedItem:
    product_id: int
    quantity: int


@dataclass
class ParsedOrder:
    operation: str
    order_id: str | None
    customer_id: str
    customer_name: str
    customer_document: str
    item_count: int
    items: list[ParsedItem] = field(default_factory=list)


@dataclass
class ParsedFile:
    file_date: str
    origin_system: str
    sequence: int
    total_orders: int
    total_items: int
    orders: list[ParsedOrder]


def _parse_header(line: str) -> tuple[str, str, int]:
    file_date = line[1:9]
    origin_system = line[9:39].rstrip()
    sequence = int(line[39:45])
    return file_date, origin_system, sequence


def _parse_order(line: str) -> ParsedOrder:
    operation = line[1:11].rstrip()
    order_id = line[11:47].strip() or None
    customer_id = line[47:67].rstrip()
    customer_name = line[67:127].rstrip()
    # campo bruto do arquivo: numérico, zero-padded a 14 posições (§6). CPF (11 dígitos) e CNPJ
    # (14 dígitos) não são distinguíveis aqui sem outro campo indicador — o parser não adivinha;
    # quem consome ParsedOrder decide como interpretar o padding.
    customer_document = line[127:141]
    item_count = int(line[141:143])
    return ParsedOrder(
        operation=operation,
        order_id=order_id,
        customer_id=customer_id,
        customer_name=customer_name,
        customer_document=customer_document,
        item_count=item_count,
    )


def _parse_item(line: str) -> ParsedItem:
    product_id = int(line[1:9])
    quantity = int(line[9:17])
    return ParsedItem(product_id=product_id, quantity=quantity)


def _parse_trailer(line: str) -> tuple[int, int]:
    total_orders = int(line[1:9])
    total_items = int(line[9:17])
    return total_orders, total_items


def parse_file(lines: list[str]) -> ParsedFile:
    """Faz o parse de um arquivo posicional completo (linhas com `\\n` opcional).

    Levanta `ArquivoInvalidoError`, `LinhaInvalidaError` ou `PedidoInvalidoError` conforme as 5
    regras de parsing de §6.
    """
    rows = [raw.rstrip("\r\n") for raw in lines]

    for row in rows:
        if len(row) != _LINE_LENGTH:
            raise LinhaInvalidaError(f"linha com {len(row)} caracteres (esperado {_LINE_LENGTH})")

    if not rows or rows[0][0:1] != "0":
        raise ArquivoInvalidoError("header ausente ou inválido")
    if rows[-1][0:1] != "9":
        raise ArquivoInvalidoError("trailer ausente ou inválido")

    file_date, origin_system, sequence = _parse_header(rows[0])
    total_orders, total_items = _parse_trailer(rows[-1])

    orders: list[ParsedOrder] = []
    current_order: ParsedOrder | None = None

    def finalize(order: ParsedOrder) -> None:
        if len(order.items) != order.item_count:
            raise PedidoInvalidoError(
                f"pedido {order.order_id!r}: item_count={order.item_count} mas "
                f"{len(order.items)} item(ns) encontrado(s)"
            )
        orders.append(order)

    for row in rows[1:-1]:
        record_type = row[0:1]
        if record_type == "1":
            if current_order is not None:
                finalize(current_order)
            current_order = _parse_order(row)
        elif record_type == "2":
            if current_order is None:
                raise LinhaInvalidaError("registro tipo 2 sem tipo 1 antecedente (item órfão)")
            current_order.items.append(_parse_item(row))
        else:
            raise LinhaInvalidaError(f"record_type desconhecido: {record_type!r}")

    if current_order is not None:
        finalize(current_order)

    if total_orders != len(orders):
        raise ArquivoInvalidoError(
            f"trailer indica total_orders={total_orders}, contado={len(orders)}"
        )

    counted_items = sum(len(order.items) for order in orders)
    if total_items != counted_items:
        raise ArquivoInvalidoError(
            f"trailer indica total_items={total_items}, contado={counted_items}"
        )

    return ParsedFile(
        file_date=file_date,
        origin_system=origin_system,
        sequence=sequence,
        total_orders=total_orders,
        total_items=total_items,
        orders=orders,
    )
