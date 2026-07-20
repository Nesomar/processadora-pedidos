import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pedidos_shared import MessageEnvelope, Settings

from order_validator.adapters import worker_loop

QUEUE_URL = "http://localhost:4566/000000000000/validar_pedido_queue"


def _envelope() -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=str(uuid.uuid4()),
        occurred_at=datetime.now(UTC),
        payload={"customer_document": "52998224725", "items": [{"product_id": 1, "quantity": 1}]},
    )


def test_process_once_calls_handler_marks_and_acks_new_message(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope = _envelope()
    sqs = MagicMock()
    sqs.receive_with_receipt.return_value = [(envelope, "receipt-1")]
    monkeypatch.setattr(worker_loop, "is_message_processed", lambda *a, **k: False)
    mark = MagicMock(return_value=False)
    monkeypatch.setattr(worker_loop, "mark_message_processed", mark)
    handler = MagicMock()

    assert worker_loop.process_once(sqs, QUEUE_URL, handler, settings) == 1

    handler.assert_called_once_with(envelope, settings)
    mark.assert_called_once_with(envelope.message_id, worker_loop.CONSUMER_NAME, settings)
    sqs.delete.assert_called_once_with(QUEUE_URL, "receipt-1")


def test_process_once_skips_handler_for_duplicate_message(
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


def test_process_once_does_not_ack_or_mark_technical_error(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope = _envelope()
    sqs = MagicMock()
    sqs.receive_with_receipt.return_value = [(envelope, "receipt-1")]
    monkeypatch.setattr(worker_loop, "is_message_processed", lambda *a, **k: False)
    mark = MagicMock()
    monkeypatch.setattr(worker_loop, "mark_message_processed", mark)
    handler = MagicMock(side_effect=RuntimeError("catalog timeout"))

    worker_loop.process_once(sqs, QUEUE_URL, handler, settings)

    mark.assert_not_called()
    sqs.delete.assert_not_called()
