"""Monta payloads publicados em validar_pedido_queue/pdf_request_queue (docs §5)."""

from typing import Any

from pedidos_shared import Order


def montar_payload_validacao(order: Order) -> dict[str, Any]:
    return {
        "customer_document": order.customer_document,
        "items": [
            {"product_id": item.product_id, "quantity": item.quantity} for item in order.items
        ],
    }


def montar_payload_pdf(order: Order) -> dict[str, Any]:
    return {
        "customer_name": order.customer_name,
        "customer_document": order.customer_document,
        "items": [item.model_dump(mode="json") for item in order.items],
        "subtotal": str(order.subtotal) if order.subtotal is not None else None,
        "discount_total": str(order.discount_total) if order.discount_total is not None else None,
        "total": str(order.total) if order.total is not None else None,
    }
