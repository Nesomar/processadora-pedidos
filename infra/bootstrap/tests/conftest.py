"""Fixtures compartilhadas: clients boto3 contra o Ministack local, pulando se indisponível."""

import os
import socket
from urllib.parse import urlparse

import pytest

from resources.aws_clients import build_client

os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")


def _ministack_available() -> bool:
    parsed = urlparse(os.environ["AWS_ENDPOINT_URL"])
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=1):
            return True
    except OSError:
        return False


def _client(service: str):
    return build_client(service)


@pytest.fixture(autouse=True)
def _skip_without_ministack() -> None:
    if not _ministack_available():
        pytest.skip("Ministack local indisponível (infra/docker-compose.yml up -d)")


@pytest.fixture
def sqs_client():
    return _client("sqs")


@pytest.fixture
def dynamodb_client():
    return _client("dynamodb")


@pytest.fixture
def s3_client():
    return _client("s3")
