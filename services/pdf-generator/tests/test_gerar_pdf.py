import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pedidos_shared import MessageEnvelope, Settings

from pdf_generator.handlers import gerar_pdf

_ITEM = {
    "product_id": 1,
    "quantity": 3,
    "unit_price": "9.99",
    "discount_percentage": "10.48",
    "line_total": "26.82",
    "product_title": "Essence Mascara Lash Princess",
    "product_sku": "BEA-ESS-ESS-001",
}


def _envelope(payload: dict) -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=str(uuid.uuid4()),
        occurred_at=datetime.now(UTC),
        payload=payload,
    )


def _payload(**overrides: object) -> dict:
    base = {
        "customer_name": "Maria Silva",
        "customer_document": "52998224725",
        "items": [_ITEM],
        "subtotal": "29.97",
        "discount_total": "3.15",
        "total": "26.82",
    }
    base.update(overrides)
    return base


def test_handle_happy_path_stores_pdf_and_publishes_success(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope = _envelope(_payload())

    fake_s3 = MagicMock()
    monkeypatch.setattr(gerar_pdf, "S3Client", lambda _settings: fake_s3)

    fake_sqs = MagicMock()
    monkeypatch.setattr(gerar_pdf, "SqsClient", lambda _settings: fake_sqs)

    gerar_pdf.handle(envelope, settings)

    fake_s3.put_object.assert_called_once()
    bucket, key, body = fake_s3.put_object.call_args.args
    assert bucket == settings.pedidos_bucket_name
    assert key.startswith("invoices/")
    assert key.endswith(f"{envelope.order_id}.pdf")
    assert body.startswith(b"%PDF-")
    assert fake_s3.put_object.call_args.kwargs == {"content_type": "application/pdf"}

    fake_sqs.send.assert_called_once()
    sent_queue_url, sent_envelope = fake_sqs.send.call_args.args
    assert sent_queue_url == settings.pdf_response_queue_url
    assert sent_envelope.order_id == envelope.order_id
    assert sent_envelope.payload["success"] is True
    assert sent_envelope.payload["s3_key"] == key
    assert sent_envelope.payload["error_message"] is None


def test_handle_incomplete_data_publishes_failure_without_storing(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    envelope = _envelope(_payload(items=[]))

    fake_s3 = MagicMock()
    monkeypatch.setattr(gerar_pdf, "S3Client", lambda _settings: fake_s3)

    fake_sqs = MagicMock()
    monkeypatch.setattr(gerar_pdf, "SqsClient", lambda _settings: fake_sqs)

    gerar_pdf.handle(envelope, settings)

    fake_s3.put_object.assert_not_called()

    fake_sqs.send.assert_called_once()
    _, sent_envelope = fake_sqs.send.call_args.args
    assert sent_envelope.payload["success"] is False
    assert sent_envelope.payload["s3_key"] is None
    assert sent_envelope.payload["error_message"]
