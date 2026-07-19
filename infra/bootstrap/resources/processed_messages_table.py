"""Criação/verificação idempotente da tabela `processed_messages` (PK simples + TTL)."""

import logging

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def create_or_verify_processed_messages_table(dynamodb_client, table_name: str) -> None:
    """Cria `table_name` (PK `PK`) e habilita TTL nativo no atributo `ttl`."""
    try:
        dynamodb_client.create_table(
            TableName=table_name,
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"}],
        )
        dynamodb_client.get_waiter("table_exists").wait(TableName=table_name)
    except dynamodb_client.exceptions.ResourceInUseException:
        description = dynamodb_client.describe_table(TableName=table_name)["Table"]
        key_schema = {k["AttributeName"]: k["KeyType"] for k in description["KeySchema"]}
        if key_schema != {"PK": "HASH"}:
            logger.warning(
                "tabela %s existe com key schema divergente do esperado: %s",
                table_name,
                key_schema,
            )

    try:
        dynamodb_client.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
        )
    except ClientError as error:
        code = error.response["Error"]["Code"]
        if code != "ValidationException":
            raise
        logger.info("TTL de %s já configurado — %s", table_name, error.response["Error"]["Message"])
