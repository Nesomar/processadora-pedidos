"""`GET /dlqs` — contagem de mensagens em cada DLQ do pipeline (011, US1)."""

from fastapi import APIRouter, HTTPException, status
from pedidos_shared import get_logger

from api_gateway.deps import SqsClientDep
from api_gateway.domain.dlq import FILAS, nome_dlq
from api_gateway.schemas import DlqResumo, ResumoDlqsResponse

router = APIRouter()
logger = get_logger("api_gateway")


@router.get("/dlqs", response_model=ResumoDlqsResponse)
def resumo_dlqs(sqs: SqsClientDep) -> ResumoDlqsResponse:
    try:
        dlqs = [
            DlqResumo(
                queue=fila,
                dlq=nome_dlq(fila),
                messages=sqs.message_count(sqs.queue_url(nome_dlq(fila))),
            )
            for fila in FILAS
        ]
    except Exception as error:
        logger.error("Falha ao consultar DLQs", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao consultar DLQs"
        ) from error

    logger.info(f"resumo de DLQs: {sum(d.messages for d in dlqs)} mensagens no total")
    return ResumoDlqsResponse(dlqs=dlqs)
