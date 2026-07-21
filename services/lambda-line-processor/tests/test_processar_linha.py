from unittest.mock import MagicMock

import pytest
from pedidos_shared import Settings

from lambda_line_processor.handlers import processar_linha

_SOLICITAR_BODY = {
    "source_file": "arquivo.txt",
    "line_number": 2,
    "operation": "SOLICITAR",
    "raw_line": "1SOLICITAR...",
    "order_id": None,
    "parsed": {"customer_id": "CUST00001", "customer_name": "Maria Silva"},
}


def test_handle_success_response_does_nothing_else(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_response = MagicMock(status_code=202)
    fake_chamar = MagicMock(return_value=fake_response)
    monkeypatch.setattr(processar_linha, "chamar", fake_chamar)

    processar_linha.handle(_SOLICITAR_BODY, settings)

    fake_chamar.assert_called_once()
    _, method, path, body = fake_chamar.call_args.args
    assert method == "POST"
    assert path == "/pedidos"
    assert body == _SOLICITAR_BODY["parsed"]


@pytest.mark.parametrize("status_code", [400, 404, 409])
def test_handle_permanent_rejection_status_codes_do_not_raise(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    fake_response = MagicMock(status_code=status_code, text="motivo qualquer")
    monkeypatch.setattr(processar_linha, "chamar", MagicMock(return_value=fake_response))

    processar_linha.handle(_SOLICITAR_BODY, settings)  # nao deve levantar excecao


def test_handle_comando_invalido_does_not_call_api_gateway(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_chamar = MagicMock()
    monkeypatch.setattr(processar_linha, "chamar", fake_chamar)
    body = {**_SOLICITAR_BODY, "operation": "EDITAR", "order_id": None}

    processar_linha.handle(body, settings)  # nao deve levantar excecao

    fake_chamar.assert_not_called()


def test_handle_unknown_operation_does_not_call_api_gateway(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_chamar = MagicMock()
    monkeypatch.setattr(processar_linha, "chamar", fake_chamar)
    body = {**_SOLICITAR_BODY, "operation": "APAGAR"}

    processar_linha.handle(body, settings)  # nao deve levantar excecao

    fake_chamar.assert_not_called()


def test_handle_5xx_response_raises_technical_failure(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_response = MagicMock(status_code=502, text="bad gateway")
    monkeypatch.setattr(processar_linha, "chamar", MagicMock(return_value=fake_response))

    with pytest.raises(RuntimeError, match="502"):
        processar_linha.handle(_SOLICITAR_BODY, settings)
