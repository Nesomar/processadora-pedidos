import json
import socket
import time
import urllib.error
import urllib.request

import pytest

from lambda_line_processor.main import HEALTH_PORT, _start_health_server


def _port_open() -> bool:
    with socket.socket() as sock:
        return sock.connect_ex(("localhost", HEALTH_PORT)) == 0


@pytest.fixture(scope="module", autouse=True)
def _health_server() -> None:
    if not _port_open():
        _start_health_server()
        time.sleep(0.2)


def test_health_returns_ok() -> None:
    with urllib.request.urlopen(f"http://localhost:{HEALTH_PORT}/health", timeout=2) as response:
        assert response.status == 200
        body = json.loads(response.read())
    assert body == {"status": "ok"}


def test_unknown_path_returns_404() -> None:
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(f"http://localhost:{HEALTH_PORT}/other", timeout=2)
    assert error.value.code == 404
