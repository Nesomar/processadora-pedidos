"""Builders dos payloads publicados em validar_pedido_response_queue."""

from decimal import Decimal

from order_validator.domain.modelos import ErroValidacao, ItemEnriquecido


def _decimal_to_str(value: Decimal) -> str:
    return f"{value:.2f}"


def _item_to_payload(item: ItemEnriquecido) -> dict:
    return {
        "product_id": item.product_id,
        "quantity": item.quantity,
        "unit_price": _decimal_to_str(item.unit_price),
        "discount_percentage": _decimal_to_str(item.discount_percentage),
        "line_total": _decimal_to_str(item.line_total),
        "product_title": item.product_title,
        "product_sku": item.product_sku,
    }


def montar_resposta_aprovada(
    itens: list[ItemEnriquecido], subtotal: Decimal, discount_total: Decimal, total: Decimal
) -> dict:
    return {
        "approved": True,
        "errors": [],
        "enriched_items": [_item_to_payload(item) for item in itens],
        "subtotal": _decimal_to_str(subtotal),
        "discount_total": _decimal_to_str(discount_total),
        "total": _decimal_to_str(total),
    }


def montar_resposta_reprovada(erros: list[ErroValidacao]) -> dict:
    return {
        "approved": False,
        "errors": [
            {"code": erro.code, "product_id": erro.product_id, "message": erro.message}
            for erro in erros
        ],
        "enriched_items": None,
        "subtotal": None,
        "discount_total": None,
        "total": None,
    }
