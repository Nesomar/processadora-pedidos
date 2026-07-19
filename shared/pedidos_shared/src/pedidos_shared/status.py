"""Máquina de estados do pedido (docs/01-dominio-e-contratos.md §2.3)."""

from enum import StrEnum


class OrderStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    INVOICING = "INVOICING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


_TERMINAL_STATES = {
    OrderStatus.COMPLETED,
    OrderStatus.CANCELLED,
    OrderStatus.REJECTED,
    OrderStatus.FAILED,
}

_CANCELLABLE_FROM = {
    OrderStatus.RECEIVED,
    OrderStatus.PROCESSING,
    OrderStatus.VALIDATING,
    OrderStatus.VALIDATED,
}

_REOPEN_TO_PROCESSING_FROM = {
    OrderStatus.RECEIVED,
    OrderStatus.VALIDATED,
    OrderStatus.REJECTED,
}

_BASE_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.RECEIVED: {OrderStatus.PROCESSING},
    OrderStatus.PROCESSING: {OrderStatus.VALIDATING},
    OrderStatus.VALIDATING: {OrderStatus.VALIDATED, OrderStatus.REJECTED},
    OrderStatus.VALIDATED: {OrderStatus.INVOICING},
    OrderStatus.INVOICING: {OrderStatus.COMPLETED, OrderStatus.FAILED},
    OrderStatus.REJECTED: set(),
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.FAILED: set(),
}


def _build_transitions() -> dict[OrderStatus, frozenset[OrderStatus]]:
    transitions = {status: set(targets) for status, targets in _BASE_TRANSITIONS.items()}

    for source in _CANCELLABLE_FROM:
        transitions[source].add(OrderStatus.CANCELLED)

    for source in _REOPEN_TO_PROCESSING_FROM:
        transitions[source].add(OrderStatus.PROCESSING)

    for source in OrderStatus:
        if source not in _TERMINAL_STATES:
            transitions[source].add(OrderStatus.FAILED)

    return {status: frozenset(targets) for status, targets in transitions.items()}


_TRANSITIONS = _build_transitions()


def is_valid_transition(current: OrderStatus, next: OrderStatus) -> bool:
    """Indica se a transição `current -> next` é permitida (§2.3)."""
    return next in _TRANSITIONS[current]
