"""Fixtures compartilhadas do order-validator."""

import os
import socket
from urllib.parse import urlparse

import pytest
from pedidos_shared import Settings, SqsClient

from order_validator.config import OrderValidatorSettings, get_settings


def _ministack_available() -> bool:
    endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
    parsed = urlparse(endpoint)
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture
def settings() -> OrderValidatorSettings:
    get_settings.cache_clear()
    return OrderValidatorSettings(
        aws_endpoint_url="http://localhost:4566",
        aws_region="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        processed_messages_table_name="processed_messages",
        validar_pedido_queue_url="http://localhost:4566/000000000000/validar_pedido_queue",
        validar_pedido_response_queue_url="http://localhost:4566/000000000000/validar_pedido_response_queue",
        catalog_products_base_url="https://dummyjson.com",
    )


@pytest.fixture
def sqs_client(settings: Settings) -> SqsClient:
    if not _ministack_available():
        pytest.skip("Ministack local indisponivel (infra/docker-compose.yml up -d)")
    return SqsClient(settings)
