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


def is_message_processed(message_id: str, consumer: str, settings: Settings) -> bool:
    """Checagem só-leitura, sem marcar nada — usada por consumidores que precisam decidir se
    reprocessam ANTES de saber se o processamento vai ter sucesso (ex.: só chamar
    `mark_message_processed` depois que o handler concluir, pra falha técnica poder ser
    reentregue pelo redrive do SQS em vez de ficar marcada como processada sem nunca ter
    processado de verdade)."""
    table = DynamoDbClient(settings).table(settings.processed_messages_table_name)
    item = table.get_item(Key={"PK": f"MSG#{message_id}"}).get("Item")
    return item is not None and item.get("consumer") == consumer
