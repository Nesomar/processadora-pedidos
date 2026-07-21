"""Fixtures compartilhadas do lambda-line-processor."""

import os
import socket
from urllib.parse import urlparse

import pytest
from pedidos_shared import SqsClient

from lambda_line_processor.config import LambdaLineProcessorSettings, get_settings


def _ministack_available() -> bool:
    endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
    parsed = urlparse(endpoint)
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=1):
            return True
    except OSError:
        return False


def _api_gateway_available(base_url: str) -> bool:
    parsed = urlparse(base_url)
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture
def settings() -> LambdaLineProcessorSettings:
    get_settings.cache_clear()
    return LambdaLineProcessorSettings(
        aws_endpoint_url="http://localhost:4566",
        aws_region="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        processed_messages_table_name="processed_messages",
        pedido_lines_queue_url="http://localhost:4566/000000000000/pedido_lines_queue",
        api_gateway_base_url=os.environ.get("API_GATEWAY_BASE_URL", "http://localhost:8000"),
    )


@pytest.fixture
def sqs_client(settings: LambdaLineProcessorSettings) -> SqsClient:
    if not _ministack_available():
        pytest.skip("Ministack local indisponivel (infra/docker-compose.yml up -d)")
    return SqsClient(settings)


@pytest.fixture
def api_gateway_available(settings: LambdaLineProcessorSettings) -> None:
    if not _api_gateway_available(settings.api_gateway_base_url):
        pytest.skip("api-gateway indisponivel (infra/docker-compose.yml up -d)")
