"""Teste de create_or_verify_queue — fila + DLQ + maxReceiveCount=3 (data-model.md)."""

import json
import uuid

import pytest

from resources.queues import create_or_verify_queue

QUEUE_NAMES = [
    "solicitar_pedido_queue",
    "editar_pedido_queue",
    "cancelar_pedido_queue",
    "validar_pedido_queue",
    "validar_pedido_response_queue",
    "pdf_request_queue",
    "pdf_response_queue",
    "s3_notifications_queue",
    "pedido_lines_queue",
]


@pytest.mark.parametrize("base_name", QUEUE_NAMES)
def test_create_or_verify_queue_creates_queue_with_dlq(sqs_client, base_name: str) -> None:
    suffix = uuid.uuid4().hex[:8]
    name = f"{base_name}_{suffix}"
    dlq_name = f"{name}_dlq"

    queue_url = create_or_verify_queue(sqs_client, name, dlq_name)

    attrs = sqs_client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["RedrivePolicy", "VisibilityTimeout", "MessageRetentionPeriod"],
    )["Attributes"]

    redrive = json.loads(attrs["RedrivePolicy"])
    assert redrive["maxReceiveCount"] == 3
    assert attrs["VisibilityTimeout"] == "60"
    assert attrs["MessageRetentionPeriod"] == str(4 * 24 * 3600)

    dlq_url = sqs_client.get_queue_url(QueueName=dlq_name)["QueueUrl"]
    dlq_arn = sqs_client.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]
    assert redrive["deadLetterTargetArn"] == dlq_arn
