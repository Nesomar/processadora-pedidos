"""`GET /pedidos?customerId=X` — lista os pedidos de um cliente (US6)."""

from fastapi import APIRouter, Query

from api_gateway.adapters.orders_repository import query_by_customer
from api_gateway.deps import DynamoDbClientDep, SettingsDep
from api_gateway.schemas import ListaPedidosResponse, PedidoResponse

router = APIRouter()


@router.get("/pedidos", response_model=ListaPedidosResponse)
def listar_pedidos(
    settings: SettingsDep,
    dynamodb: DynamoDbClientDep,
    customerId: str = Query(...),  # noqa: N803 — nome literal do query param (docs §3)
) -> ListaPedidosResponse:
    orders = query_by_customer(dynamodb, settings.orders_table_name, customerId)
    return ListaPedidosResponse(pedidos=[PedidoResponse.from_order(order) for order in orders])
