"""`POST /dlqs/{fila}/reprocessamento` — devolve mensagens da DLQ à fila de origem (011, US3)."""

from fastapi import APIRouter, HTTPException, status
from pedidos_shared import SqsClient, get_logger

from api_gateway.deps import SqsClientDep
from api_gateway.domain.dlq import FILAS, nome_dlq
from api_gateway.schemas import ReprocessamentoRequest, ReprocessamentoResponse

router = APIRouter()
logger = get_logger("api_gateway")

_RODADAS = 100  # até ~1000 mensagens por chamada; além disso a resposta traz has_more
_VAZIAS_PARA_PARAR = 3


def _reprocessar(
    sqs: SqsClient, dlq_url: str, origem_url: str, message_id: str | None
) -> tuple[int, bool]:
    """Devolve `(movidas, completo)`; `completo=False` quando o limite de rodadas encerrou a
    varredura antes de a DLQ esvaziar."""
    movidas = 0
    vazias = 0
    # Tudo que for recebido e não apagado volta à fila só no fim (`finally`): a fila entrega em
    # ordem de chegada, então soltar a cada rodada faria a varredura reler sempre as mesmas.
    recebidas: list[str] = []
    apagadas: set[str] = set()
    try:
        for _ in range(_RODADAS):
            mensagens = sqs.receive_raw_messages(dlq_url)
            vazias = 0 if mensagens else vazias + 1
            if vazias >= _VAZIAS_PARA_PARAR:
                return movidas, True
            recebidas.extend(m["ReceiptHandle"] for m in mensagens)
            for mensagem in mensagens:
                if message_id is not None and mensagem["MessageId"] != message_id:
                    continue
                # Enviar ANTES de deletar: falha no meio duplica, nunca perde (FR-007). O consumidor
                # é idempotente por `message_id`; nas filas fora do envelope (`pedido_lines`,
                # `s3_notifications`) a chave é o MessageId nativo, que o reenvio troca.
                # ponytail: nessas duas, falha de delete após o send pode reexecutar linha/arquivo.
                sqs.send_body(origem_url, mensagem["Body"])
                sqs.delete(dlq_url, mensagem["ReceiptHandle"])
                apagadas.add(mensagem["ReceiptHandle"])
                movidas += 1
                if message_id is not None:
                    return movidas, True
    finally:
        for recibo in recebidas:
            if recibo not in apagadas:
                sqs.release(dlq_url, recibo)
    return movidas, False


@router.post("/dlqs/{fila}/reprocessamento", response_model=ReprocessamentoResponse)
def reprocessar_dlq(
    fila: str,
    sqs: SqsClientDep,
    payload: ReprocessamentoRequest | None = None,
) -> ReprocessamentoResponse:
    if fila not in FILAS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fila não encontrada")

    message_id = payload.message_id if payload else None
    try:
        dlq_url = sqs.queue_url(nome_dlq(fila))
        origem_url = sqs.queue_url(fila)
        movidas, completo = _reprocessar(sqs, dlq_url, origem_url, message_id)
    except Exception as error:
        logger.error(f"Falha ao reprocessar a {nome_dlq(fila)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Falha ao reprocessar DLQ"
        ) from error

    if message_id is not None and movidas == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mensagem não encontrada na DLQ"
            if completo
            else "Mensagem não encontrada nas primeiras mensagens da DLQ (varredura limitada)",
        )

    logger.info(f"reprocessadas {movidas} mensagens da {nome_dlq(fila)} para {fila}")
    return ReprocessamentoResponse(queue=fila, reprocessed=movidas, has_more=not completo)
