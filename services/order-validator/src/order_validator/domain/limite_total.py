"""Regra de limite maximo do total do pedido."""

from decimal import Decimal

from order_validator.domain.modelos import ErroValidacao

_LIMIT = Decimal("100000.00")


def validar_limite_total(total: Decimal) -> ErroValidacao | None:
    if total <= _LIMIT:
        return None
    return ErroValidacao(
        code="ORDER_TOTAL_EXCEEDS_LIMIT",
        product_id=None,
        message=f"Total do pedido ({total:.2f}) excede o limite maximo de {_LIMIT:.2f}",
    )
