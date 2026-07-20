"""Schemas Pydantic da API HTTP — request/response, distintos de Order/OrderItem (data-model.md)."""

from typing import Literal

from pedidos_shared import Order, mask_document
from pydantic import BaseModel, model_validator

from api_gateway.domain.validar_payload import PayloadInvalidoError, validar_payload


class ItemRequest(BaseModel):
    product_id: int
    quantity: int


class ItemResponse(BaseModel):
    """Espelha `OrderItem` de pedidos_shared — inclui os campos preenchidos pelo Validator."""

    product_id: int
    quantity: int
    unit_price: str | None = None
    discount_percentage: str | None = None
    line_total: str | None = None
    product_title: str | None = None
    product_sku: str | None = None


class _PedidoPayloadBase(BaseModel):
    """Campos comuns a criar/editar pedido — payload de `solicitar_pedido_queue`/
    `editar_pedido_queue` (docs/01-dominio-e-contratos.md §5)."""

    customer_id: str
    customer_name: str
    customer_document: str
    channel: Literal["HTTP", "BATCH"] = "HTTP"
    items: list[ItemRequest]
    source_file: str | None = None
    source_line: int | None = None

    @model_validator(mode="after")
    def _validar_payload(self) -> "_PedidoPayloadBase":
        try:
            validar_payload(
                self.customer_id,
                self.customer_document,
                [item.quantity for item in self.items],
            )
        except PayloadInvalidoError as error:
            raise ValueError(str(error)) from error
        return self


class SolicitarPedidoRequest(_PedidoPayloadBase):
    pass


class EditarPedidoRequest(_PedidoPayloadBase):
    pass


class CancelarPedidoRequest(BaseModel):
    reason: str


class AceitePedidoResponse(BaseModel):
    order_id: str
    correlation_id: str


class PedidoResponse(BaseModel):
    order_id: str
    customer_id: str
    customer_name: str
    customer_document: str
    channel: Literal["HTTP", "BATCH"]
    items: list[ItemResponse]
    subtotal: str | None = None
    discount_total: str | None = None
    total: str | None = None
    status: str
    status_reason: str | None = None
    invoice_s3_key: str | None = None
    correlation_id: str
    source_file: str | None = None
    source_line: int | None = None
    created_at: str
    updated_at: str
    version: int

    @classmethod
    def from_order(cls, order: Order) -> "PedidoResponse":
        """Constrói a resposta a partir de `Order`, mascarando `customer_document` (FR-008)."""
        data = order.model_dump(mode="json")
        data["customer_document"] = mask_document(order.customer_document)
        return cls.model_validate(data)


class ListaPedidosResponse(BaseModel):
    pedidos: list[PedidoResponse]


class ErrorResponse(BaseModel):
    detail: str
