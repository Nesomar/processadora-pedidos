"""Consome `validar_pedido_response_queue` — aprova (dispara PDF) ou rejeita o pedido (US2)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pedidos_shared import DynamoDbClient, MessageEnvelope, Order, OrderItem, Settings, SqsClient

from order_processor.adapters.orders_repository import record_rejection, update_with_version
from order_processor.domain.mensagens import montar_payload_pdf
from order_processor.domain.transicoes import TransicaoInvalidaError, aplicar_resposta_validacao


def _reason_from_errors(errors: list[dict[str, str]]) -> str:
    if not errors:
        return "Pedido reprovado na validação"
    return "; ".join(error.get("message", "") for error in errors)


def handle(envelope: MessageEnvelope, settings: Settings) -> None:
    payload = envelope.payload
    approved = payload["approved"]
    dynamodb = DynamoDbClient(settings)

    if approved:

        def _apply_approved(order: Order) -> Order:
            novo_status = aplicar_resposta_validacao(order.status, True)
            items = [OrderItem(**item) for item in payload["enriched_items"]]
            return order.model_copy(
                update={
                    "status": novo_status,
                    "items": items,
                    "subtotal": Decimal(payload["subtotal"]),
                    "discount_total": Decimal(payload["discount_total"]),
                    "total": Decimal(payload["total"]),
                }
            )

        try:
            updated = update_with_version(
                dynamodb, settings.orders_table_name, envelope.order_id, _apply_approved
            )
        except TransicaoInvalidaError as error:
            record_rejection(dynamodb, settings.orders_table_name, envelope.order_id, str(error))
            raise

        pdf_request = MessageEnvelope(
            message_id=str(uuid.uuid4()),
            correlation_id=updated.correlation_id,
            order_id=updated.order_id,
            occurred_at=datetime.now(UTC),
            payload=montar_payload_pdf(updated),
        )
        SqsClient(settings).send(settings.pdf_request_queue_url, pdf_request)
        return

    reason = _reason_from_errors(payload.get("errors", []))

    def _apply_rejected(order: Order) -> Order:
        novo_status = aplicar_resposta_validacao(order.status, False)
        return order.model_copy(update={"status": novo_status, "status_reason": reason})

    try:
        update_with_version(
            dynamodb, settings.orders_table_name, envelope.order_id, _apply_rejected
        )
    except TransicaoInvalidaError as error:
        record_rejection(dynamodb, settings.orders_table_name, envelope.order_id, str(error))
        raise
