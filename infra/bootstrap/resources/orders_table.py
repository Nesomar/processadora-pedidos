"""Criação/verificação idempotente da tabela `orders` (PK/SK + GSI1 + GSI2, research.md #6)."""

import logging

logger = logging.getLogger(__name__)


def create_or_verify_orders_table(dynamodb_client, table_name: str) -> None:
    """Cria `table_name` com `PK`/`SK` e os índices `GSI1`/`GSI2` já na definição inicial.

    GSIs do DynamoDB não podem ser adicionados via update de forma simples no Ministack — por
    isso ambos entram na chamada de criação (contrato regra 4).
    """
    try:
        dynamodb_client.create_table(
            TableName=table_name,
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        )
        dynamodb_client.get_waiter("table_exists").wait(TableName=table_name)
    except dynamodb_client.exceptions.ResourceInUseException:
        description = dynamodb_client.describe_table(TableName=table_name)["Table"]
        gsi_names = {gsi["IndexName"] for gsi in description.get("GlobalSecondaryIndexes", [])}
        if gsi_names != {"GSI1", "GSI2"}:
            logger.warning(
                "tabela %s existe com GSIs divergentes do esperado: %s", table_name, gsi_names
            )
