from decimal import Decimal

from order_validator.domain.limite_total import validar_limite_total


def test_validar_limite_total_accepts_below_limit() -> None:
    assert validar_limite_total(Decimal("99999.99")) is None


def test_validar_limite_total_accepts_equal_limit() -> None:
    assert validar_limite_total(Decimal("100000.00")) is None


def test_validar_limite_total_rejects_above_limit() -> None:
    error = validar_limite_total(Decimal("100000.01"))

    assert error is not None
    assert error.code == "ORDER_TOTAL_EXCEEDS_LIMIT"
    assert error.product_id is None
