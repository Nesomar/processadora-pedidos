import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from pedidos_shared import MessageEnvelope, Settings

from order_validator.adapters.catalogo_produtos import CatalogoCache, ProdutoNaoEncontradoError
from order_validator.domain.modelos import Produto
from order_validator.handlers import validar_pedido


def _produto(
    product_id: int = 1,
    price: str = "10.00",
    stock: int = 10,
    minimum: int = 1,
    status: str = "In Stock",
    discount: str = "0",
) -> Produto:
    return Produto(
        product_id,
        f"Produto {product_id}",
        Decimal(price),
        stock,
        minimum,
        status,
        f"SKU-{product_id}",
        Decimal(discount),
    )


def _envelope(payload: dict) -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=str(uuid.uuid4()),
        occurred_at=datetime.now(UTC),
        payload=payload,
    )


def _payload(document: str = "52998224725", items: list[dict] | None = None) -> dict:
    return {"customer_document": document, "items": items or [{"product_id": 1, "quantity": 2}]}


class _FakeSqs:
    sent: list[tuple[str, MessageEnvelope]] = []

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, queue_url: str, envelope: MessageEnvelope) -> str:
        self.sent.append((queue_url, envelope))
        return "sent-id"


@pytest.fixture(autouse=True)
def _fake_sqs(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSqs.sent = []
    monkeypatch.setattr(validar_pedido, "SqsClient", _FakeSqs)


def _sent_payload() -> dict:
    assert len(_FakeSqs.sent) == 1
    return _FakeSqs.sent[0][1].payload


def test_handle_publishes_approved_response(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validar_pedido, "buscar_produto", lambda *args: _produto(discount="10"))
    envelope = _envelope(_payload())

    validar_pedido.handle(envelope, settings, client=MagicMock(), cache=CatalogoCache())

    _, response = _FakeSqs.sent[0]
    assert response.order_id == envelope.order_id
    assert response.correlation_id == envelope.correlation_id
    assert response.payload == {
        "approved": True,
        "errors": [],
        "enriched_items": [
            {
                "product_id": 1,
                "quantity": 2,
                "unit_price": "10.00",
                "discount_percentage": "10.00",
                "line_total": "18.00",
                "product_title": "Produto 1",
                "product_sku": "SKU-1",
            }
        ],
        "subtotal": "20.00",
        "discount_total": "2.00",
        "total": "18.00",
    }


def test_handle_rejects_invalid_document(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validar_pedido, "buscar_produto", lambda *args: _produto())

    validar_pedido.handle(
        _envelope(_payload(document="11111111111")),
        settings,
        client=MagicMock(),
        cache=CatalogoCache(),
    )

    payload = _sent_payload()
    assert payload["approved"] is False
    assert payload["enriched_items"] is None
    assert payload["errors"][0]["code"] == "INVALID_DOCUMENT"
    assert payload["errors"][0]["product_id"] is None


def test_handle_aggregates_invalid_document_and_item_errors(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validar_pedido, "buscar_produto", lambda *args: _produto(minimum=5))

    validar_pedido.handle(
        _envelope(_payload(document="11111111111", items=[{"product_id": 1, "quantity": 1}])),
        settings,
        client=MagicMock(),
        cache=CatalogoCache(),
    )

    codes = [error["code"] for error in _sent_payload()["errors"]]
    assert codes == ["INVALID_DOCUMENT", "BELOW_MINIMUM_ORDER_QUANTITY"]


def test_handle_aggregates_multiple_item_errors(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        validar_pedido, "buscar_produto", lambda *args: _produto(stock=5, minimum=20)
    )

    validar_pedido.handle(
        _envelope(_payload(items=[{"product_id": 1, "quantity": 10}])),
        settings,
        client=MagicMock(),
        cache=CatalogoCache(),
    )

    codes = [error["code"] for error in _sent_payload()["errors"]]
    assert codes == ["INSUFFICIENT_STOCK", "BELOW_MINIMUM_ORDER_QUANTITY"]


def test_handle_rejects_total_above_limit(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validar_pedido, "buscar_produto", lambda *args: _produto(price="100000.01"))

    validar_pedido.handle(
        _envelope(_payload()), settings, client=MagicMock(), cache=CatalogoCache()
    )

    payload = _sent_payload()
    assert payload["approved"] is False
    assert payload["errors"] == [
        {
            "code": "ORDER_TOTAL_EXCEEDS_LIMIT",
            "product_id": None,
            "message": "Total do pedido (200000.02) excede o limite maximo de 100000.00",
        }
    ]


def test_handle_skips_limit_when_item_errors_exist(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        validar_pedido,
        "buscar_produto",
        lambda *args: _produto(price="200000.00", stock=1, minimum=1),
    )

    validar_pedido.handle(
        _envelope(_payload(items=[{"product_id": 1, "quantity": 2}])),
        settings,
        client=MagicMock(),
        cache=CatalogoCache(),
    )

    codes = [error["code"] for error in _sent_payload()["errors"]]
    assert codes == ["INSUFFICIENT_STOCK"]


def test_handle_maps_product_not_found(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_not_found(*args):
        raise ProdutoNaoEncontradoError("not found")

    monkeypatch.setattr(validar_pedido, "buscar_produto", raise_not_found)

    validar_pedido.handle(
        _envelope(_payload()), settings, client=MagicMock(), cache=CatalogoCache()
    )

    payload = _sent_payload()
    assert payload["approved"] is False
    assert payload["errors"] == [
        {"code": "PRODUCT_NOT_FOUND", "product_id": 1, "message": "Produto 1 nao encontrado"}
    ]


def test_handle_does_not_apply_item_rules_after_product_not_found(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def raise_not_found(*args):
        raise ProdutoNaoEncontradoError("not found")

    stock_rule = MagicMock()
    monkeypatch.setattr(validar_pedido, "buscar_produto", raise_not_found)
    monkeypatch.setattr(validar_pedido, "validar_estoque", stock_rule)

    validar_pedido.handle(
        _envelope(_payload()), settings, client=MagicMock(), cache=CatalogoCache()
    )

    stock_rule.assert_not_called()


def test_handle_reuses_cache_across_messages(settings: Settings) -> None:
    calls = 0

    def fake_handler(*args):
        nonlocal calls
        calls += 1
        return _produto()

    class FakeClient:
        def get(self, *args, **kwargs):
            return fake_handler()

    cache = CatalogoCache()
    client = MagicMock()

    def fake_buscar(client_arg, cache_arg, product_id, base_url):
        cached = cache_arg.get(product_id)
        if cached is not None:
            return cached
        produto = fake_handler()
        cache_arg.set(produto)
        return produto

    original = validar_pedido.buscar_produto
    validar_pedido.buscar_produto = fake_buscar
    try:
        validar_pedido.handle(_envelope(_payload()), settings, client=client, cache=cache)
        validar_pedido.handle(_envelope(_payload()), settings, client=client, cache=cache)
    finally:
        validar_pedido.buscar_produto = original

    assert calls == 1
    assert len(_FakeSqs.sent) == 2
