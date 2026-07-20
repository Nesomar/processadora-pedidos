"""Cliente fino sobre SQS (constitution VIII — wrapper síncrono, DI de Settings)."""

import json

import boto3

from pedidos_shared.models import MessageEnvelope
from pedidos_shared.settings import Settings


class SqsClient:
    def __init__(self, settings: Settings) -> None:
        self._client = boto3.client(
            "sqs",
            endpoint_url=settings.aws_endpoint_url,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def send(self, queue_url: str, envelope: MessageEnvelope) -> str:
        response = self._client.send_message(
            QueueUrl=queue_url,
            MessageBody=envelope.model_dump_json(),
        )
        return response["MessageId"]

    def receive(self, queue_url: str, max_messages: int = 10) -> list[MessageEnvelope]:
        response = self._client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
        )
        return [
            MessageEnvelope.model_validate_json(message["Body"])
            for message in response.get("Messages", [])
        ]

    def delete(self, queue_url: str, receipt_handle: str) -> None:
        self._client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

    def receive_with_receipt(
        self, queue_url: str, max_messages: int = 10
    ) -> list[tuple[MessageEnvelope, str]]:
        """Como `receive`, mas devolve o `ReceiptHandle` de cada mensagem — necessário pra
        confirmar (`delete`) uma mensagem específica depois de processá-la."""
        response = self._client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
        )
        return [
            (MessageEnvelope.model_validate_json(message["Body"]), message["ReceiptHandle"])
            for message in response.get("Messages", [])
        ]

    def send_raw(self, queue_url: str, body: dict) -> str:
        """Como `send`, mas publica um corpo JSON cru — para filas que não usam `MessageEnvelope`
        (ex.: `pedido_lines_queue`, docs/01-dominio-e-contratos.md §5)."""
        response = self._client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
        return response["MessageId"]

    def receive_raw_with_receipt(
        self, queue_url: str, max_messages: int = 10
    ) -> list[tuple[dict, str, str]]:
        """Como `receive_with_receipt`, mas sem validar o corpo contra `MessageEnvelope` — para
        filas com corpo nativo de terceiros (ex.: `s3_notifications_queue`). Devolve
        `(corpo_json, receipt_handle, MessageId nativo do SQS)` por mensagem."""
        response = self._client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
        )
        return [
            (json.loads(message["Body"]), message["ReceiptHandle"], message["MessageId"])
            for message in response.get("Messages", [])
        ]
