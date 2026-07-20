"""Calculos monetarios puros do order-validator."""

from decimal import ROUND_HALF_UP, Decimal

from order_validator.domain.modelos import ItemEnriquecido, ItemValidacao, Produto

_CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def calcular_item(item: ItemValidacao, produto: Produto) -> ItemEnriquecido:
    discount_factor = Decimal("1") - (produto.discount_percentage / Decimal("100"))
    line_total = _money(Decimal(item.quantity) * produto.price * discount_factor)
    return ItemEnriquecido(
        product_id=item.product_id,
        quantity=item.quantity,
        unit_price=_money(produto.price),
        discount_percentage=_money(produto.discount_percentage),
        line_total=line_total,
        product_title=produto.title,
        product_sku=produto.sku,
    )


def calcular_totais(itens: list[ItemEnriquecido]) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = _money(sum((Decimal(i.quantity) * i.unit_price for i in itens), Decimal("0")))
    total = _money(sum((i.line_total for i in itens), Decimal("0")))
    discount_total = _money(subtotal - total)
    return subtotal, discount_total, total
