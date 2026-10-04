"""Teste de S3Client.put_object — ContentType opcional (006-pdf-generator research.md #2)."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from pedidos_shared.clients.s3 import ObjectNotFoundError, S3Client
from pedidos_shared.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        aws_endpoint_url="http://localhost:4566",
        aws_region="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        processed_messages_table_name="processed_messages",
    )


@pytest.fixture
def fake_boto_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    fake: MagicMock = MagicMock()
    monkeypatch.setattr("pedidos_shared.clients.s3.boto3.client", lambda *args, **kwargs: fake)
    return fake


def test_put_object_without_content_type_omits_it(
    settings: Settings, fake_boto_client: MagicMock
) -> None:
    S3Client(settings).put_object("bucket", "key.bin", b"data")

    kwargs: dict[str, Any] = fake_boto_client.put_object.call_args.kwargs
    assert kwargs == {"Bucket": "bucket", "Key": "key.bin", "Body": b"data"}


def test_put_object_with_content_type_forwards_it(
    settings: Settings, fake_boto_client: MagicMock
) -> None:
    S3Client(settings).put_object("bucket", "invoice.pdf", b"%PDF-", content_type="application/pdf")

    kwargs: dict[str, Any] = fake_boto_client.put_object.call_args.kwargs
    assert kwargs == {
        "Bucket": "bucket",
        "Key": "invoice.pdf",
        "Body": b"%PDF-",
        "ContentType": "application/pdf",
    }


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "GetObject")


def test_get_object_returns_bytes(settings: Settings, fake_boto_client: MagicMock) -> None:
    fake_boto_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"%PDF-")}

    assert S3Client(settings).get_object("bucket", "k.pdf") == b"%PDF-"


def test_get_object_no_such_key_raises_object_not_found(
    settings: Settings, fake_boto_client: MagicMock
) -> None:
    fake_boto_client.get_object.side_effect = _client_error("NoSuchKey")

    with pytest.raises(ObjectNotFoundError):
        S3Client(settings).get_object("bucket", "k.pdf")


def test_get_object_other_client_error_propagates(
    settings: Settings, fake_boto_client: MagicMock
) -> None:
    fake_boto_client.get_object.side_effect = _client_error("AccessDenied")

    with pytest.raises(ClientError):
        S3Client(settings).get_object("bucket", "k.pdf")
