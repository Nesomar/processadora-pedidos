"""`PUT /pedidos/{order_id}` — edita pedido existente, reabrindo o ciclo (US3)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pedidos_shared import MessageEnvelope

from api_gateway.adapters.orders_repository import get_by_id
from api_gateway.deps import DynamoDbClientDep, SettingsDep, SqsClientDep
from api_gateway.domain.elegibilidade_transicao import pode_editar
from api_gateway.publish import publicar_ou_502
from api_gateway.schemas import AceitePedidoResponse, EditarPedidoRequest

router = APIRouter()


@router.put(
    "/pedidos/{order_id}",
    response_model=AceitePedidoResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def editar_pedido(
    order_id: str,
    payload: EditarPedidoRequest,
    settings: SettingsDep,
    sqs: SqsClientDep,
    dynamodb: DynamoDbClientDep,
) -> AceitePedidoResponse:
    order = get_by_id(dynamodb, settings.orders_table_name, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")

    if not pode_editar(order.status):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pedido em status {order.status.value} não pode ser editado",
        )

    envelope = MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=order.correlation_id,
        order_id=order_id,
        occurred_at=datetime.now(UTC),
        payload=payload.model_dump(mode="json"),
    )

    publicar_ou_502(
        sqs, settings.editar_pedido_queue_url, envelope, "Falha ao publicar edição de pedido"
    )

    return AceitePedidoResponse(order_id=order_id, correlation_id=order.correlation_id)
