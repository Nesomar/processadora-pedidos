"""Teste dos endpoints de DLQ (011-observabilidade-dlq)."""

import json
import uuid
from unittest.mock import MagicMock, call

import pytest
from fastapi.testclient import TestClient
from pedidos_shared import SqsClient

from api_gateway.domain.dlq import FILAS

FILA = "validar_pedido_queue"
DLQ_URL = f"http://q/{FILA}_dlq"
ORIGEM_URL = f"http://q/{FILA}"
CORPO = json.dumps(
    {
        "message_id": "m-1",
        "order_id": "o-1",
        "correlation_id": "c-1",
        "payload": {"customer_document": "12345678901"},
    }
)


@pytest.fixture(autouse=True)
def _urls(fake_sqs_client: MagicMock) -> None:
    fake_sqs_client.queue_url.side_effect = lambda nome: f"http://q/{nome}"


def _mensagem(message_id: str = "sqs-1", body: str = CORPO, receipt: str | None = None) -> dict:
    return {"MessageId": message_id, "Body": body, "ReceiptHandle": receipt or f"r-{message_id}"}


# --- GET /dlqs (US1) ---


def test_resumo_devolve_as_nove_dlqs_com_contagem(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    fake_sqs_client.message_count.side_effect = lambda url: 1 if url == DLQ_URL else 0

    response = client.get("/dlqs")

    assert response.status_code == 200
    dlqs = response.json()["dlqs"]
    assert [d["queue"] for d in dlqs] == list(FILAS)
    assert all(d["dlq"] == f"{d['queue']}_dlq" for d in dlqs)
    assert {d["queue"]: d["messages"] for d in dlqs}[FILA] == 1
    assert sum(d["messages"] for d in dlqs) == 1


def test_resumo_502_quando_sqs_falha(client: TestClient, fake_sqs_client: MagicMock) -> None:
    fake_sqs_client.message_count.side_effect = RuntimeError("sqs down")

    assert client.get("/dlqs").status_code == 502


# --- GET /dlqs/{fila}/mensagens (US2) ---


def test_listar_identifica_pedido_e_mascara_documento(
    client: TestClient, fake_sqs_client: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_sqs_client.peek.return_value = [
        {"MessageId": "sqs-1", "Body": CORPO, "SentTimestamp": "1790000000000"}
    ]
    fake_sqs_client.message_count.return_value = 1

    response = client.get(f"/dlqs/{FILA}/mensagens")

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["has_more"] is False
    mensagem = corpo["messages"][0]
    assert mensagem["message_id"] == "sqs-1"
    assert mensagem["order_id"] == "o-1"
    assert mensagem["correlation_id"] == "c-1"
    assert mensagem["sent_at"].startswith("2026-")
    assert mensagem["body"]["payload"]["customer_document"] == "*******8901"
    assert "12345678901" not in response.text
    assert "12345678901" not in capsys.readouterr().out
    fake_sqs_client.delete.assert_not_called()


def test_listar_respeita_limit_e_has_more(client: TestClient, fake_sqs_client: MagicMock) -> None:
    fake_sqs_client.peek.return_value = [{"MessageId": f"sqs-{i}", "Body": CORPO} for i in range(3)]
    fake_sqs_client.message_count.return_value = 7

    corpo = client.get(f"/dlqs/{FILA}/mensagens", params={"limit": 2}).json()

    assert len(corpo["messages"]) == 2
    assert corpo["has_more"] is True


def test_listar_corpo_nao_json_vira_texto_truncado(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    fake_sqs_client.peek.return_value = [{"MessageId": "sqs-1", "Body": "x" * 5000}]
    fake_sqs_client.message_count.return_value = 1

    mensagem = client.get(f"/dlqs/{FILA}/mensagens").json()["messages"][0]

    assert mensagem["body"] == "x" * 2000
    assert mensagem["order_id"] is None


def test_listar_corpo_nao_json_mascara_documento(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    truncado = '{"payload": {"customer_document": "12345678901", "customer_na'
    fake_sqs_client.peek.return_value = [{"MessageId": "sqs-1", "Body": truncado}]
    fake_sqs_client.message_count.return_value = 1

    response = client.get(f"/dlqs/{FILA}/mensagens")

    assert response.status_code == 200
    assert "12345678901" not in response.text
    assert "*******8901" in response.text


def test_listar_poison_com_tipos_errados_nao_derruba_a_listagem(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    ruim = json.dumps({"order_id": 123, "correlation_id": ["x"]})
    linha = json.dumps({"source_file": "a.txt", "line_number": "quatro"})
    fake_sqs_client.peek.return_value = [
        {"MessageId": "sqs-1", "Body": ruim},
        {"MessageId": "sqs-2", "Body": linha},
    ]
    fake_sqs_client.message_count.return_value = 2

    response = client.get(f"/dlqs/{FILA}/mensagens")

    assert response.status_code == 200
    mensagens = response.json()["messages"]
    assert mensagens[0]["order_id"] is None
    assert mensagens[1]["source_file"] == "a.txt"
    assert mensagens[1]["source_line"] is None


def test_listar_fila_batch_identifica_arquivo_e_linha(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    body = json.dumps({"source_file": "p.txt", "line_number": 4, "operation": "SOLICITAR"})
    fake_sqs_client.peek.return_value = [{"MessageId": "sqs-1", "Body": body}]
    fake_sqs_client.message_count.return_value = 1

    mensagem = client.get("/dlqs/pedido_lines_queue/mensagens").json()["messages"][0]

    assert mensagem["source_file"] == "p.txt"
    assert mensagem["source_line"] == 4
    assert mensagem["order_id"] is None


def test_listar_dlq_vazia(client: TestClient, fake_sqs_client: MagicMock) -> None:
    fake_sqs_client.peek.return_value = []
    fake_sqs_client.message_count.return_value = 0

    corpo = client.get(f"/dlqs/{FILA}/mensagens").json()

    assert corpo == {"queue": FILA, "messages": [], "has_more": False}


def test_listar_fila_desconhecida_404(client: TestClient) -> None:
    response = client.get("/dlqs/fila_inexistente/mensagens")

    assert response.status_code == 404
    assert response.json() == {"detail": "Fila não encontrada"}


@pytest.mark.parametrize("limit", [0, 51])
def test_listar_limit_invalido(client: TestClient, limit: int) -> None:
    assert client.get(f"/dlqs/{FILA}/mensagens", params={"limit": limit}).status_code == 400


def test_listar_502_quando_sqs_falha(client: TestClient, fake_sqs_client: MagicMock) -> None:
    fake_sqs_client.peek.side_effect = RuntimeError("sqs down")

    assert client.get(f"/dlqs/{FILA}/mensagens").status_code == 502


# --- POST /dlqs/{fila}/reprocessamento (US3) ---


def test_reprocessar_dlq_inteira_envia_antes_de_deletar(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    fake_sqs_client.receive_raw_messages.side_effect = [
        [_mensagem("a", "corpo-a"), _mensagem("b", "corpo-b")],
        [],
        [],
        [],
    ]
    ordem = MagicMock()
    ordem.attach_mock(fake_sqs_client.send_body, "send")
    ordem.attach_mock(fake_sqs_client.delete, "delete")

    response = client.post(f"/dlqs/{FILA}/reprocessamento")

    assert response.status_code == 200
    assert response.json() == {"queue": FILA, "reprocessed": 2, "has_more": False}
    assert ordem.mock_calls == [
        call.send(ORIGEM_URL, "corpo-a"),
        call.delete(DLQ_URL, "r-a"),
        call.send(ORIGEM_URL, "corpo-b"),
        call.delete(DLQ_URL, "r-b"),
    ]


def test_reprocessar_por_message_id_move_so_ela(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    fake_sqs_client.receive_raw_messages.return_value = [
        _mensagem("a"),
        _mensagem("b"),
        _mensagem("c"),
    ]

    response = client.post(f"/dlqs/{FILA}/reprocessamento", json={"message_id": "b"})

    assert response.json() == {"queue": FILA, "reprocessed": 1, "has_more": False}
    fake_sqs_client.send_body.assert_called_once_with(ORIGEM_URL, CORPO)
    fake_sqs_client.delete.assert_called_once_with(DLQ_URL, "r-b")
    liberadas = {c.args[1] for c in fake_sqs_client.release.call_args_list}
    assert liberadas == {"r-a", "r-c"}


def test_reprocessar_message_id_inexistente_404_sem_mover(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    fake_sqs_client.receive_raw_messages.side_effect = [[_mensagem("a")], [], [], []]

    response = client.post(f"/dlqs/{FILA}/reprocessamento", json={"message_id": "zzz"})

    assert response.status_code == 404
    fake_sqs_client.send_body.assert_not_called()
    fake_sqs_client.delete.assert_not_called()
    fake_sqs_client.release.assert_called_once_with(DLQ_URL, "r-a")


def test_reprocessar_dlq_vazia_devolve_zero(client: TestClient, fake_sqs_client: MagicMock) -> None:
    fake_sqs_client.receive_raw_messages.return_value = []

    response = client.post(f"/dlqs/{FILA}/reprocessamento")

    assert response.status_code == 200
    assert response.json() == {"queue": FILA, "reprocessed": 0, "has_more": False}
    fake_sqs_client.send_body.assert_not_called()


def test_reprocessar_varredura_limitada_sinaliza_has_more(
    client: TestClient, fake_sqs_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("api_gateway.handlers.reprocessar_dlq._RODADAS", 2)
    contador = iter(range(100))
    fake_sqs_client.receive_raw_messages.side_effect = lambda url: [_mensagem(f"m{next(contador)}")]

    response = client.post(f"/dlqs/{FILA}/reprocessamento")

    assert response.json() == {"queue": FILA, "reprocessed": 2, "has_more": True}


def test_reprocessar_message_id_alem_da_varredura_explica_o_404(
    client: TestClient, fake_sqs_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("api_gateway.handlers.reprocessar_dlq._RODADAS", 2)
    fake_sqs_client.receive_raw_messages.return_value = [_mensagem("a")]

    response = client.post(f"/dlqs/{FILA}/reprocessamento", json={"message_id": "zzz"})

    assert response.status_code == 404
    assert "varredura limitada" in response.json()["detail"]


def test_reprocessar_fila_desconhecida_404(client: TestClient) -> None:
    assert client.post("/dlqs/fila_inexistente/reprocessamento").status_code == 404


def test_reprocessar_falha_no_send_nao_deleta_e_devolve_502(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    fake_sqs_client.receive_raw_messages.return_value = [_mensagem("a"), _mensagem("b")]
    fake_sqs_client.send_body.side_effect = RuntimeError("sqs down")

    response = client.post(f"/dlqs/{FILA}/reprocessamento")

    assert response.status_code == 502
    fake_sqs_client.delete.assert_not_called()
    assert {c.args[1] for c in fake_sqs_client.release.call_args_list} == {"r-a", "r-b"}


def test_reprocessar_falha_no_delete_devolve_502_sem_perder(
    client: TestClient, fake_sqs_client: MagicMock
) -> None:
    fake_sqs_client.receive_raw_messages.return_value = [_mensagem("a")]
    fake_sqs_client.delete.side_effect = RuntimeError("sqs down")

    response = client.post(f"/dlqs/{FILA}/reprocessamento")

    assert response.status_code == 502
    fake_sqs_client.send_body.assert_called_once()
    fake_sqs_client.release.assert_called_once_with(DLQ_URL, "r-a")


# --- integração contra o Ministack ---


@pytest.fixture
def sqs_real():
    from api_gateway.config import get_settings

    return SqsClient(get_settings())


@pytest.fixture
def tags_criadas(sqs_real: SqsClient):
    """Os testes de integração reenviam mensagens à fila de origem real; ao final, remove as
    que criaram para não deixar lixo que quebre outros testes que leem essa fila."""
    tags: list[str] = []
    yield tags
    origem_url = sqs_real.queue_url(FILA)
    for _ in range(30):
        resposta = sqs_real._client.receive_message(
            QueueUrl=origem_url, MaxNumberOfMessages=10, VisibilityTimeout=1
        )
        for mensagem in resposta.get("Messages", []):
            if json.loads(mensagem["Body"]).get("message_id") in tags:
                sqs_real.delete(origem_url, mensagem["ReceiptHandle"])


def _enviar_para_dlq(sqs: SqsClient, tag: str) -> tuple[str, str]:
    body = json.dumps(
        {
            "message_id": tag,
            "occurred_at": "2026-10-03T21:00:00Z",
            "order_id": tag,
            "correlation_id": f"c-{tag}",
            "payload": {"customer_document": "12345678901"},
        }
    )
    return sqs.send_body(sqs.queue_url(f"{FILA}_dlq"), body), tag


def _ids_na_dlq(integration_client: TestClient) -> dict[str, dict]:
    corpo = integration_client.get(f"/dlqs/{FILA}/mensagens", params={"limit": 50}).json()
    return {m["message_id"]: m for m in corpo["messages"]}


def test_dlqs_integration_resumo_e_listagem_nao_consome(
    integration_client: TestClient, sqs_real: SqsClient, tags_criadas: list[str]
) -> None:
    message_id, tag = _enviar_para_dlq(sqs_real, uuid.uuid4().hex)
    tags_criadas.append(tag)

    resumo = {d["queue"]: d["messages"] for d in integration_client.get("/dlqs").json()["dlqs"]}
    primeira = _ids_na_dlq(integration_client)
    segunda = _ids_na_dlq(integration_client)

    assert resumo[FILA] >= 1
    assert primeira[message_id]["order_id"] == tag
    assert primeira[message_id]["body"]["payload"]["customer_document"] == "*******8901"
    assert message_id in segunda

    # limpa o que o teste criou (também valida o reprocessamento por id)
    assert (
        integration_client.post(
            f"/dlqs/{FILA}/reprocessamento", json={"message_id": message_id}
        ).status_code
        == 200
    )


def test_dlqs_integration_reprocessa_por_message_id(
    integration_client: TestClient, sqs_real: SqsClient, tags_criadas: list[str]
) -> None:
    id_a, tag_a = _enviar_para_dlq(sqs_real, uuid.uuid4().hex)
    id_b, tag_b = _enviar_para_dlq(sqs_real, uuid.uuid4().hex)
    tags_criadas.extend([tag_a, tag_b])

    primeira = integration_client.post(f"/dlqs/{FILA}/reprocessamento", json={"message_id": id_a})

    assert primeira.status_code == 200
    assert primeira.json()["reprocessed"] == 1
    restantes = _ids_na_dlq(integration_client)
    assert id_a not in restantes
    assert id_b in restantes

    assert (
        integration_client.post(f"/dlqs/{FILA}/reprocessamento", json={"message_id": id_b}).json()[
            "reprocessed"
        ]
        == 1
    )
    assert (
        integration_client.post(
            f"/dlqs/{FILA}/reprocessamento", json={"message_id": id_a}
        ).status_code
        == 404
    )
