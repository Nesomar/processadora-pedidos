from unittest.mock import MagicMock

import pytest

from pdf_generator.adapters.armazenamento import salvar_pdf


def test_salvar_pdf_calls_put_object_with_content_type() -> None:
    fake_s3 = MagicMock()

    salvar_pdf(fake_s3, "bucket", "invoices/2026/07/20/order-1.pdf", b"%PDF-")

    fake_s3.put_object.assert_called_once_with(
        "bucket", "invoices/2026/07/20/order-1.pdf", b"%PDF-", content_type="application/pdf"
    )


def test_salvar_pdf_propagates_s3_client_exceptions() -> None:
    fake_s3 = MagicMock()
    fake_s3.put_object.side_effect = RuntimeError("s3 indisponivel")

    with pytest.raises(RuntimeError, match="s3 indisponivel"):
        salvar_pdf(fake_s3, "bucket", "invoices/2026/07/20/order-1.pdf", b"%PDF-")
