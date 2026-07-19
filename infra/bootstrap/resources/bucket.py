"""Criação/verificação idempotente do bucket + notificação de evento (research.md #5)."""

import logging

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_NOTIFICATION_ID = "uploads-txt-to-s3-notifications-queue"


def _expected_notification(queue_arn: str) -> dict:
    return {
        "QueueConfigurations": [
            {
                "Id": _NOTIFICATION_ID,
                "QueueArn": queue_arn,
                "Events": ["s3:ObjectCreated:*"],
                "Filter": {
                    "Key": {
                        "FilterRules": [
                            {"Name": "prefix", "Value": "uploads/"},
                            {"Name": "suffix", "Value": ".txt"},
                        ]
                    }
                },
            }
        ]
    }


def create_or_verify_bucket(s3_client, bucket_name: str, notification_queue_arn: str) -> None:
    """Cria `bucket_name` (se não existir) e garante a notificação `uploads/*.txt` -> fila.

    A notificação só é escrita se a configuração existente for diferente da esperada — o put é
    uma substituição completa da config de notificação do bucket, então reescrever
    incondicionalmente arriscaria apagar outras regras (contrato regra 5).
    """
    try:
        s3_client.create_bucket(Bucket=bucket_name)
    except ClientError as error:
        code = error.response["Error"]["Code"]
        if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise

    existing = s3_client.get_bucket_notification_configuration(Bucket=bucket_name)
    existing.pop("ResponseMetadata", None)
    expected = _expected_notification(notification_queue_arn)

    if existing == expected:
        return
    if not existing.get("QueueConfigurations"):
        s3_client.put_bucket_notification_configuration(
            Bucket=bucket_name, NotificationConfiguration=expected
        )
        return

    logger.warning(
        "bucket %s já tem notificação de evento divergente da esperada: %s", bucket_name, existing
    )
