from decimal import Decimal

import httpx
import pytest

from order_validator.adapters import catalogo_produtos
from order_validator.adapters.catalogo_produtos import (
    CatalogoCache,
    ProdutoNaoEncontradoError,
    buscar_produto,
)
from order_validator.domain.modelos import Produto


def _response(status: int, payload: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=payload or {}, request=httpx.Request("GET", "http://x"))


def _produto(product_id: int = 1) -> Produto:
    return Produto(product_id, "Produto", Decimal("10.00"), 10, 1, "In Stock", "SKU", Decimal("0"))


def test_buscar_produto_parses_successful_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(
            200,
            {
                "id": 1,
                "title": "Produto",
                "price": 9.99,
                "stock": 10,
                "minimumOrderQuantity": 2,
                "availabilityStatus": "In Stock",
                "sku": "SKU-1",
                "discountPercentage": 10.48,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    produto = buscar_produto(client, CatalogoCache(), 1, "http://catalog")

    assert produto.id == 1
    assert produto.price == Decimal("9.99")
    assert produto.discount_percentage == Decimal("10.48")


def test_buscar_produto_maps_404_to_business_error() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: _response(404)))

    with pytest.raises(ProdutoNaoEncontradoError):
        buscar_produto(client, CatalogoCache(), 999, "http://catalog")


def test_buscar_produto_propagates_5xx_as_technical_error() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: _response(500)))

    with pytest.raises(httpx.HTTPStatusError):
        buscar_produto(client, CatalogoCache(), 1, "http://catalog")


def test_buscar_produto_retries_timeout_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectTimeout("timeout")
        return _response(
            200,
            {
                "id": 1,
                "title": "Produto",
                "price": 10,
                "stock": 10,
                "minimumOrderQuantity": 1,
                "availabilityStatus": "In Stock",
                "sku": "SKU",
                "discountPercentage": 0,
            },
        )

    monkeypatch.setattr(catalogo_produtos.time, "sleep", lambda seconds: None)
    client = httpx.Client(transport=httpx.MockTransport(handler))

    assert buscar_produto(client, CatalogoCache(), 1, "http://catalog").id == 1
    assert calls == 3


def test_catalogo_cache_hits_misses_and_expires() -> None:
    now = 1000.0
    cache = CatalogoCache(ttl_seconds=300, clock=lambda: now)
    produto = _produto()

    assert cache.get(1) is None
    cache.set(produto)
    assert cache.get(1) == produto

    now = 1300.0
    assert cache.get(1) is None


def test_buscar_produto_uses_cache_before_external_call() -> None:
    cache = CatalogoCache()
    cache.set(_produto())
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: pytest.fail("external call should not run"))
    )

    assert buscar_produto(client, cache, 1, "http://catalog").id == 1
