"""Consome `pdf_response_queue` — conclui ou marca falha no pedido (US3)."""

from pedidos_shared import DynamoDbClient, MessageEnvelope, Order, Settings

from order_processor.adapters.orders_repository import record_rejection, update_with_version
from order_processor.domain.transicoes import TransicaoInvalidaError, aplicar_resposta_pdf


def handle(envelope: MessageEnvelope, settings: Settings) -> None:
    payload = envelope.payload
    success = payload["success"]
    dynamodb = DynamoDbClient(settings)

    if success:

        def _apply_success(order: Order) -> Order:
            novo_status = aplicar_resposta_pdf(order.status, True)
            return order.model_copy(
                update={"status": novo_status, "invoice_s3_key": payload["s3_key"]}
            )

        try:
            update_with_version(
                dynamodb, settings.orders_table_name, envelope.order_id, _apply_success
            )
        except TransicaoInvalidaError as error:
            record_rejection(dynamodb, settings.orders_table_name, envelope.order_id, str(error))
            raise
        return

    def _apply_failure(order: Order) -> Order:
        novo_status = aplicar_resposta_pdf(order.status, False)
        return order.model_copy(
            update={
                "status": novo_status,
                "status_reason": payload.get("error_message") or "Falha na emissão da nota fiscal",
            }
        )

    try:
        update_with_version(dynamodb, settings.orders_table_name, envelope.order_id, _apply_failure)
    except TransicaoInvalidaError as error:
        record_rejection(dynamodb, settings.orders_table_name, envelope.order_id, str(error))
        raise
