"""Builder de arquivo posicional parametrizavel (research.md #4).

Mesma logica de `services/file-consumer/tests/*` e
`shared/pedidos_shared/tests/test_file_layout.py`, mas com `customer_id` parametrizavel —
`infra/bootstrap/seed_file.py` gera sempre o mesmo `CUST00001` fixo, inadequado para um teste que
precisa de identificador unico por execucao (FR-004).
"""

from datetime import UTC, datetime


def _record(record_type: str, *fields: tuple[str, int, str]) -> str:
    line = record_type
    for text, width, align in fields:
        line += text.rjust(width, "0") if align == "R0" else text.ljust(width)
    return line.ljust(200)


def montar_arquivo_valido(customer_id: str, product_id: int, quantity: int) -> bytes:
    today = datetime.now(UTC).strftime("%Y%m%d")

    header = _record("0", (today, 8, "L"), ("E2E_TESTS", 30, "L"), ("1", 6, "R0"))
    pedido = _record(
        "1",
        ("SOLICITAR", 10, "L"),
        ("", 36, "L"),
        (customer_id, 20, "L"),
        ("Cliente E2E", 60, "L"),
        ("52998224725", 14, "R0"),
        ("1", 2, "R0"),
    )
    item = _record("2", (str(product_id), 8, "R0"), (str(quantity), 8, "R0"))
    trailer = _record("9", ("1", 8, "R0"), ("1", 8, "R0"))

    return ("\n".join([header, pedido, item, trailer]) + "\n").encode("utf-8")
