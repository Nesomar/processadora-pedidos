"""Teste de worker_loop.process_once — idempotência + dispatch + ack seletivo."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pedidos_shared import MessageEnvelope, Settings

from order_processor.adapters import worker_loop
from order_processor.domain.transicoes import TransicaoInvalidaError

QUEUE_URL = "http://localhost:4566/000000000000/solicitar_pedido_queue"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        aws_endpoint_url="http://localhost:4566",
        aws_region="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        processed_messages_table_name="processed_messages",
    )


def _envelope() -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid4()),
        correlation_id=str(uuid4()),
        order_id=str(uuid4()),
        occurred_at=datetime.now(UTC),
        payload={},
    )


def test_process_once_calls_handler_and_acks_new_message(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope = _envelope()
    sqs = MagicMock()
    sqs.receive_with_receipt.return_value = [(envelope, "receipt-1")]
    monkeypatch.setattr(worker_loop, "is_message_processed", lambda *a, **k: False)
    mark = MagicMock(return_value=False)
    monkeypatch.setattr(worker_loop, "mark_message_processed", mark)
    handler = MagicMock()

    count = worker_loop.process_once(sqs, QUEUE_URL, handler, settings)

    assert count == 1
    handler.assert_called_once_with(envelope, settings)
    mark.assert_called_once_with(envelope.message_id, worker_loop.CONSUMER_NAME, settings)
    sqs.delete.assert_called_once_with(QUEUE_URL, "receipt-1")


def test_process_once_skips_handler_for_already_processed_message(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope = _envelope()
    sqs = MagicMock()
    sqs.receive_with_receipt.return_value = [(envelope, "receipt-1")]
    monkeypatch.setattr(worker_loop, "is_message_processed", lambda *a, **k: True)
    mark = MagicMock()
    monkeypatch.setattr(worker_loop, "mark_message_processed", mark)
    handler = MagicMock()

    worker_loop.process_once(sqs, QUEUE_URL, handler, settings)

    handler.assert_not_called()
    mark.assert_not_called()
    sqs.delete.assert_called_once_with(QUEUE_URL, "receipt-1")


def test_process_once_does_not_ack_or_mark_when_handler_raises_technical_error(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope = _envelope()
    sqs = MagicMock()
    sqs.receive_with_receipt.return_value = [(envelope, "receipt-1")]
    monkeypatch.setattr(worker_loop, "is_message_processed", lambda *a, **k: False)
    mark = MagicMock()
    monkeypatch.setattr(worker_loop, "mark_message_processed", mark)
    handler = MagicMock(side_effect=RuntimeError("erro técnico"))

    worker_loop.process_once(sqs, QUEUE_URL, handler, settings)

    # falha técnica não marca como processada nem confirma — assim o redrive do SQS reentrega e
    # `is_message_processed` continua vendo `False`, permitindo reprocessar de verdade.
    mark.assert_not_called()
    sqs.delete.assert_not_called()


def test_process_once_acks_and_marks_on_business_rejection(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope = _envelope()
    sqs = MagicMock()
    sqs.receive_with_receipt.return_value = [(envelope, "receipt-1")]
    monkeypatch.setattr(worker_loop, "is_message_processed", lambda *a, **k: False)
    mark = MagicMock(return_value=False)
    monkeypatch.setattr(worker_loop, "mark_message_processed", mark)
    handler = MagicMock(side_effect=TransicaoInvalidaError("estado não permite edição"))

    worker_loop.process_once(sqs, QUEUE_URL, handler, settings)

    mark.assert_called_once_with(envelope.message_id, worker_loop.CONSUMER_NAME, settings)
    sqs.delete.assert_called_once_with(QUEUE_URL, "receipt-1")
