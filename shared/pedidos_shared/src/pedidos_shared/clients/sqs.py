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

    def queue_url(self, name: str) -> str:
        """Resolve a URL pelo nome; `QueueDoesNotExist` propaga."""
        return self._client.get_queue_url(QueueName=name)["QueueUrl"]

    def message_count(self, queue_url: str) -> int:
        """Visíveis + em voo + atrasadas — mensagem recebida por outro consumidor ainda conta."""
        attrs = self._client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed",
            ],
        )["Attributes"]
        return sum(int(value) for value in attrs.values())

    def peek(self, queue_url: str, limit: int = 10, rounds: int = 5) -> list[dict]:
        """Espia até `limit` mensagens sem consumi-las: `MessageId`, `Body`, `SentTimestamp` (ms
        desde a epoch, string). Mantém as já vistas escondidas durante a varredura (a fila entrega
        em ordem de chegada; sem isso toda rodada releria as mesmas) e libera todas no fim com
        `change_message_visibility(0)` — `VisibilityTimeout=0` direto no receive é tratado como o
        padrão (60 s) pelo Ministack e esconderia a mensagem."""
        vistas: dict[str, dict] = {}
        recibos: list[str] = []
        try:
            for _ in range(rounds):
                if len(vistas) >= limit:
                    break
                response = self._client.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=min(10, limit - len(vistas)),
                    VisibilityTimeout=30,
                    AttributeNames=["SentTimestamp"],
                )
                mensagens = response.get("Messages", [])
                if not mensagens:
                    break
                for message in mensagens:
                    recibos.append(message["ReceiptHandle"])
                    vistas.setdefault(
                        message["MessageId"],
                        {
                            "MessageId": message["MessageId"],
                            "Body": message["Body"],
                            "SentTimestamp": message.get("Attributes", {}).get("SentTimestamp"),
                        },
                    )
        finally:
            for recibo in recibos:
                self.release(queue_url, recibo)
        return list(vistas.values())

    def receive_raw_messages(self, queue_url: str, max_messages: int = 10) -> list[dict]:
        """Recebe com a visibilidade padrão da fila: `MessageId`, `Body`, `ReceiptHandle`.
        Long polling de 1 s: na AWS real, short polling pode vir vazio com mensagens na fila."""
        response = self._client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=1,
        )
        return [
            {
                "MessageId": message["MessageId"],
                "Body": message["Body"],
                "ReceiptHandle": message["ReceiptHandle"],
            }
            for message in response.get("Messages", [])
        ]

    def send_body(self, queue_url: str, body: str) -> str:
        """Reenvia o corpo exatamente como está (reprocessamento de DLQ)."""
        return self._client.send_message(QueueUrl=queue_url, MessageBody=body)["MessageId"]

    def release(self, queue_url: str, receipt_handle: str) -> None:
        """Devolve uma mensagem recebida à fila já visível (`VisibilityTimeout=0`)."""
        self._client.change_message_visibility(
            QueueUrl=queue_url, ReceiptHandle=receipt_handle, VisibilityTimeout=0
        )
