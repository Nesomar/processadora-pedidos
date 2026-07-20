"""Elegibilidade de edição/cancelamento — wrapper fino sobre is_valid_transition (research.md #2).

Nenhuma tabela de estados própria: `is_valid_transition` de `pedidos_shared` é a única fonte de
verdade sobre transições permitidas (contrato regra 3 de pedidos_shared-api.md).
"""

from pedidos_shared import OrderStatus, is_valid_transition


def pode_editar(status_atual: OrderStatus) -> bool:
    return is_valid_transition(status_atual, OrderStatus.PROCESSING)


def pode_cancelar(status_atual: OrderStatus) -> bool:
    return is_valid_transition(status_atual, OrderStatus.CANCELLED)
