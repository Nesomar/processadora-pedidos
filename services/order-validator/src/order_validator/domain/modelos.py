"""Modelos internos do order-validator."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Produto:
    id: int
    title: str
    price: Decimal
    stock: int
    minimum_order_quantity: int
    availability_status: str
    sku: str
    discount_percentage: Decimal


@dataclass(frozen=True)
class ItemValidacao:
    product_id: int
    quantity: int


@dataclass(frozen=True)
class ErroValidacao:
    code: str
    product_id: int | None
    message: str


@dataclass(frozen=True)
class ItemEnriquecido:
    product_id: int
    quantity: int
    unit_price: Decimal
    discount_percentage: Decimal
    line_total: Decimal
    product_title: str
    product_sku: str
