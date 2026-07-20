"""Cliente do catalogo externo dummyjson com cache TTL."""

import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import httpx

from order_validator.domain.modelos import Produto

DEFAULT_BASE_URL = "https://dummyjson.com"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_RETRY_SLEEP_SECONDS = 0.5
MAX_ATTEMPTS = 3


class ProdutoNaoEncontradoError(Exception):
    """Produto inexistente no catalogo externo."""


class CatalogoCache:
    def __init__(
        self,
        ttl_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._values: dict[int, tuple[Produto, float]] = {}

    def get(self, product_id: int) -> Produto | None:
        cached = self._values.get(product_id)
        if cached is None:
            return None
        produto, expires_at = cached
        if expires_at <= self._clock():
            del self._values[product_id]
            return None
        return produto

    def set(self, produto: Produto) -> None:
        self._values[produto.id] = (produto, self._clock() + self._ttl_seconds)


def _decimal_from_api(value: Any) -> Decimal:
    return Decimal(str(value))


def _parse_produto(data: dict[str, Any]) -> Produto:
    return Produto(
        id=int(data["id"]),
        title=str(data["title"]),
        price=_decimal_from_api(data["price"]),
        stock=int(data["stock"]),
        minimum_order_quantity=int(data["minimumOrderQuantity"]),
        availability_status=str(data["availabilityStatus"]),
        sku=str(data["sku"]),
        discount_percentage=_decimal_from_api(data["discountPercentage"]),
    )


def buscar_produto(
    client: httpx.Client,
    cache: CatalogoCache,
    product_id: int,
    base_url: str = DEFAULT_BASE_URL,
) -> Produto:
    cached = cache.get(product_id)
    if cached is not None:
        return cached

    url = f"{base_url.rstrip('/')}/products/{product_id}"
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = client.get(url, timeout=DEFAULT_TIMEOUT_SECONDS)
            if response.status_code == 404:
                raise ProdutoNaoEncontradoError(f"produto {product_id} nao encontrado")
            response.raise_for_status()
            produto = _parse_produto(response.json())
            cache.set(produto)
            return produto
        except ProdutoNaoEncontradoError:
            raise
        except httpx.RequestError as error:
            last_error = error
            if attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(DEFAULT_RETRY_SLEEP_SECONDS)
        except httpx.HTTPStatusError:
            raise

    raise RuntimeError(f"falha inesperada ao buscar produto {product_id}") from last_error
