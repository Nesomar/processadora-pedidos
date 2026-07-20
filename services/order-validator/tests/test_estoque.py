from decimal import Decimal

from order_validator.domain.estoque import validar_estoque
from order_validator.domain.modelos import Produto


def _produto(stock: int = 10, status: str = "In Stock") -> Produto:
    return Produto(1, "Produto", Decimal("10.00"), stock, 1, status, "SKU", Decimal("0"))


def test_validar_estoque_accepts_available_quantity() -> None:
    assert validar_estoque(10, _produto()) is None


def test_validar_estoque_rejects_quantity_above_stock() -> None:
    error = validar_estoque(11, _produto(stock=10))

    assert error is not None
    assert error.code == "INSUFFICIENT_STOCK"
    assert error.product_id == 1


def test_validar_estoque_rejects_out_of_stock_status() -> None:
    error = validar_estoque(1, _produto(stock=10, status="Out of Stock"))

    assert error is not None
    assert error.code == "INSUFFICIENT_STOCK"
