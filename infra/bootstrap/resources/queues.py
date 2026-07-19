"""Criação/verificação idempotente de filas SQS + DLQ (research.md #3, contrato regra 3)."""

import json
import logging

logger = logging.getLogger(__name__)

VISIBILITY_TIMEOUT_SECONDS = "60"
MESSAGE_RETENTION_SECONDS = str(4 * 24 * 3600)
MAX_RECEIVE_COUNT = 3


def _create_or_get_queue_url(sqs_client, name: str, attributes: dict[str, str]) -> str:
    try:
        response = sqs_client.create_queue(QueueName=name, Attributes=attributes)
        return response["QueueUrl"]
    except sqs_client.exceptions.QueueNameExists:
        return sqs_client.get_queue_url(QueueName=name)["QueueUrl"]


def _queue_arn(sqs_client, queue_url: str) -> str:
    attrs = sqs_client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
    return attrs["Attributes"]["QueueArn"]


def create_or_verify_queue(sqs_client, name: str, dlq_name: str) -> str:
    """Cria (ou reaproveita) `name` com sua `dlq_name`, `maxReceiveCount=3` (constitution I.4).

    Configuração divergente num recurso pré-existente vira log de aviso, não falha
    (constitution I.5 / research.md #3).
    """
    dlq_url = _create_or_get_queue_url(
        sqs_client,
        dlq_name,
        {
            "VisibilityTimeout": VISIBILITY_TIMEOUT_SECONDS,
            "MessageRetentionPeriod": MESSAGE_RETENTION_SECONDS,
        },
    )
    dlq_arn = _queue_arn(sqs_client, dlq_url)

    redrive_policy = json.dumps(
        {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": MAX_RECEIVE_COUNT}
    )
    queue_url = _create_or_get_queue_url(
        sqs_client,
        name,
        {
            "VisibilityTimeout": VISIBILITY_TIMEOUT_SECONDS,
            "MessageRetentionPeriod": MESSAGE_RETENTION_SECONDS,
            "RedrivePolicy": redrive_policy,
        },
    )

    attrs = sqs_client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["VisibilityTimeout", "MessageRetentionPeriod", "RedrivePolicy"],
    )["Attributes"]
    existing_max_receive = json.loads(attrs.get("RedrivePolicy", "{}")).get("maxReceiveCount")
    if (
        attrs.get("VisibilityTimeout") != VISIBILITY_TIMEOUT_SECONDS
        or attrs.get("MessageRetentionPeriod") != MESSAGE_RETENTION_SECONDS
        or existing_max_receive != MAX_RECEIVE_COUNT
    ):
        logger.warning("fila %s existe com configuração divergente da esperada: %s", name, attrs)

    return queue_url
