"""Composition root do bootstrap: cria/verifica todos os recursos do domínio no Ministack."""

import os
import time

from botocore.exceptions import ClientError, EndpointConnectionError

from resources.aws_clients import build_client
from resources.bucket import create_or_verify_bucket
from resources.orders_table import create_or_verify_orders_table
from resources.processed_messages_table import create_or_verify_processed_messages_table
from resources.queues import create_or_verify_queue

# As 9 filas do domínio (docs/01-dominio-e-contratos.md §4) — conjunto completo e fechado
# (contrato regra 2), não configurável por ambiente.
QUEUE_NAMES = [
    "solicitar_pedido_queue",
    "editar_pedido_queue",
    "cancelar_pedido_queue",
    "validar_pedido_queue",
    "validar_pedido_response_queue",
    "pdf_request_queue",
    "pdf_response_queue",
    "s3_notifications_queue",
    "pedido_lines_queue",
]


def wait_for_ministack(sqs_client, attempts: int = 10, delay_seconds: float = 1.0) -> None:
    """Retry curto de defesa extra (research.md #4).

    O `depends_on: condition: service_healthy` do compose já garante que o healthcheck do
    Ministack passou, mas cobre o caso raro em que a API ainda não aceita conexões de fato um
    instante depois.
    """
    last_error: Exception | None = None

    for _ in range(attempts):
        try:
            sqs_client.list_queues()
            return
        except (ClientError, EndpointConnectionError, ConnectionError, OSError) as error:
            last_error = error
            time.sleep(delay_seconds)

    raise ConnectionError(f"Ministack não respondeu após {attempts} tentativas") from last_error


def main() -> None:
    sqs = build_client("sqs")
    dynamodb = build_client("dynamodb")
    s3 = build_client("s3")

    wait_for_ministack(sqs)

    for name in QUEUE_NAMES:
        create_or_verify_queue(sqs, name, f"{name}_dlq")
    print(f"bootstrap: {len(QUEUE_NAMES)} filas (+{len(QUEUE_NAMES)} DLQs) prontas")

    create_or_verify_orders_table(dynamodb, os.environ.get("ORDERS_TABLE_NAME", "orders"))
    create_or_verify_processed_messages_table(
        dynamodb, os.environ.get("PROCESSED_MESSAGES_TABLE_NAME", "processed_messages")
    )
    print("bootstrap: tabelas orders e processed_messages prontas")

    notifications_queue_url = sqs.get_queue_url(QueueName="s3_notifications_queue")["QueueUrl"]
    notifications_queue_arn = sqs.get_queue_attributes(
        QueueUrl=notifications_queue_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    create_or_verify_bucket(
        s3, os.environ.get("PEDIDOS_BUCKET_NAME", "pedidos-bucket"), notifications_queue_arn
    )
    print("bootstrap: bucket pedidos-bucket + notificação de evento prontos")

    print("bootstrap: concluído")


if __name__ == "__main__":
    main()
