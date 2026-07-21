from unittest.mock import MagicMock

import httpx
import pytest

from lambda_line_processor.adapters import api_gateway_client
from lambda_line_processor.adapters.api_gateway_client import chamar


def test_chamar_returns_response_unchanged_regardless_of_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    fake_response = MagicMock(status_code=404)
    client.request.return_value = fake_response

    response = chamar(client, "POST", "/pedidos", {"foo": "bar"})

    assert response is fake_response
    client.request.assert_called_once_with(
        "POST", "/pedidos", json={"foo": "bar"}, timeout=api_gateway_client.DEFAULT_TIMEOUT_SECONDS
    )


def test_chamar_retries_on_connect_error_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_gateway_client.time, "sleep", lambda _seconds: None)
    client = MagicMock()
    fake_response = MagicMock(status_code=202)
    client.request.side_effect = [httpx.ConnectError("boom"), fake_response]

    response = chamar(client, "POST", "/pedidos", {})

    assert response is fake_response
    assert client.request.call_count == 2


def test_chamar_propagates_after_exhausting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_gateway_client.time, "sleep", lambda _seconds: None)
    client = MagicMock()
    client.request.side_effect = httpx.TimeoutException("timeout")

    with pytest.raises(httpx.TimeoutException):
        chamar(client, "POST", "/pedidos", {})

    assert client.request.call_count == api_gateway_client.MAX_ATTEMPTS
