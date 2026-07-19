"""Testes de OrderStatus e is_valid_transition contra a tabela de data-model.md (§2.3)."""

import itertools

import pytest

from pedidos_shared.status import OrderStatus, is_valid_transition

VALID_TRANSITIONS: set[tuple[OrderStatus, OrderStatus]] = {
    (OrderStatus.RECEIVED, OrderStatus.PROCESSING),
    (OrderStatus.PROCESSING, OrderStatus.VALIDATING),
    (OrderStatus.VALIDATING, OrderStatus.VALIDATED),
    (OrderStatus.VALIDATING, OrderStatus.REJECTED),
    (OrderStatus.VALIDATED, OrderStatus.INVOICING),
    (OrderStatus.INVOICING, OrderStatus.COMPLETED),
    (OrderStatus.INVOICING, OrderStatus.FAILED),
    # cancelamento a partir de qualquer estado não-terminal anterior ao faturamento
    (OrderStatus.RECEIVED, OrderStatus.CANCELLED),
    (OrderStatus.PROCESSING, OrderStatus.CANCELLED),
    (OrderStatus.VALIDATING, OrderStatus.CANCELLED),
    (OrderStatus.VALIDATED, OrderStatus.CANCELLED),
    # edição reinicia o ciclo
    (OrderStatus.RECEIVED, OrderStatus.PROCESSING),
    (OrderStatus.VALIDATED, OrderStatus.PROCESSING),
    (OrderStatus.REJECTED, OrderStatus.PROCESSING),
    # qualquer não-terminal -> FAILED (erro técnico)
    (OrderStatus.RECEIVED, OrderStatus.FAILED),
    (OrderStatus.PROCESSING, OrderStatus.FAILED),
    (OrderStatus.VALIDATING, OrderStatus.FAILED),
    (OrderStatus.VALIDATED, OrderStatus.FAILED),
}

ALL_PAIRS = list(itertools.product(OrderStatus, OrderStatus))


@pytest.mark.parametrize("current,next_", ALL_PAIRS)
def test_is_valid_transition_matches_domain_table(current: OrderStatus, next_: OrderStatus) -> None:
    expected = (current, next_) in VALID_TRANSITIONS
    assert is_valid_transition(current, next_) is expected


def test_terminal_states_have_no_outgoing_transition_except_rejected_reopen() -> None:
    for terminal in (OrderStatus.COMPLETED, OrderStatus.CANCELLED, OrderStatus.FAILED):
        for target in OrderStatus:
            assert is_valid_transition(terminal, target) is False

    assert is_valid_transition(OrderStatus.REJECTED, OrderStatus.PROCESSING) is True
    for target in OrderStatus:
        if target is not OrderStatus.PROCESSING:
            assert is_valid_transition(OrderStatus.REJECTED, target) is False
