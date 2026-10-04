"""Elegibilidade para download da nota fiscal — função pura, sem I/O (010-acesso-pdf-pedido)."""

from pedidos_shared import Order, OrderStatus

_SEM_PDF = {OrderStatus.REJECTED, OrderStatus.FAILED, OrderStatus.CANCELLED}


class NotaFiscalEmAndamentoError(Exception):
    """Pedido ainda em processamento — transitório (409)."""


class NotaFiscalIndisponivelError(Exception):
    """Pedido terminou sem PDF — permanente (410)."""


class NotaFiscalAusenteError(Exception):
    """Pedido `COMPLETED`, mas sem chave de PDF registrada (404)."""


def chave_da_nota_fiscal(order: Order) -> str:
    if order.status in _SEM_PDF:
        raise NotaFiscalIndisponivelError
    if order.status != OrderStatus.COMPLETED:
        raise NotaFiscalEmAndamentoError
    if order.invoice_s3_key is None:
        raise NotaFiscalAusenteError
    return order.invoice_s3_key
