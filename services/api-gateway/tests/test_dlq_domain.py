"""Teste das funções puras de DLQ (011-observabilidade-dlq)."""

from api_gateway.domain.dlq import FILAS, identificar, mascarar, mascarar_texto, nome_dlq

NONE_TUDO = {"order_id": None, "correlation_id": None, "source_file": None, "source_line": None}


def test_filas_sao_as_nove_do_dominio() -> None:
    assert len(FILAS) == 9
    assert len(set(FILAS)) == 9
    assert "validar_pedido_queue" in FILAS


def test_nome_dlq() -> None:
    assert nome_dlq("validar_pedido_queue") == "validar_pedido_queue_dlq"


def test_identificar_envelope() -> None:
    body = {"message_id": "m", "order_id": "o-1", "correlation_id": "c-1", "payload": {}}

    assert identificar(body) == {**NONE_TUDO, "order_id": "o-1", "correlation_id": "c-1"}


def test_identificar_evento_s3() -> None:
    body = {"Records": [{"s3": {"object": {"key": "uploads/a.txt"}}}]}

    assert identificar(body) == {**NONE_TUDO, "source_file": "uploads/a.txt"}


def test_identificar_linha_de_lote() -> None:
    body = {"source_file": "pedidos.txt", "line_number": 42, "operation": "SOLICITAR"}

    assert identificar(body) == {**NONE_TUDO, "source_file": "pedidos.txt", "source_line": 42}


def test_identificar_desconhecido_nunca_levanta() -> None:
    assert identificar({"foo": 1}) == NONE_TUDO
    assert identificar({"Records": []}) == NONE_TUDO
    assert identificar({"Records": [{"s3": None}]}) == NONE_TUDO
    assert identificar("texto") == NONE_TUDO
    assert identificar(None) == NONE_TUDO


def test_identificar_tipos_errados_viram_none() -> None:
    assert identificar({"order_id": 1, "correlation_id": None}) == NONE_TUDO
    assert identificar({"source_file": "a.txt", "line_number": "x"}) == {
        **NONE_TUDO,
        "source_file": "a.txt",
    }
    assert identificar({"source_file": "a.txt", "line_number": True})["source_line"] is None
    assert identificar({"Records": [{"s3": {"object": {"key": 5}}}]}) == NONE_TUDO


def test_mascarar_texto_cobre_cpf_e_cnpj() -> None:
    texto = '{"customer_document": "12345678901", "outro": "11222333000181", "n": "123"'

    mascarado = mascarar_texto(texto)

    assert "12345678901" not in mascarado
    assert "11222333000181" not in mascarado
    assert "*******8901" in mascarado
    assert '"n": "123"' in mascarado


def test_mascarar_em_qualquer_nivel_sem_alterar_original() -> None:
    original = {
        "payload": {
            "customer_document": "12345678901",
            "items": [{"customer_document": "98765432100"}],
        },
        "parsed": {"customer_document": "12345678901"},
        "outro": "12345678901",
    }

    resultado = mascarar(original)

    assert resultado["payload"]["customer_document"] == "*******8901"
    assert resultado["payload"]["items"][0]["customer_document"] == "*******2100"
    assert resultado["parsed"]["customer_document"] == "*******8901"
    assert resultado["outro"] == "12345678901"
    assert original["parsed"]["customer_document"] == "12345678901"
