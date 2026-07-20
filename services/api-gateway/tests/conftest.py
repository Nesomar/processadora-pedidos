"""Fixtures compartilhadas: TestClient com clients mockados, e cliente real p/ integração."""

import os
import socket
from unittest.mock import MagicMock
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from pedidos_shared import Settings

from api_gateway.config import get_settings
from api_gateway.deps import get_dynamodb_client, get_sqs_client
from api_gateway.main import app

FAKE_SETTINGS = Settings(
    aws_endpoint_url="http://localhost:4566",
    aws_region="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    processed_messages_table_name="processed_messages",
    orders_table_name="orders",
    solicitar_pedido_queue_url="http://localhost:4566/000000000000/solicitar_pedido_queue",
    editar_pedido_queue_url="http://localhost:4566/000000000000/editar_pedido_queue",
    cancelar_pedido_queue_url="http://localhost:4566/000000000000/cancelar_pedido_queue",
)


@pytest.fixture
def fake_sqs_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def fake_dynamodb_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(fake_sqs_client: MagicMock, fake_dynamodb_client: MagicMock) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: FAKE_SETTINGS
    app.dependency_overrides[get_sqs_client] = lambda: fake_sqs_client
    app.dependency_overrides[get_dynamodb_client] = lambda: fake_dynamodb_client
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _ministack_available() -> bool:
    endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
    parsed = urlparse(endpoint)
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture
def integration_client() -> TestClient:
    if not _ministack_available():
        pytest.skip("Ministack local indisponível (infra/docker-compose.yml up -d)")
    return TestClient(app)
