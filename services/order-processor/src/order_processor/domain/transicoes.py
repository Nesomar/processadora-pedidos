"""Wrappers finos sobre is_valid_transition — nenhuma tabela de estados própria (research.md #5)."""

from pedidos_shared import OrderStatus, is_valid_transition


class TransicaoInvalidaError(Exception):
    """`is_valid_transition` reprovou a transição pedida (contrato regra 3 de pedidos_shared)."""


def aplicar_solicitacao() -> OrderStatus:
    """US1 — `— -> RECEIVED -> PROCESSING -> VALIDATING` colapsadas numa única escrita: o pedido
    já nasce persistido pronto pra validação, pois este handler publica em `validar_pedido_queue`
    na mesma operação (§2.3 de docs/01-dominio-e-contratos.md)."""
    return OrderStatus.VALIDATING


def aplicar_resposta_validacao(status_atual: OrderStatus, approved: bool) -> OrderStatus:
    """US2 — aprovado: `VALIDATING`→`VALIDATED`→`INVOICING` (as duas transições da tabela §2.3
    aplicadas na mesma mensagem, sem escrita intermediária); reprovado: `VALIDATING`→`REJECTED`."""
    if approved:
        if not is_valid_transition(status_atual, OrderStatus.VALIDATED):
            raise TransicaoInvalidaError(
                f"{status_atual.value} não pode ir para VALIDATED (resposta de validação aprovada)"
            )
        return OrderStatus.INVOICING

    if not is_valid_transition(status_atual, OrderStatus.REJECTED):
        raise TransicaoInvalidaError(
            f"{status_atual.value} não pode ir para REJECTED (resposta de validação reprovada)"
        )
    return OrderStatus.REJECTED


def aplicar_edicao(status_atual: OrderStatus) -> OrderStatus:
    """US4 — edição válida a partir de `RECEIVED`/`VALIDATED`/`REJECTED` (FR-008); reabre o ciclo
    em `PROCESSING -> VALIDATING` colapsadas (mesma lógica de `aplicar_solicitacao`), já que este
    handler republica em `validar_pedido_queue` na mesma operação."""
    if not is_valid_transition(status_atual, OrderStatus.PROCESSING):
        raise TransicaoInvalidaError(f"{status_atual.value} não pode ser editado")
    return OrderStatus.VALIDATING


def aplicar_cancelamento(status_atual: OrderStatus) -> OrderStatus:
    """US5 — cancelamento válido a partir de `RECEIVED`/`PROCESSING`/`VALIDATING`/`VALIDATED`
    (FR-009)."""
    if not is_valid_transition(status_atual, OrderStatus.CANCELLED):
        raise TransicaoInvalidaError(f"{status_atual.value} não pode ser cancelado")
    return OrderStatus.CANCELLED


def aplicar_resposta_pdf(status_atual: OrderStatus, success: bool) -> OrderStatus:
    """US3 — sucesso: `INVOICING`→`COMPLETED`; falha: `INVOICING`→`FAILED`.

    Checa `status_atual == INVOICING` explicitamente porque `is_valid_transition(_, FAILED)` é
    verdadeiro pra qualquer estado não-terminal (regra "erro técnico esgota retries" de §2.3) —
    sem esse guard, uma resposta de PDF com `success=false` seria aceita indevidamente vinda de
    qualquer estado ativo, não só de quem de fato está aguardando o PDF."""
    if status_atual is not OrderStatus.INVOICING:
        raise TransicaoInvalidaError(
            f"{status_atual.value} não pode receber resposta de emissão de PDF (esperado INVOICING)"
        )
    return OrderStatus.COMPLETED if success else OrderStatus.FAILED
