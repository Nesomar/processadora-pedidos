"""Integração real (Ministack): upload real, notificação real do bucket, dedup real no DynamoDB.

O bucket já tem a notificação `uploads/*.txt` -> `s3_notifications_queue` configurada por
`002-infraestrutura-local` — o upload abaixo dispara a notificação real automaticamente, sem
precisar construir uma mensagem sintética. Redelivery genuína do SQS pelo mesmo `MessageId`
depende do timeout de visibilidade da fila (lento/frágil de simular em teste); a segunda entrega é
simulada reaproveitando o `MessageId` nativo real capturado na primeira entrega — a checagem de
idempotência em si roda contra o DynamoDB real, só o transporte SQS da segunda entrega é um duble.
"""

import time
import uuid
from unittest.mock import MagicMock

from pedidos_shared import (
    S3Client,
    Settings,
    SqsClient,
    is_message_processed,
    mark_message_processed,
)

from file_consumer.adapters import worker_loop
from file_consumer.handlers import processar_notificacao


def _record(record_type: str, *fields: tuple[str, int, str]) -> str:
    line = record_type
    for text, width, align in fields:
        line += text.rjust(width, "0") if align == "R0" else text.ljust(width)
    return line.ljust(200)


def _valid_file_bytes(customer_id: str) -> bytes:
    header = _record("0", ("20260720", 8, "L"), ("TESTE", 30, "L"), ("1", 6, "R0"))
    pedido = _record(
        "1",
        ("SOLICITAR", 10, "L"),
        ("", 36, "L"),
        (customer_id, 20, "L"),
        ("CLIENTE IDEMPOTENCIA", 60, "L"),
        ("11111111111", 14, "R0"),
        ("1", 2, "R0"),
    )
    item = _record("2", ("1", 8, "R0"), ("10", 8, "R0"))
    trailer = _record("9", ("1", 8, "R0"), ("1", 8, "R0"))
    return ("\n".join([header, pedido, item, trailer]) + "\n").encode("utf-8")


def _receive_real_notification_for(
    sqs_client: SqsClient, queue_url: str, key: str
) -> tuple[dict, str, str]:
    """Poll até a notificação real do upload (disparada pelo bucket) aparecer na fila,
    descartando qualquer mensagem que não referencie `key` (ex.: `s3:TestEvent`)."""
    for _ in range(10):
        for body, receipt, message_id in sqs_client.receive_raw_with_receipt(queue_url):
            records = body.get("Records") or []
            if any(record.get("s3", {}).get("object", {}).get("key") == key for record in records):
                return body, receipt, message_id
            sqs_client.delete(queue_url, receipt)
        time.sleep(0.5)
    raise AssertionError(f"notificação real para {key!r} não chegou a tempo")


def test_reprocessing_integration_same_notification_id_publishes_lines_once(
    sqs_client: SqsClient, s3_client: S3Client, settings: Settings
) -> None:
    customer_id = f"CUST{uuid.uuid4().hex[:8]}"
    key = f"uploads/idempotencia-{uuid.uuid4().hex[:8]}.txt"
    s3_client.put_object(settings.pedidos_bucket_name, key, _valid_file_bytes(customer_id))

    body, receipt_handle, native_message_id = _receive_real_notification_for(
        sqs_client, settings.s3_notifications_queue_url, key
    )
    assert is_message_processed(native_message_id, worker_loop.CONSUMER_NAME, settings) is False

    # primeira entrega real: processa (S3 + parse reais), marca (DynamoDB real), confirma (SQS real)
    processar_notificacao.handle(body, settings)
    mark_message_processed(native_message_id, worker_loop.CONSUMER_NAME, settings)
    sqs_client.delete(settings.s3_notifications_queue_url, receipt_handle)

    published = [
        raw for raw, _, _ in sqs_client.receive_raw_with_receipt(settings.pedido_lines_queue_url)
    ]
    matching = [r for r in published if r["parsed"]["customer_id"] == customer_id]
    assert len(matching) == 1
    assert is_message_processed(native_message_id, worker_loop.CONSUMER_NAME, settings) is True

    # segunda entrega simulada do MESMO MessageId nativo (redelivery real do SQS manteria o
    # mesmo MessageId) — a checagem de dedup abaixo é real (DynamoDB), só o transporte é um duble
    stub_sqs = MagicMock(spec=SqsClient)
    stub_sqs.receive_raw_with_receipt.return_value = [
        (body, "receipt-redelivery", native_message_id)
    ]
    handler_spy = MagicMock(wraps=processar_notificacao.handle)

    worker_loop.process_once(stub_sqs, settings.s3_notifications_queue_url, handler_spy, settings)

    handler_spy.assert_not_called()
    stub_sqs.delete.assert_called_once_with(
        settings.s3_notifications_queue_url, "receipt-redelivery"
    )
