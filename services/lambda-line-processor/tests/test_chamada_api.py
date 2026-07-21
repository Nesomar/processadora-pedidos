import pytest

from lambda_line_processor.domain.chamada_api import ComandoInvalidoError, montar_chamada


def test_solicitar_calls_post_pedidos() -> None:
    body = {"operation": "SOLICITAR", "order_id": None, "parsed": {"customer_id": "CUST1"}}

    method, path, parsed = montar_chamada(body)

    assert method == "POST"
    assert path == "/pedidos"
    assert parsed == {"customer_id": "CUST1"}


def test_editar_calls_put_pedidos_order_id() -> None:
    body = {
        "operation": "EDITAR",
        "order_id": "11111111-1111-1111-1111-111111111111",
        "parsed": {"customer_id": "CUST1"},
    }

    method, path, parsed = montar_chamada(body)

    assert method == "PUT"
    assert path == "/pedidos/11111111-1111-1111-1111-111111111111"
    assert parsed == {"customer_id": "CUST1"}


def test_cancelar_calls_post_cancelamento() -> None:
    body = {
        "operation": "CANCELAR",
        "order_id": "22222222-2222-2222-2222-222222222222",
        "parsed": {"reason": "Cancelamento via arquivo batch"},
    }

    method, path, parsed = montar_chamada(body)

    assert method == "POST"
    assert path == "/pedidos/22222222-2222-2222-2222-222222222222/cancelamento"
    assert parsed == {"reason": "Cancelamento via arquivo batch"}


def test_editar_sem_order_id_levanta_comando_invalido() -> None:
    body = {"operation": "EDITAR", "order_id": None, "parsed": {}}

    with pytest.raises(ComandoInvalidoError):
        montar_chamada(body)


def test_cancelar_sem_order_id_levanta_comando_invalido() -> None:
    body = {"operation": "CANCELAR", "order_id": None, "parsed": {}}

    with pytest.raises(ComandoInvalidoError):
        montar_chamada(body)


def test_operation_desconhecida_levanta_comando_invalido() -> None:
    body = {"operation": "APAGAR", "order_id": None, "parsed": {}}

    with pytest.raises(ComandoInvalidoError):
        montar_chamada(body)
