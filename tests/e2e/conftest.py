"""Fixtures compartilhadas da suite e2e (research.md #3)."""

import os

import httpx
import pytest
from pedidos_shared import S3Client, Settings

_SERVICE_PORTS = {
    "api-gateway": 8000,
    "order-processor": 8080,
    "order-validator": 8081,
    "pdf-generator": 8082,
    "file-consumer": 8083,
    "lambda-line-processor": 8084,
}

API_GATEWAY_BASE_URL = os.environ.get("API_GATEWAY_BASE_URL", "http://localhost:8000")


def _health_ok(port: int) -> bool:
    try:
        with httpx.Client(timeout=2.0) as client:
            return client.get(f"http://localhost:{port}/health").status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session", autouse=True)
def _ambiente_no_ar() -> None:
    indisponiveis = [
        name for name, port in _SERVICE_PORTS.items() if not _health_ok(port)
    ]
    if indisponiveis:
        pytest.exit(
            f"ambiente incompleto — serviço(s) inacessível(is): {', '.join(indisponiveis)} "
            "(rode 'make up' antes de 'make e2e')",
            returncode=1,
        )


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        aws_endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
        processed_messages_table_name=os.environ.get(
            "PROCESSED_MESSAGES_TABLE_NAME", "processed_messages"
        ),
        pedidos_bucket_name=os.environ.get("PEDIDOS_BUCKET_NAME", "pedidos-bucket"),
    )


@pytest.fixture(scope="session")
def s3_client(settings: Settings) -> S3Client:
    return S3Client(settings)


@pytest.fixture
def api_gateway():
    with httpx.Client(base_url=API_GATEWAY_BASE_URL, timeout=10.0) as client:
        yield client
