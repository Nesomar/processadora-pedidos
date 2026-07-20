"""Validacao de dados incompletos na solicitacao de nota fiscal (US2/FR-005, Clarifications)."""

_REQUIRED_ITEM_FIELDS = ("quantity", "unit_price", "discount_percentage", "line_total")
_REQUIRED_TOTAL_FIELDS = ("subtotal", "discount_total", "total")


def validar_solicitacao(payload: dict) -> str | None:
    if not payload.get("customer_name"):
        return "customer_name ausente"
    if not payload.get("customer_document"):
        return "customer_document ausente"

    items = payload.get("items") or []
    if not items:
        return "lista de itens vazia — nada para faturar"

    for index, item in enumerate(items):
        missing = [field for field in _REQUIRED_ITEM_FIELDS if item.get(field) is None]
        if missing:
            return f"item {index} sem campo(s) obrigatório(s): {', '.join(missing)}"

    missing_totals = [field for field in _REQUIRED_TOTAL_FIELDS if payload.get(field) is None]
    if missing_totals:
        return f"totais ausentes: {', '.join(missing_totals)}"

    return None
