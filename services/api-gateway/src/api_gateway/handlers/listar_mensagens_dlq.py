"""`GET /dlqs/{fila}/mensagens` — espia mensagens de uma DLQ sem consumi-las (011, US2)."""

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pedidos_shared import get_logger

from api_gateway.deps import SqsClientDep
from api_gateway.domain.dlq import FILAS, identificar, mascarar, mascarar_texto, nome_dlq
from api_gateway.schemas import ListaMensagensDlqResponse, MensagemDlq

router = APIRouter()
logger = get_logger("api_gateway")

_TEXTO_MAX = 2000


def _sent_at(timestamp_ms: str | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=UTC).isoformat()


def _corpo(texto: str) -> object:
    try:
        return mascarar(json.loads(texto))
    except ValueError:
        return mascarar_texto(texto[:_TEXTO_MAX])


@router.get("/dlqs/{fila}/mensagens", response_model=ListaMensagensDlqResponse)
def listar_mensagens_dlq(
    fila: str,
    sqs: SqsClientDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> ListaMensagensDlqResponse:
    if fila not in FILAS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fila não encontrada")

    try:
        dlq_url = sqs.queue_url(nome_dlq(fila))
        encontradas = sqs.peek(dlq_url, limit)
        total = sqs.message_count(dlq_url)
    except Exception as error:
        logger.error("Falha ao listar mensagens da DLQ", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao consultar DLQ"
        ) from error

    mensagens = []
    for mensagem in encontradas[:limit]:
        corpo = _corpo(mensagem["Body"])
        mensagens.append(
            MensagemDlq(
                message_id=mensagem["MessageId"],
                sent_at=_sent_at(mensagem.get("SentTimestamp")),
                body=corpo,
                **identificar(corpo),
            )
        )

    logger.info(f"listadas {len(mensagens)} mensagens da {nome_dlq(fila)}")
    return ListaMensagensDlqResponse(
        queue=fila, messages=mensagens, has_more=total > len(mensagens)
    )
