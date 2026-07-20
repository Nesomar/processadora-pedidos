from unittest.mock import MagicMock

import pytest
from pedidos_shared import Settings

from file_consumer.adapters import worker_loop

QUEUE_URL = "http://localhost:4566/000000000000/s3_notifications_queue"

_BODY = {"Records": [{"eventName": "ObjectCreated:Put"}]}


def test_process_once_calls_handler_marks_and_acks_new_message(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    sqs = MagicMock()
    sqs.receive_raw_with_receipt.return_value = [(_BODY, "receipt-1", "native-id-1")]
    monkeypatch.setattr(worker_loop, "is_message_processed", lambda *a, **k: False)
    mark = MagicMock(return_value=False)
    monkeypatch.setattr(worker_loop, "mark_message_processed", mark)
    handler = MagicMock()

    assert worker_loop.process_once(sqs, QUEUE_URL, handler, settings) == 1

    handler.assert_called_once_with(_BODY, settings)
    mark.assert_called_once_with("native-id-1", worker_loop.CONSUMER_NAME, settings)
    sqs.delete.assert_called_once_with(QUEUE_URL, "receipt-1")


def test_process_once_skips_handler_for_duplicate_message(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    sqs = MagicMock()
    sqs.receive_raw_with_receipt.return_value = [(_BODY, "receipt-1", "native-id-1")]
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
    sqs = MagicMock()
    sqs.receive_raw_with_receipt.return_value = [(_BODY, "receipt-1", "native-id-1")]
    monkeypatch.setattr(worker_loop, "is_message_processed", lambda *a, **k: False)
    mark = MagicMock()
    monkeypatch.setattr(worker_loop, "mark_message_processed", mark)
    handler = MagicMock(side_effect=RuntimeError("s3 indisponivel"))

    worker_loop.process_once(sqs, QUEUE_URL, handler, settings)

    mark.assert_not_called()
    sqs.delete.assert_not_called()
