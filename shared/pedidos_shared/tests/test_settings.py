"""Testes de Settings (data-model.md — 4 campos de conexão + processed_messages_table_name)."""

import pytest
from pydantic import ValidationError

from pedidos_shared.settings import Settings

REQUIRED_ENV = {
    "AWS_ENDPOINT_URL": "http://localhost:4566",
    "AWS_REGION": "us-east-1",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
    "PROCESSED_MESSAGES_TABLE_NAME": "processed_messages",
}

ALL_SETTINGS_ENV_VARS = REQUIRED_ENV.keys() | {
    "ORDERS_TABLE_NAME",
    "PEDIDOS_BUCKET_NAME",
    "SOLICITAR_PEDIDO_QUEUE_URL",
    "EDITAR_PEDIDO_QUEUE_URL",
    "CANCELAR_PEDIDO_QUEUE_URL",
    "VALIDAR_PEDIDO_QUEUE_URL",
    "VALIDAR_PEDIDO_RESPONSE_QUEUE_URL",
    "PDF_REQUEST_QUEUE_URL",
    "PDF_RESPONSE_QUEUE_URL",
    "S3_NOTIFICATIONS_QUEUE_URL",
    "PEDIDO_LINES_QUEUE_URL",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ALL_SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)


def test_settings_loads_with_required_values(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)

    settings = Settings()

    assert settings.aws_endpoint_url == "http://localhost:4566"
    assert settings.aws_region == "us-east-1"
    assert settings.aws_access_key_id == "test"
    assert settings.aws_secret_access_key == "test"
    assert settings.processed_messages_table_name == "processed_messages"
    assert settings.orders_table_name == "orders"
    assert settings.pedidos_bucket_name == "pedidos-bucket"
    assert settings.solicitar_pedido_queue_url is None


@pytest.mark.parametrize(
    "missing",
    [
        "AWS_ENDPOINT_URL",
        "AWS_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "PROCESSED_MESSAGES_TABLE_NAME",
    ],
)
def test_settings_fails_clearly_when_required_var_missing(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    _set_required(monkeypatch)
    monkeypatch.delenv(missing, raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert missing.lower() in str(exc_info.value)


def test_settings_reads_optional_queue_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("SOLICITAR_PEDIDO_QUEUE_URL", "http://localhost:4566/queue/solicitar")

    settings = Settings()

    assert settings.solicitar_pedido_queue_url == "http://localhost:4566/queue/solicitar"
    assert settings.editar_pedido_queue_url is None
