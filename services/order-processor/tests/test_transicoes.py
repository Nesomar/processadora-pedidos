"""Teste de domain/transicoes.py — wrappers finos sobre is_valid_transition (research.md #5)."""

import pytest
from pedidos_shared import OrderStatus

from order_processor.domain.transicoes import (
    TransicaoInvalidaError,
    aplicar_cancelamento,
    aplicar_edicao,
    aplicar_resposta_pdf,
    aplicar_resposta_validacao,
    aplicar_solicitacao,
)

EDITAVEIS = {OrderStatus.RECEIVED, OrderStatus.VALIDATED, OrderStatus.REJECTED}
CANCELAVEIS = {
    OrderStatus.RECEIVED,
    OrderStatus.PROCESSING,
    OrderStatus.VALIDATING,
    OrderStatus.VALIDATED,
}


def test_aplicar_solicitacao_always_results_in_validating() -> None:
    assert aplicar_solicitacao() == OrderStatus.VALIDATING


def test_aplicar_resposta_validacao_approved_results_in_invoicing() -> None:
    assert (
        aplicar_resposta_validacao(OrderStatus.VALIDATING, approved=True) == OrderStatus.INVOICING
    )


def test_aplicar_resposta_validacao_rejected_results_in_rejected() -> None:
    assert (
        aplicar_resposta_validacao(OrderStatus.VALIDATING, approved=False) == OrderStatus.REJECTED
    )


@pytest.mark.parametrize("status", [s for s in OrderStatus if s != OrderStatus.VALIDATING])
def test_aplicar_resposta_validacao_raises_when_not_validating(status: OrderStatus) -> None:
    with pytest.raises(TransicaoInvalidaError):
        aplicar_resposta_validacao(status, approved=True)
    with pytest.raises(TransicaoInvalidaError):
        aplicar_resposta_validacao(status, approved=False)


def test_aplicar_resposta_pdf_success_results_in_completed() -> None:
    assert aplicar_resposta_pdf(OrderStatus.INVOICING, success=True) == OrderStatus.COMPLETED


def test_aplicar_resposta_pdf_failure_results_in_failed() -> None:
    assert aplicar_resposta_pdf(OrderStatus.INVOICING, success=False) == OrderStatus.FAILED


@pytest.mark.parametrize("status", [s for s in OrderStatus if s != OrderStatus.INVOICING])
def test_aplicar_resposta_pdf_success_raises_when_not_invoicing(status: OrderStatus) -> None:
    with pytest.raises(TransicaoInvalidaError):
        aplicar_resposta_pdf(status, success=True)


@pytest.mark.parametrize("status", [s for s in OrderStatus if s != OrderStatus.INVOICING])
def test_aplicar_resposta_pdf_failure_raises_when_not_invoicing(status: OrderStatus) -> None:
    # is_valid_transition(_, FAILED) é verdadeiro pra qualquer não-terminal (regra "erro técnico
    # esgota retries" de §2.3) — aplicar_resposta_pdf precisa checar INVOICING explicitamente pra
    # não aceitar resposta de PDF vinda de qualquer estado ativo.
    with pytest.raises(TransicaoInvalidaError):
        aplicar_resposta_pdf(status, success=False)


@pytest.mark.parametrize("status", list(OrderStatus))
def test_aplicar_edicao_matches_fr008(status: OrderStatus) -> None:
    if status in EDITAVEIS:
        assert aplicar_edicao(status) == OrderStatus.VALIDATING
    else:
        with pytest.raises(TransicaoInvalidaError):
            aplicar_edicao(status)


@pytest.mark.parametrize("status", list(OrderStatus))
def test_aplicar_cancelamento_matches_fr009(status: OrderStatus) -> None:
    if status in CANCELAVEIS:
        assert aplicar_cancelamento(status) == OrderStatus.CANCELLED
    else:
        with pytest.raises(TransicaoInvalidaError):
            aplicar_cancelamento(status)
