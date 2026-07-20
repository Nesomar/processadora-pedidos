"""Teste de create_or_verify_bucket — bucket + notificação uploads/*.txt (data-model.md)."""

import uuid

from resources.bucket import create_or_verify_bucket


def _make_notification_queue_arn(sqs_client) -> str:
    name = f"s3_notifications_queue_{uuid.uuid4().hex[:8]}"
    queue_url = sqs_client.create_queue(QueueName=name)["QueueUrl"]
    return sqs_client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]


def test_create_or_verify_bucket_creates_bucket_and_notification(s3_client, sqs_client) -> None:
    bucket_name = f"pedidos-bucket-test-{uuid.uuid4().hex[:8]}"
    queue_arn = _make_notification_queue_arn(sqs_client)

    create_or_verify_bucket(s3_client, bucket_name, queue_arn)

    buckets = {b["Name"] for b in s3_client.list_buckets()["Buckets"]}
    assert bucket_name in buckets

    config = s3_client.get_bucket_notification_configuration(Bucket=bucket_name)
    queue_configs = config["QueueConfigurations"]
    assert len(queue_configs) == 1
    assert queue_configs[0]["QueueArn"] == queue_arn
    assert queue_configs[0]["Events"] == ["s3:ObjectCreated:*"]

    rules = {
        rule["Name"]: rule["Value"] for rule in queue_configs[0]["Filter"]["Key"]["FilterRules"]
    }
    assert rules == {"prefix": "uploads/", "suffix": ".txt"}


def test_create_or_verify_bucket_is_idempotent_and_does_not_duplicate_notification(
    s3_client, sqs_client
) -> None:
    bucket_name = f"pedidos-bucket-test-{uuid.uuid4().hex[:8]}"
    queue_arn = _make_notification_queue_arn(sqs_client)

    create_or_verify_bucket(s3_client, bucket_name, queue_arn)
    create_or_verify_bucket(s3_client, bucket_name, queue_arn)

    config = s3_client.get_bucket_notification_configuration(Bucket=bucket_name)
    assert len(config["QueueConfigurations"]) == 1


def test_create_or_verify_bucket_does_not_overwrite_divergent_notification(
    s3_client, sqs_client
) -> None:
    bucket_name = f"pedidos-bucket-test-{uuid.uuid4().hex[:8]}"
    expected_queue_arn = _make_notification_queue_arn(sqs_client)
    other_queue_arn = _make_notification_queue_arn(sqs_client)

    # configura manualmente a notificação apontando para uma fila diferente da esperada
    s3_client.create_bucket(Bucket=bucket_name)
    s3_client.put_bucket_notification_configuration(
        Bucket=bucket_name,
        NotificationConfiguration={
            "QueueConfigurations": [
                {
                    "Id": "manual-config",
                    "QueueArn": other_queue_arn,
                    "Events": ["s3:ObjectCreated:*"],
                }
            ]
        },
    )

    create_or_verify_bucket(s3_client, bucket_name, expected_queue_arn)

    config = s3_client.get_bucket_notification_configuration(Bucket=bucket_name)
    assert len(config["QueueConfigurations"]) == 1
    assert config["QueueConfigurations"][0]["QueueArn"] == other_queue_arn
