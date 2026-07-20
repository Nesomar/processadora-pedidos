"""Providers de dependência FastAPI — únicos pontos que instanciam clients reais."""

from typing import Annotated

from fastapi import Depends
from pedidos_shared import DynamoDbClient, Settings, SqsClient

from api_gateway.config import get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_sqs_client(settings: SettingsDep) -> SqsClient:
    return SqsClient(settings)


def get_dynamodb_client(settings: SettingsDep) -> DynamoDbClient:
    return DynamoDbClient(settings)


SqsClientDep = Annotated[SqsClient, Depends(get_sqs_client)]
DynamoDbClientDep = Annotated[DynamoDbClient, Depends(get_dynamodb_client)]
