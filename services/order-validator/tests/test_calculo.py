from decimal import Decimal

from order_validator.domain.calculo import calcular_item, calcular_totais
from order_validator.domain.modelos import ItemValidacao, Produto


def _produto(price: str = "9.99", discount: str = "10.00") -> Produto:
    return Produto(
        id=1,
        title="Produto",
        price=Decimal(price),
        stock=100,
        minimum_order_quantity=1,
        availability_status="In Stock",
        sku="SKU-1",
        discount_percentage=Decimal(discount),
    )


def test_calcular_item_enriquece_e_arredonda_line_total() -> None:
    item = calcular_item(ItemValidacao(product_id=1, quantity=3), _produto())

    assert item.unit_price == Decimal("9.99")
    assert item.discount_percentage == Decimal("10.00")
    assert item.line_total == Decimal("26.97")
    assert item.product_title == "Produto"
    assert item.product_sku == "SKU-1"


def test_calcular_totais_soma_subtotal_total_e_desconto() -> None:
    itens = [
        calcular_item(ItemValidacao(product_id=1, quantity=3), _produto()),
        calcular_item(ItemValidacao(product_id=1, quantity=2), _produto("10.00", "5.00")),
    ]

    assert calcular_totais(itens) == (
        Decimal("49.97"),
        Decimal("4.00"),
        Decimal("45.97"),
    )
