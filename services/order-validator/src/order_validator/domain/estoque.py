"""Regra de estoque do order-validator."""

from order_validator.domain.modelos import ErroValidacao, Produto


def validar_estoque(quantity: int, produto: Produto) -> ErroValidacao | None:
    if produto.availability_status == "Out of Stock":
        return ErroValidacao(
            code="INSUFFICIENT_STOCK",
            product_id=produto.id,
            message=f"Produto {produto.id} indisponivel em estoque",
        )
    if quantity > produto.stock:
        return ErroValidacao(
            code="INSUFFICIENT_STOCK",
            product_id=produto.id,
            message=f"Quantidade {quantity} excede o estoque disponivel ({produto.stock})",
        )
    return None
