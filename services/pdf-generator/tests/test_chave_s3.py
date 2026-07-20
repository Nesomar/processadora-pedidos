from datetime import UTC, datetime

from pdf_generator.domain.chave_s3 import montar_chave_invoice


def test_montar_chave_invoice_formata_data_com_zero_a_esquerda() -> None:
    momento = datetime(2026, 7, 5, 10, 30, tzinfo=UTC)

    chave = montar_chave_invoice("order-123", momento)

    assert chave == "invoices/2026/07/05/order-123.pdf"


def test_montar_chave_invoice_usa_o_momento_recebido_nao_o_relogio_atual() -> None:
    momento = datetime(2020, 1, 1, tzinfo=UTC)

    chave = montar_chave_invoice("abc", momento)

    assert chave.startswith("invoices/2020/01/01/")
