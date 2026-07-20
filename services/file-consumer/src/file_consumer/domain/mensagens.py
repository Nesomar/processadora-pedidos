"""Builder da mensagem publicada em pedido_lines_queue (data-model.md, research.md #5)."""

from pedidos_shared.file_layout import ParsedOrder

_CANCELAR_REASON = "Cancelamento via arquivo batch"


def montar_linha_pedido(source_file: str, order: ParsedOrder) -> dict:
    if order.operation == "CANCELAR":
        parsed: dict = {"reason": _CANCELAR_REASON}
    else:
        parsed = {
            "customer_id": order.customer_id,
            "customer_name": order.customer_name,
            "customer_document": order.customer_document,
            "channel": "BATCH",
            "items": [
                {"product_id": item.product_id, "quantity": item.quantity} for item in order.items
            ],
            "source_file": source_file,
            "source_line": order.line_number,
        }

    return {
        "source_file": source_file,
        "line_number": order.line_number,
        "operation": order.operation,
        "raw_line": order.raw_line,
        "order_id": order.order_id,
        "parsed": parsed,
    }
