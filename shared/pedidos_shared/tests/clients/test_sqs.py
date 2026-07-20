"""Teste de integração de SqsClient contra o Ministack local (feature 002-infraestrutura-local).

Requer `docker compose up` em `infra/` e `.env` carregado. Se o endpoint não responder, os
testes são pulados (Ministack ainda não provisionado nesta sessão de desenvolvimento).
"""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from pedidos_shared.clients.sqs import SqsClient
from pedidos_shared.models import MessageEnvelope
from pedidos_shared.settings import Settings


def _ministack_available(settings: Settings) -> bool:
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(settings.aws_endpoint_url)
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture
def settings() -> Settings:
    return Settings(
        aws_endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
        processed_messages_table_name=os.environ.get(
            "PROCESSED_MESSAGES_TABLE_NAME", "processed_messages"
        ),
        solicitar_pedido_queue_url=os.environ.get("SOLICITAR_PEDIDO_QUEUE_URL"),
    )


def test_send_and_receive_full_envelope(settings: Settings) -> None:
    if not _ministack_available(settings):
        pytest.skip("Ministack local indisponível (feature 002-infraestrutura-local)")
    if not settings.solicitar_pedido_queue_url:
        pytest.skip("SOLICITAR_PEDIDO_QUEUE_URL não configurada")

    sqs = SqsClient(settings)
    envelope = MessageEnvelope(
        message_id=str(uuid4()),
        correlation_id=str(uuid4()),
        order_id=str(uuid4()),
        occurred_at=datetime.now(UTC),
        payload={"foo": "bar"},
    )

    sqs.send(settings.solicitar_pedido_queue_url, envelope)
    received = sqs.receive(settings.solicitar_pedido_queue_url)

    assert any(msg.message_id == envelope.message_id for msg in received)


def test_receive_with_receipt_returns_envelope_and_deletable_receipt(settings: Settings) -> None:
    if not _ministack_available(settings):
        pytest.skip("Ministack local indisponível (feature 002-infraestrutura-local)")
    if not settings.solicitar_pedido_queue_url:
        pytest.skip("SOLICITAR_PEDIDO_QUEUE_URL não configurada")

    sqs = SqsClient(settings)
    envelope = MessageEnvelope(
        message_id=str(uuid4()),
        correlation_id=str(uuid4()),
        order_id=str(uuid4()),
        occurred_at=datetime.now(UTC),
        payload={"foo": "bar"},
    )
    sqs.send(settings.solicitar_pedido_queue_url, envelope)

    received = sqs.receive_with_receipt(settings.solicitar_pedido_queue_url)
    match = next((pair for pair in received if pair[0].message_id == envelope.message_id), None)
    assert match is not None
    _, receipt_handle = match

    sqs.delete(settings.solicitar_pedido_queue_url, receipt_handle)

    remaining = sqs.receive_with_receipt(settings.solicitar_pedido_queue_url)
    assert not any(env.message_id == envelope.message_id for env, _ in remaining)
