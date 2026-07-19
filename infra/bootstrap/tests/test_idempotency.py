"""Teste de idempotência: rodar create_or_verify_* duas vezes não falha nem duplica (FR-006)."""

import uuid

from resources.orders_table import create_or_verify_orders_table
from resources.processed_messages_table import create_or_verify_processed_messages_table
from resources.queues import create_or_verify_queue


def test_create_or_verify_queue_twice_does_not_duplicate(sqs_client) -> None:
    suffix = uuid.uuid4().hex[:8]
    name = f"idempotency_queue_{suffix}"
    dlq_name = f"{name}_dlq"

    first_url = create_or_verify_queue(sqs_client, name, dlq_name)
    second_url = create_or_verify_queue(sqs_client, name, dlq_name)

    assert first_url == second_url

    all_urls = sqs_client.list_queues(QueueNamePrefix=name).get("QueueUrls", [])
    matching = [url for url in all_urls if url.rsplit("/", 1)[-1] == name]
    assert len(matching) == 1


def test_create_or_verify_queue_with_drifted_attributes_logs_warning_not_exception(
    sqs_client,
) -> None:
    suffix = uuid.uuid4().hex[:8]
    name = f"idempotency_drift_queue_{suffix}"
    dlq_name = f"{name}_dlq"

    # cria a fila manualmente, sem DLQ/atributos esperados — simula recurso pré-existente divergente
    sqs_client.create_queue(QueueName=name)

    queue_url = create_or_verify_queue(sqs_client, name, dlq_name)

    assert queue_url == sqs_client.get_queue_url(QueueName=name)["QueueUrl"]


def test_create_or_verify_orders_table_twice_does_not_raise(dynamodb_client) -> None:
    table_name = f"orders_idempotency_{uuid.uuid4().hex[:8]}"

    create_or_verify_orders_table(dynamodb_client, table_name)
    create_or_verify_orders_table(dynamodb_client, table_name)

    assert dynamodb_client.list_tables()["TableNames"].count(table_name) == 1


def test_create_or_verify_processed_messages_table_twice_does_not_raise(dynamodb_client) -> None:
    table_name = f"processed_messages_idempotency_{uuid.uuid4().hex[:8]}"

    create_or_verify_processed_messages_table(dynamodb_client, table_name)
    create_or_verify_processed_messages_table(dynamodb_client, table_name)

    assert dynamodb_client.list_tables()["TableNames"].count(table_name) == 1
    ttl = dynamodb_client.describe_time_to_live(TableName=table_name)["TimeToLiveDescription"]
    assert ttl["AttributeName"] == "ttl"
