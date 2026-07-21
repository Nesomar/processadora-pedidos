"""Mapeamento operacao -> chamada HTTP ao API Gateway (data-model.md, research.md #3)."""


class ComandoInvalidoError(Exception):
    """`operation` desconhecida ou `order_id` ausente para EDITAR/CANCELAR."""


def montar_chamada(body: dict) -> tuple[str, str, dict]:
    operation = body.get("operation")
    order_id = body.get("order_id")
    parsed = body.get("parsed")

    if operation == "SOLICITAR":
        return "POST", "/pedidos", parsed

    if operation == "EDITAR":
        if not order_id:
            raise ComandoInvalidoError("EDITAR sem order_id")
        return "PUT", f"/pedidos/{order_id}", parsed

    if operation == "CANCELAR":
        if not order_id:
            raise ComandoInvalidoError("CANCELAR sem order_id")
        return "POST", f"/pedidos/{order_id}/cancelamento", parsed

    raise ComandoInvalidoError(f"operation desconhecida: {operation!r}")
