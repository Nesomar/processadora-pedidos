import uuid
from datetime import UTC, datetime

from pedidos_shared import MessageEnvelope, S3Client, Settings

from pdf_generator.adapters import worker_loop
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


def _envelope() -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        order_id=str(uuid.uuid4()),
        occurred_at=datetime.now(UTC),
        payload={
            "customer_name": "Maria Silva",
            "customer_document": "52998224725",
            "items": [_ITEM],
            "subtotal": "29.97",
            "discount_total": "3.15",
            "total": "26.82",
        },
    )


def test_reprocessing_integration_same_message_twice_publishes_one_response_and_one_object(
    sqs_client, s3_client: S3Client, settings: Settings
) -> None:
    envelope = _envelope()

    sqs_client.send(settings.pdf_request_queue_url, envelope)
    worker_loop.process_once(sqs_client, settings.pdf_request_queue_url, gerar_pdf.handle, settings)
    sqs_client.send(settings.pdf_request_queue_url, envelope)
    worker_loop.process_once(sqs_client, settings.pdf_request_queue_url, gerar_pdf.handle, settings)

    responses = sqs_client.receive(settings.pdf_response_queue_url)
    matching = [message for message in responses if message.order_id == envelope.order_id]
    assert len(matching) == 1

    s3_key = matching[0].payload["s3_key"]
    pdf_bytes = s3_client.get_object(settings.pedidos_bucket_name, s3_key)
    assert pdf_bytes.startswith(b"%PDF-")
