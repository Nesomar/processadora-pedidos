import uuid
from datetime import UTC, datetime

import pytest
from pedidos_shared import MessageEnvelope, Settings

from order_validator.adapters import worker_loop
from order_validator.adapters.catalogo_produtos import CatalogoCache
from order_validator.domain.modelos import Produto
from order_validator.handlers import validar_pedido


def _envelope() -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=str(uuid.uuid4()),
        occurred_at=datetime.now(UTC),
        payload={"customer_document": "52998224725", "items": [{"product_id": 1, "quantity": 1}]},
    )


def test_reprocessing_integration_same_message_twice_publishes_one_response(
    sqs_client, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from decimal import Decimal

    envelope = _envelope()

    def fake_buscar(*args):
        return Produto(1, "Produto", Decimal("10.00"), 10, 1, "In Stock", "SKU", Decimal("0"))

    monkeypatch.setattr(validar_pedido, "buscar_produto", fake_buscar)

    def handler(message: MessageEnvelope, inner_settings: Settings) -> None:
        validar_pedido.handle(message, inner_settings, cache=CatalogoCache())

    sqs_client.send(settings.validar_pedido_queue_url, envelope)
    worker_loop.process_once(sqs_client, settings.validar_pedido_queue_url, handler, settings)
    sqs_client.send(settings.validar_pedido_queue_url, envelope)
    worker_loop.process_once(sqs_client, settings.validar_pedido_queue_url, handler, settings)

    responses = sqs_client.receive(settings.validar_pedido_response_queue_url)
    matching = [message for message in responses if message.order_id == envelope.order_id]
    assert len(matching) == 1
