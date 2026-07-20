"""Cliente fino sobre SQS (constitution VIII — wrapper síncrono, DI de Settings)."""

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
