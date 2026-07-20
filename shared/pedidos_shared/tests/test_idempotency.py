"""Teste de mark_message_processed (research.md #4 — write condicional + TTL)."""

from typing import Any

import pytest
from botocore.exceptions import ClientError

from pedidos_shared.idempotency import is_message_processed, mark_message_processed
from pedidos_shared.settings import Settings


class _FakeTable:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def put_item(self, Item: dict[str, Any], **kwargs: Any) -> None:  # noqa: N803
        pk = Item["PK"]
        if pk in self._store:
            raise ClientError(
                {
                    "Error": {
                        "Code": "ConditionalCheckFailedException",
                        "Message": "The conditional request failed",
                    }
                },
                "PutItem",
            )
        self._store[pk] = Item

    def get_item(self, Key: dict[str, Any]) -> dict[str, Any]:  # noqa: N803
        item = self._store.get(Key["PK"])
        return {"Item": item} if item is not None else {}


class _FakeResource:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}

    def Table(self, name: str) -> _FakeTable:  # noqa: N802
        return _FakeTable(self.store)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        aws_endpoint_url="http://localhost:4566",
        aws_region="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        processed_messages_table_name="processed_messages",
    )


@pytest.fixture(autouse=True)
def _fake_dynamodb(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_resource = _FakeResource()
    monkeypatch.setattr(
        "pedidos_shared.clients.dynamodb.boto3.resource",
        lambda *args, **kwargs: fake_resource,
    )


def test_first_call_processes_second_call_indicates_duplicate(settings: Settings) -> None:
    first = mark_message_processed("msg-1", "quickstart", settings)
    second = mark_message_processed("msg-1", "quickstart", settings)

    assert first is False
    assert second is True


def test_different_message_ids_both_process(settings: Settings) -> None:
    assert mark_message_processed("msg-a", "quickstart", settings) is False
    assert mark_message_processed("msg-b", "quickstart", settings) is False


def test_is_message_processed_false_before_mark_true_after(settings: Settings) -> None:
    assert is_message_processed("msg-1", "quickstart", settings) is False

    mark_message_processed("msg-1", "quickstart", settings)

    assert is_message_processed("msg-1", "quickstart", settings) is True
