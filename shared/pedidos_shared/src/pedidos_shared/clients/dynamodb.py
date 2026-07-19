"""Cliente fino sobre DynamoDB (constitution VIII — wrapper síncrono, DI de Settings)."""

from typing import Any

import boto3

from pedidos_shared.settings import Settings


class DynamoDbClient:
    def __init__(self, settings: Settings) -> None:
        self._resource = boto3.resource(
            "dynamodb",
            endpoint_url=settings.aws_endpoint_url,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def table(self, name: str) -> Any:
        return self._resource.Table(name)

    def put_item(self, table_name: str, item: dict[str, Any], **kwargs: Any) -> None:
        self.table(table_name).put_item(Item=item, **kwargs)

    def get_item(self, table_name: str, key: dict[str, Any]) -> dict[str, Any] | None:
        response = self.table(table_name).get_item(Key=key)
        return response.get("Item")
