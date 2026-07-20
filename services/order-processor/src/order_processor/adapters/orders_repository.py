"""Único escritor de `orders` — leitura + escrita com concorrência otimista (research.md #3)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import ClientError
from pedidos_shared import DynamoDbClient, Order


class ConflitoDeConcorrenciaError(Exception):
    """Esgotadas as tentativas de recarregar+reavaliar em conflito de `version` (research.md #3)."""


def _pk(order_id: str) -> str:
    return f"ORDER#{order_id}"


def _to_item(order: Order) -> dict[str, Any]:
    item = order.model_dump(mode="json")
    item["PK"] = _pk(order.order_id)
    item["SK"] = "METADATA"
    item["GSI1PK"] = f"CUSTOMER#{order.customer_id}"
    item["GSI1SK"] = f"{item['created_at']}#{order.order_id}"
    item["GSI2PK"] = f"STATUS#{order.status.value}"
    item["GSI2SK"] = item["GSI1SK"]
    return item


def _from_item(item: dict[str, Any]) -> Order:
    data = {
        k: v
        for k, v in item.items()
        if k not in ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK")
    }
    return Order.model_validate(data)


def get_by_id(dynamodb: DynamoDbClient, table_name: str, order_id: str) -> Order | None:
    item = dynamodb.get_item(table_name, {"PK": _pk(order_id), "SK": "METADATA"})
    if item is None:
        return None
    return _from_item(item)


def create(dynamodb: DynamoDbClient, table_name: str, order: Order) -> None:
    """Primeira escrita do pedido — falha (`ClientError`) se `order_id` já existir."""
    dynamodb.put_item(table_name, _to_item(order), ConditionExpression="attribute_not_exists(PK)")


def update_with_version(
    dynamodb: DynamoDbClient,
    table_name: str,
    order_id: str,
    apply_fn: Callable[[Order], Order],
    max_attempts: int = 3,
) -> Order:
    """Recarrega o pedido, aplica `apply_fn` (que já decidiu a transição via
    `domain/transicoes.py`), grava condicionado à `version` não ter mudado desde a leitura. Em
    conflito, recarrega e tenta de novo, até `max_attempts` vezes (research.md #3)."""
    for _ in range(max_attempts):
        current = get_by_id(dynamodb, table_name, order_id)
        if current is None:
            raise ValueError(f"pedido {order_id!r} não encontrado")

        updated = apply_fn(current).model_copy(
            update={"version": current.version + 1, "updated_at": datetime.now(UTC)}
        )

        try:
            dynamodb.put_item(
                table_name,
                _to_item(updated),
                ConditionExpression="version = :expected",
                ExpressionAttributeValues={":expected": current.version},
            )
            return updated
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    raise ConflitoDeConcorrenciaError(
        f"conflito de concorrência não resolvido após {max_attempts} tentativas em {order_id!r}"
    )


def record_rejection(dynamodb: DynamoDbClient, table_name: str, order_id: str, reason: str) -> None:
    """Grava `status_reason` sem mudar `status` — chamado quando um handler rejeita a transição
    (`TransicaoInvalidaError`), pra cumprir a constitution I.5 ("toda falha de negócio grava
    statusReason no registro do pedido")."""
    update_with_version(
        dynamodb,
        table_name,
        order_id,
        lambda order: order.model_copy(update={"status_reason": reason}),
    )
