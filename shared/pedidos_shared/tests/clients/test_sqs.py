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
        s3_notifications_queue_url=os.environ.get("S3_NOTIFICATIONS_QUEUE_URL"),
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


def test_send_raw_and_receive_raw_with_receipt_roundtrip(settings: Settings) -> None:
    if not _ministack_available(settings):
        pytest.skip("Ministack local indisponível (feature 002-infraestrutura-local)")
    if not settings.s3_notifications_queue_url:
        pytest.skip("S3_NOTIFICATIONS_QUEUE_URL não configurada")

    sqs = SqsClient(settings)
    marker = str(uuid4())
    body = {"Records": [{"eventName": "ObjectCreated:Put", "marker": marker}]}

    message_id = sqs.send_raw(settings.s3_notifications_queue_url, body)
    assert message_id

    received = sqs.receive_raw_with_receipt(settings.s3_notifications_queue_url)
    match = next(
        (item for item in received if item[0].get("Records", [{}])[0].get("marker") == marker),
        None,
    )
    assert match is not None
    received_body, receipt_handle, native_message_id = match
    assert received_body == body
    assert native_message_id

    sqs.delete(settings.s3_notifications_queue_url, receipt_handle)


# --- primitivas de DLQ (011-observabilidade-dlq): boto3 mockado ---


@pytest.fixture
def fake_boto(monkeypatch: pytest.MonkeyPatch, settings: Settings):
    from unittest.mock import MagicMock

    fake = MagicMock()
    monkeypatch.setattr("pedidos_shared.clients.sqs.boto3.client", lambda *a, **k: fake)
    return fake


def test_queue_url_resolves_by_name(settings: Settings, fake_boto) -> None:
    fake_boto.get_queue_url.return_value = {"QueueUrl": "http://q/x_dlq"}

    assert SqsClient(settings).queue_url("x_dlq") == "http://q/x_dlq"
    fake_boto.get_queue_url.assert_called_once_with(QueueName="x_dlq")


def test_queue_url_propagates_missing_queue(settings: Settings, fake_boto) -> None:
    fake_boto.get_queue_url.side_effect = RuntimeError("QueueDoesNotExist")

    with pytest.raises(RuntimeError):
        SqsClient(settings).queue_url("nope")


def test_message_count_sums_visible_in_flight_and_delayed(settings: Settings, fake_boto) -> None:
    fake_boto.get_queue_attributes.return_value = {
        "Attributes": {
            "ApproximateNumberOfMessages": "2",
            "ApproximateNumberOfMessagesNotVisible": "1",
            "ApproximateNumberOfMessagesDelayed": "0",
        }
    }

    assert SqsClient(settings).message_count("http://q") == 3


def test_peek_hides_during_scan_then_releases_and_maps_fields(
    settings: Settings, fake_boto
) -> None:
    fake_boto.receive_message.side_effect = [
        {
            "Messages": [
                {
                    "MessageId": "m1",
                    "Body": "{}",
                    "ReceiptHandle": "r1",
                    "Attributes": {"SentTimestamp": "1790000000000"},
                }
            ]
        },
        {"Messages": [{"MessageId": "m2", "Body": "[]", "ReceiptHandle": "r2"}]},
        {},
    ]

    result = SqsClient(settings).peek("http://q", 5)

    assert fake_boto.receive_message.call_args.kwargs["VisibilityTimeout"] == 30
    calls = fake_boto.change_message_visibility.call_args_list
    assert [c.kwargs["ReceiptHandle"] for c in calls] == ["r1", "r2"]
    assert all(c.kwargs["VisibilityTimeout"] == 0 for c in calls)
    fake_boto.delete_message.assert_not_called()
    assert result == [
        {"MessageId": "m1", "Body": "{}", "SentTimestamp": "1790000000000"},
        {"MessageId": "m2", "Body": "[]", "SentTimestamp": None},
    ]


def test_peek_releases_what_it_saw_when_a_later_round_fails(settings: Settings, fake_boto) -> None:
    fake_boto.receive_message.side_effect = [
        {"Messages": [{"MessageId": "m1", "Body": "{}", "ReceiptHandle": "r1"}]},
        RuntimeError("sqs down"),
    ]

    with pytest.raises(RuntimeError):
        SqsClient(settings).peek("http://q", 5)

    fake_boto.change_message_visibility.assert_called_once()


def test_peek_stops_when_limit_reached(settings: Settings, fake_boto) -> None:
    fake_boto.receive_message.return_value = {
        "Messages": [{"MessageId": "m1", "Body": "{}", "ReceiptHandle": "r1"}]
    }

    result = SqsClient(settings).peek("http://q", 1)

    assert len(result) == 1
    assert fake_boto.receive_message.call_count == 1


def test_peek_empty_queue_returns_empty_list(settings: Settings, fake_boto) -> None:
    fake_boto.receive_message.return_value = {}

    assert SqsClient(settings).peek("http://q") == []


def test_receive_raw_messages_keeps_default_visibility_and_receipt(
    settings: Settings, fake_boto
) -> None:
    fake_boto.receive_message.return_value = {
        "Messages": [{"MessageId": "m1", "Body": "b", "ReceiptHandle": "r1"}]
    }

    result = SqsClient(settings).receive_raw_messages("http://q")

    kwargs = fake_boto.receive_message.call_args.kwargs
    assert "VisibilityTimeout" not in kwargs
    assert kwargs["WaitTimeSeconds"] == 1
    assert result == [{"MessageId": "m1", "Body": "b", "ReceiptHandle": "r1"}]


def test_release_sets_visibility_to_zero(settings: Settings, fake_boto) -> None:
    SqsClient(settings).release("http://q", "r1")

    fake_boto.change_message_visibility.assert_called_once_with(
        QueueUrl="http://q", ReceiptHandle="r1", VisibilityTimeout=0
    )


def test_send_body_forwards_exact_body(settings: Settings, fake_boto) -> None:
    fake_boto.send_message.return_value = {"MessageId": "new"}

    assert SqsClient(settings).send_body("http://q", '{"a": 1}') == "new"
    fake_boto.send_message.assert_called_once_with(QueueUrl="http://q", MessageBody='{"a": 1}')
