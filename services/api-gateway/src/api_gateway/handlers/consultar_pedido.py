"""`GET /pedidos/{order_id}` — consulta um pedido específico (US5)."""

from fastapi import APIRouter, HTTPException, status

from api_gateway.adapters.orders_repository import get_by_id
from api_gateway.deps import DynamoDbClientDep, SettingsDep
from api_gateway.schemas import PedidoResponse

router = APIRouter()


@router.get("/pedidos/{order_id}", response_model=PedidoResponse)
def consultar_pedido(
    order_id: str,
    settings: SettingsDep,
    dynamodb: DynamoDbClientDep,
) -> PedidoResponse:
    order = get_by_id(dynamodb, settings.orders_table_name, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")

    return PedidoResponse.from_order(order)
