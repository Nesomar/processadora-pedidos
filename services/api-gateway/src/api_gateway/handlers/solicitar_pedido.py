"""`POST /pedidos` — cria pedido (US1) ou aceita linha de arquivo batch (US2)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status
from pedidos_shared import MessageEnvelope

from api_gateway.deps import SettingsDep, SqsClientDep
from api_gateway.publish import publicar_ou_502
from api_gateway.schemas import AceitePedidoResponse, SolicitarPedidoRequest

router = APIRouter()


@router.post(
    "/pedidos",
    response_model=AceitePedidoResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def solicitar_pedido(
    payload: SolicitarPedidoRequest,
    settings: SettingsDep,
    sqs: SqsClientDep,
) -> AceitePedidoResponse:
    order_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())

    envelope = MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=correlation_id,
        order_id=order_id,
        occurred_at=datetime.now(UTC),
        payload=payload.model_dump(mode="json"),
    )

    publicar_ou_502(
        sqs,
        settings.solicitar_pedido_queue_url,
        envelope,
        "Falha ao publicar solicitação de pedido",
    )

    return AceitePedidoResponse(order_id=order_id, correlation_id=correlation_id)
