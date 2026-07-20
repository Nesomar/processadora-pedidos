"""Teste de GET /health (constitution IV — thread HTTP simples na porta 8080)."""

import json
import time
import urllib.error
import urllib.request

import pytest

from order_processor.main import HEALTH_PORT, _start_health_server


@pytest.fixture(scope="module", autouse=True)
def _health_server() -> None:
    _start_health_server()
    time.sleep(0.2)


def test_health_returns_ok() -> None:
    with urllib.request.urlopen(f"http://localhost:{HEALTH_PORT}/health", timeout=2) as response:
        assert response.status == 200
        body = json.loads(response.read())
    assert body == {"status": "ok"}


def test_unknown_path_returns_404() -> None:
    try:
        urllib.request.urlopen(f"http://localhost:{HEALTH_PORT}/other", timeout=2)
        raised = False
    except urllib.error.HTTPError as error:
        raised = True
        assert error.code == 404
    assert raised
