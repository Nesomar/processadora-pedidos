"""Fixtures compartilhadas do pdf-generator."""

import os
import socket
from urllib.parse import urlparse

import pytest
from pedidos_shared import S3Client, Settings, SqsClient

from pdf_generator.config import get_settings


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
    return Settings(
        aws_endpoint_url="http://localhost:4566",
        aws_region="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        processed_messages_table_name="processed_messages",
        pedidos_bucket_name="pedidos-bucket",
        pdf_request_queue_url="http://localhost:4566/000000000000/pdf_request_queue",
        pdf_response_queue_url="http://localhost:4566/000000000000/pdf_response_queue",
    )


@pytest.fixture
def sqs_client(settings: Settings) -> SqsClient:
    if not _ministack_available():
        pytest.skip("Ministack local indisponivel (infra/docker-compose.yml up -d)")
    return SqsClient(settings)


@pytest.fixture
def s3_client(settings: Settings) -> S3Client:
    if not _ministack_available():
        pytest.skip("Ministack local indisponivel (infra/docker-compose.yml up -d)")
    return S3Client(settings)
