"""Integração real: Ministack (SQS + DynamoDB) e um api-gateway real rodando.

A primeira entrega é 100% real (SQS + HTTP real ao api-gateway + DynamoDB real). A segunda
entrega reaproveita o `MessageId` nativo já recebido, simulando redelivery — a checagem de
idempotência em si roda contra o DynamoDB real (research.md #4, mesmo padrão de
007-file-consumer).

`POST /pedidos` responde `202 Accepted` de forma assíncrona (publica em `solicitar_pedido_queue`)
— o pedido só aparece em `GET /pedidos` depois que o `order-processor` (outro serviço) o
processar, daí o poll curto abaixo em vez de checar a resposta imediatamente após a primeira
entrega.
"""

import time
import uuid
from unittest.mock import MagicMock

import httpx
from pedidos_shared import SqsClient, is_message_processed

from lambda_line_processor.adapters import worker_loop
from lambda_line_processor.config import LambdaLineProcessorSettings
from lambda_line_processor.handlers import processar_linha


def _pedidos_do_cliente(base_url: str, customer_id: str) -> list[dict]:
    with httpx.Client(base_url=base_url) as client:
        response = client.get("/pedidos", params={"customerId": customer_id})
    response.raise_for_status()
    return response.json()["pedidos"]


def _aguardar_pedido_criado(base_url: str, customer_id: str, tentativas: int = 10) -> list[dict]:
    for _ in range(tentativas):
        pedidos = _pedidos_do_cliente(base_url, customer_id)
        if pedidos:
            return pedidos
        time.sleep(0.5)
    return []


def test_reprocessing_integration_same_message_id_creates_order_once(
    sqs_client: SqsClient,
    settings: LambdaLineProcessorSettings,
    api_gateway_available: None,
) -> None:
    customer_id = f"CUST{uuid.uuid4().hex[:8]}"
    body = {
        "source_file": "idempotencia.txt",
        "line_number": 1,
        "operation": "SOLICITAR",
        "raw_line": "...",
        "order_id": None,
        "parsed": {
            "customer_id": customer_id,
            "customer_name": "Cliente Idempotencia",
            "customer_document": "52998224725",
            "channel": "BATCH",
            "items": [{"product_id": 1, "quantity": 3}],
            "source_file": "idempotencia.txt",
            "source_line": 1,
        },
    }
    native_message_id = sqs_client.send_raw(settings.pedido_lines_queue_url, body)

    def handler(raw_body: dict, inner_settings) -> None:
        processar_linha.handle(raw_body, inner_settings)

    # primeira entrega real: recebe, chama o api-gateway real,
    # marca (DynamoDB real), confirma (SQS real)
    worker_loop.process_once(sqs_client, settings.pedido_lines_queue_url, handler, settings)

    pedidos = _aguardar_pedido_criado(settings.api_gateway_base_url, customer_id)
    assert len(pedidos) == 1

    assert is_message_processed(native_message_id, worker_loop.CONSUMER_NAME, settings) is True

    # segunda entrega simulada do MESMO MessageId nativo — dedup real contra o DynamoDB
    stub_sqs = MagicMock(spec=SqsClient)
    stub_sqs.receive_raw_with_receipt.return_value = [
        (body, "receipt-redelivery", native_message_id)
    ]
    handler_spy = MagicMock(wraps=handler)

    worker_loop.process_once(stub_sqs, settings.pedido_lines_queue_url, handler_spy, settings)

    handler_spy.assert_not_called()
    stub_sqs.delete.assert_called_once_with(settings.pedido_lines_queue_url, "receipt-redelivery")

    assert len(_pedidos_do_cliente(settings.api_gateway_base_url, customer_id)) == 1
