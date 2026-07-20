"""Regra de quantidade minima do order-validator."""

from order_validator.domain.modelos import ErroValidacao, Produto


def validar_quantidade_minima(quantity: int, produto: Produto) -> ErroValidacao | None:
    if quantity >= produto.minimum_order_quantity:
        return None
    return ErroValidacao(
        code="BELOW_MINIMUM_ORDER_QUANTITY",
        product_id=produto.id,
        message=f"Quantidade {quantity} abaixo do minimo {produto.minimum_order_quantity}",
    )
