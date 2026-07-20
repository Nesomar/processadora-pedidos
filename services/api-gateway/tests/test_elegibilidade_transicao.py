"""Teste de elegibilidade_transicao — reaproveita is_valid_transition (research.md #2, FR-006)."""

import pytest
from pedidos_shared import OrderStatus

from api_gateway.domain.elegibilidade_transicao import pode_cancelar, pode_editar

EDITAVEIS = {OrderStatus.RECEIVED, OrderStatus.VALIDATED, OrderStatus.REJECTED}
CANCELAVEIS = {
    OrderStatus.RECEIVED,
    OrderStatus.PROCESSING,
    OrderStatus.VALIDATING,
    OrderStatus.VALIDATED,
}


@pytest.mark.parametrize("status", list(OrderStatus))
def test_pode_editar_matches_fr006(status: OrderStatus) -> None:
    assert pode_editar(status) is (status in EDITAVEIS)


@pytest.mark.parametrize("status", list(OrderStatus))
def test_pode_cancelar_matches_fr006(status: OrderStatus) -> None:
    assert pode_cancelar(status) is (status in CANCELAVEIS)
