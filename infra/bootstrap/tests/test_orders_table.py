"""Teste de create_or_verify_orders_table — PK/SK + GSI1 + GSI2 (data-model.md)."""

import uuid

from resources.orders_table import create_or_verify_orders_table


def test_create_or_verify_orders_table_creates_pk_sk_and_gsis(dynamodb_client) -> None:
    table_name = f"orders_test_{uuid.uuid4().hex[:8]}"

    create_or_verify_orders_table(dynamodb_client, table_name)

    description = dynamodb_client.describe_table(TableName=table_name)["Table"]

    key_schema = {k["AttributeName"]: k["KeyType"] for k in description["KeySchema"]}
    assert key_schema == {"PK": "HASH", "SK": "RANGE"}

    gsis = {gsi["IndexName"]: gsi for gsi in description.get("GlobalSecondaryIndexes", [])}
    assert set(gsis) == {"GSI1", "GSI2"}

    gsi1_keys = {k["AttributeName"]: k["KeyType"] for k in gsis["GSI1"]["KeySchema"]}
    assert gsi1_keys == {"GSI1PK": "HASH", "GSI1SK": "RANGE"}

    gsi2_keys = {k["AttributeName"]: k["KeyType"] for k in gsis["GSI2"]["KeySchema"]}
    assert gsi2_keys == {"GSI2PK": "HASH", "GSI2SK": "RANGE"}
