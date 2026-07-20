from decimal import Decimal

from order_validator.domain.modelos import Produto
from order_validator.domain.quantidade_minima import validar_quantidade_minima


def _produto(minimum: int = 5) -> Produto:
    return Produto(1, "Produto", Decimal("10.00"), 10, minimum, "In Stock", "SKU", Decimal("0"))


def test_validar_quantidade_minima_accepts_equal_or_above_minimum() -> None:
    assert validar_quantidade_minima(5, _produto()) is None
    assert validar_quantidade_minima(6, _produto()) is None


def test_validar_quantidade_minima_rejects_below_minimum() -> None:
    error = validar_quantidade_minima(4, _produto())

    assert error is not None
    assert error.code == "BELOW_MINIMUM_ORDER_QUANTITY"
    assert error.product_id == 1
