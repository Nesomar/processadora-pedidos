"""Fixtures compartilhadas: clients reais contra o Ministack local, pulando se indisponível."""

import os
import socket
from urllib.parse import urlparse

import pytest
from pedidos_shared import DynamoDbClient, Settings, SqsClient

from order_processor.config import get_settings


def _ministack_available() -> bool:
    endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
    parsed = urlparse(endpoint)
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture
def settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def dynamodb_client(settings: Settings) -> DynamoDbClient:
    if not _ministack_available():
        pytest.skip("Ministack local indisponível (infra/docker-compose.yml up -d)")
    return DynamoDbClient(settings)


@pytest.fixture
def sqs_client(settings: Settings) -> SqsClient:
    if not _ministack_available():
        pytest.skip("Ministack local indisponível (infra/docker-compose.yml up -d)")
    return SqsClient(settings)


@pytest.fixture
def table_name(settings: Settings) -> str:
    return settings.orders_table_name
