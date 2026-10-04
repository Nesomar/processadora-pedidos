"""Teste da função pura chave_da_nota_fiscal (010-acesso-pdf-pedido)."""

from datetime import UTC, datetime

import pytest
from pedidos_shared import Order, OrderStatus

from api_gateway.domain.nota_fiscal import (
    NotaFiscalAusenteError,
    NotaFiscalEmAndamentoError,
    NotaFiscalIndisponivelError,
    chave_da_nota_fiscal,
)


def _order(status: OrderStatus, chave: str | None = None) -> Order:
    now = datetime.now(UTC)
    return Order(
        order_id="11111111-1111-1111-1111-111111111111",
        customer_id="CUST00001",
        customer_name="Maria Silva",
        customer_document="12345678901",
        channel="HTTP",
        items=[{"product_id": 1, "quantity": 1}],
        status=status,
        status_reason="motivo",
        invoice_s3_key=chave,
        correlation_id="22222222-2222-2222-2222-222222222222",
        created_at=now,
        updated_at=now,
        version=0,
    )


def test_completed_com_chave_devolve_chave() -> None:
    assert chave_da_nota_fiscal(_order(OrderStatus.COMPLETED, "invoices/a.pdf")) == "invoices/a.pdf"


def test_completed_sem_chave_levanta_ausente() -> None:
    with pytest.raises(NotaFiscalAusenteError):
        chave_da_nota_fiscal(_order(OrderStatus.COMPLETED))


@pytest.mark.parametrize(
    "status",
    [
        OrderStatus.RECEIVED,
        OrderStatus.PROCESSING,
        OrderStatus.VALIDATING,
        OrderStatus.VALIDATED,
        OrderStatus.INVOICING,
    ],
)
def test_em_andamento_ignora_chave_antiga(status: OrderStatus) -> None:
    with pytest.raises(NotaFiscalEmAndamentoError):
        chave_da_nota_fiscal(_order(status, "invoices/velha.pdf"))


@pytest.mark.parametrize(
    "status", [OrderStatus.REJECTED, OrderStatus.FAILED, OrderStatus.CANCELLED]
)
def test_terminal_sem_pdf_levanta_indisponivel(status: OrderStatus) -> None:
    with pytest.raises(NotaFiscalIndisponivelError):
        chave_da_nota_fiscal(_order(status))
