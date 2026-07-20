"""Leitura de `orders` — só leitura (research.md #3); nenhum método de escrita exposto."""

from pedidos_shared import DynamoDbClient, Order


def get_by_id(dynamodb: DynamoDbClient, table_name: str, order_id: str) -> Order | None:
    item = dynamodb.get_item(table_name, {"PK": f"ORDER#{order_id}", "SK": "METADATA"})
    if item is None:
        return None
    return Order.model_validate(item)


def query_by_customer(dynamodb: DynamoDbClient, table_name: str, customer_id: str) -> list[Order]:
    table = dynamodb.table(table_name)
    response = table.query(
        IndexName="GSI1",
        KeyConditionExpression="GSI1PK = :pk",
        ExpressionAttributeValues={":pk": f"CUSTOMER#{customer_id}"},
        ScanIndexForward=False,
    )
    return [Order.model_validate(item) for item in response.get("Items", [])]
