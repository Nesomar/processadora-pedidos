"""Contratos de mensagem (docs/01-dominio-e-contratos.md §2, §5)."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from pedidos_shared.status import OrderStatus


class OrderItem(BaseModel):
    product_id: int
    quantity: int
    unit_price: Decimal | None = None
    discount_percentage: Decimal | None = None
    line_total: Decimal | None = None
    product_title: str | None = None
    product_sku: str | None = None


class Order(BaseModel):
    order_id: str
    customer_id: str
    customer_name: str
    customer_document: str
    channel: Literal["HTTP", "BATCH"]
    items: list[OrderItem]
    subtotal: Decimal | None = None
    discount_total: Decimal | None = None
    total: Decimal | None = None
    status: OrderStatus
    status_reason: str | None = None
    invoice_s3_key: str | None = None
    correlation_id: str
    source_file: str | None = None
    source_line: int | None = None
    created_at: datetime
    updated_at: datetime
    version: int

    @model_validator(mode="after")
    def _status_reason_required_on_rejected_or_failed(self) -> "Order":
        if self.status in (OrderStatus.REJECTED, OrderStatus.FAILED) and not self.status_reason:
            raise ValueError(f"status_reason é obrigatório quando status={self.status.value}")
        return self


class MessageEnvelope(BaseModel):
    message_id: str
    correlation_id: str
    order_id: str
    occurred_at: datetime
    payload: dict[str, Any]
