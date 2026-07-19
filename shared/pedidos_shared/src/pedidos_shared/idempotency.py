"""Idempotência via tabela `processed_messages` (research.md #4)."""

import time

from botocore.exceptions import ClientError

from pedidos_shared.clients.dynamodb import DynamoDbClient
from pedidos_shared.settings import Settings

_TTL_SECONDS = 7 * 24 * 3600


def mark_message_processed(message_id: str, consumer: str, settings: Settings) -> bool:
    """Marca `message_id` como processado por `consumer`.

    Retorna `False` na primeira chamada (mensagem deve ser processada agora) e `True` se a
    mensagem já havia sido marcada antes (duplicata). Usa write condicional atômico
    (`ConditionExpression=attribute_not_exists(PK)`) para eliminar race condition entre checar e
    marcar.
    """
    table = DynamoDbClient(settings).table(settings.processed_messages_table_name)
    now = int(time.time())

    try:
        table.put_item(
            Item={
                "PK": f"MSG#{message_id}",
                "consumer": consumer,
                "processed_at": now,
                "ttl": now + _TTL_SECONDS,
            },
            ConditionExpression="attribute_not_exists(PK)",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return True
        raise

    return False
