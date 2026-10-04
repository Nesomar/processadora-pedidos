"""Teste de GET /pedidos/{order_id}/nota-fiscal (010-acesso-pdf-pedido)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pedidos_shared import DynamoDbClient, ObjectNotFoundError, S3Client

ORDER_ID = "11111111-1111-1111-1111-111111111111"
CHAVE = "invoices/2026/10/03/11111111-1111-1111-1111-111111111111.pdf"
PDF = b"%PDF-1.4 conteudo"


def _order_dict(
    status: str = "COMPLETED", chave: str | None = CHAVE, order_id: str = ORDER_ID
) -> dict:
    now = datetime.now(UTC).isoformat()
    item = {
        "order_id": order_id,
        "customer_id": "CUST00001",
        "customer_name": "Maria Silva",
        "customer_document": "12345678901",
        "channel": "HTTP",
        "items": [{"product_id": 1, "quantity": 2}],
        "status": status,
        "status_reason": "motivo",
        "correlation_id": "22222222-2222-2222-2222-222222222222",
        "created_at": now,
        "updated_at": now,
        "version": 0,
    }
    if chave:
        item["invoice_s3_key"] = chave
    return item


def test_nota_fiscal_devolve_pdf(
    client: TestClient,
    fake_dynamodb_client: MagicMock,
    fake_s3_client: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict()
    fake_s3_client.get_object.return_value = PDF

    response = client.get(f"/pedidos/{ORDER_ID}/nota-fiscal")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        f'inline; filename="nota-fiscal-{ORDER_ID}.pdf"'
    )
    assert response.content == PDF
    fake_s3_client.get_object.assert_called_once_with("pedidos-bucket", CHAVE)
    assert "12345678901" not in capsys.readouterr().out


def test_nota_fiscal_pedido_inexistente_404(
    client: TestClient, fake_dynamodb_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = None

    response = client.get("/pedidos/nao-existe/nota-fiscal")

    assert response.status_code == 404
    assert response.json() == {"detail": "Pedido não encontrado"}


@pytest.mark.parametrize(
    "status", ["RECEIVED", "PROCESSING", "VALIDATING", "VALIDATED", "INVOICING"]
)
def test_nota_fiscal_em_andamento_409(
    client: TestClient,
    fake_dynamodb_client: MagicMock,
    fake_s3_client: MagicMock,
    status: str,
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict(status)

    response = client.get(f"/pedidos/{ORDER_ID}/nota-fiscal")

    assert response.status_code == 409
    fake_s3_client.get_object.assert_not_called()


@pytest.mark.parametrize("status", ["REJECTED", "FAILED", "CANCELLED"])
def test_nota_fiscal_sem_pdf_410(
    client: TestClient, fake_dynamodb_client: MagicMock, status: str
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict(status, chave=None)

    response = client.get(f"/pedidos/{ORDER_ID}/nota-fiscal")

    assert response.status_code == 410
    assert response.json() == {"detail": "Nenhum PDF será gerado para este pedido"}


def test_nota_fiscal_completed_sem_chave_404(
    client: TestClient, fake_dynamodb_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict(chave=None)

    response = client.get(f"/pedidos/{ORDER_ID}/nota-fiscal")

    assert response.status_code == 404
    assert response.json() == {"detail": "PDF não encontrado no armazenamento"}


def test_nota_fiscal_objeto_ausente_404(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_s3_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict()
    fake_s3_client.get_object.side_effect = ObjectNotFoundError(CHAVE)

    response = client.get(f"/pedidos/{ORDER_ID}/nota-fiscal")

    assert response.status_code == 404
    assert response.json() == {"detail": "PDF não encontrado no armazenamento"}


def test_nota_fiscal_erro_tecnico_do_s3_vira_500(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_s3_client: MagicMock
) -> None:
    fake_dynamodb_client.get_item.return_value = _order_dict()
    fake_s3_client.get_object.side_effect = RuntimeError("boto: bucket pedidos-bucket down")
    tolerante = TestClient(client.app, raise_server_exceptions=False)

    response = tolerante.get(f"/pedidos/{ORDER_ID}/nota-fiscal")

    assert response.status_code == 500
    assert "pedidos-bucket" not in response.text


def test_nota_fiscal_respostas_nao_vazam_armazenamento(
    client: TestClient, fake_dynamodb_client: MagicMock, fake_s3_client: MagicMock
) -> None:
    fake_s3_client.get_object.return_value = PDF
    cenarios = [
        _order_dict(),
        _order_dict("PROCESSING"),
        _order_dict("REJECTED", chave=None),
        _order_dict(chave=None),
    ]
    for cenario in cenarios:
        fake_dynamodb_client.get_item.return_value = cenario
        response = client.get(f"/pedidos/{ORDER_ID}/nota-fiscal")
        texto = str(dict(response.headers))
        if response.status_code != 200:
            texto += response.text
        for proibido in ("invoices/", "pedidos-bucket", "localhost:4566"):
            assert proibido not in texto


def test_nota_fiscal_integration_devolve_mesmos_bytes(integration_client: TestClient) -> None:
    from api_gateway.config import get_settings

    settings = get_settings()
    order_id = str(uuid.uuid4())
    chave = f"invoices/teste/{order_id}.pdf"
    S3Client(settings).put_object(
        settings.pedidos_bucket_name, chave, PDF, content_type="application/pdf"
    )
    DynamoDbClient(settings).put_item(
        settings.orders_table_name,
        {
            **_order_dict(chave=chave, order_id=order_id),
            "PK": f"ORDER#{order_id}",
            "SK": "METADATA",
        },
    )

    response = integration_client.get(f"/pedidos/{order_id}/nota-fiscal")

    assert response.status_code == 200
    assert response.content == PDF
