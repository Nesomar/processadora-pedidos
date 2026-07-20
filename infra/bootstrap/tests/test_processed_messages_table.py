"""Teste de create_or_verify_processed_messages_table — PK + TTL habilitado (data-model.md)."""

import uuid

from resources.processed_messages_table import create_or_verify_processed_messages_table


def test_create_or_verify_processed_messages_table_creates_pk_and_ttl(dynamodb_client) -> None:
    table_name = f"processed_messages_test_{uuid.uuid4().hex[:8]}"

    create_or_verify_processed_messages_table(dynamodb_client, table_name)

    description = dynamodb_client.describe_table(TableName=table_name)["Table"]
    key_schema = {k["AttributeName"]: k["KeyType"] for k in description["KeySchema"]}
    assert key_schema == {"PK": "HASH"}

    ttl = dynamodb_client.describe_time_to_live(TableName=table_name)["TimeToLiveDescription"]
    assert ttl["AttributeName"] == "ttl"
    assert ttl["TimeToLiveStatus"] in ("ENABLED", "ENABLING")
