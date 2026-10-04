"""`GET /pedidos/{order_id}/nota-fiscal` — devolve o PDF da nota fiscal (010-acesso-pdf-pedido)."""

from fastapi import APIRouter, HTTPException, Response, status
from pedidos_shared import ObjectNotFoundError, get_logger

from api_gateway.adapters.orders_repository import get_by_id
from api_gateway.deps import DynamoDbClientDep, S3ClientDep, SettingsDep
from api_gateway.domain.nota_fiscal import (
    NotaFiscalAusenteError,
    NotaFiscalEmAndamentoError,
    NotaFiscalIndisponivelError,
    chave_da_nota_fiscal,
)

router = APIRouter()
logger = get_logger("api_gateway")

_PDF_AUSENTE = "PDF não encontrado no armazenamento"


@router.get("/pedidos/{order_id}/nota-fiscal")
def baixar_nota_fiscal(
    order_id: str,
    settings: SettingsDep,
    dynamodb: DynamoDbClientDep,
    s3: S3ClientDep,
) -> Response:
    order = get_by_id(dynamodb, settings.orders_table_name, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")

    log_extra = {"order_id": order_id, "correlation_id": order.correlation_id}
    try:
        chave = chave_da_nota_fiscal(order)
        pdf = s3.get_object(settings.pedidos_bucket_name, chave)
    except NotaFiscalEmAndamentoError:
        logger.info("nota fiscal ainda não disponível", extra=log_extra)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nota fiscal ainda não disponível, tente novamente",
        ) from None
    except NotaFiscalIndisponivelError:
        logger.info("pedido sem nota fiscal", extra=log_extra)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Nenhum PDF será gerado para este pedido",
        ) from None
    except (NotaFiscalAusenteError, ObjectNotFoundError):
        logger.error("PDF da nota fiscal ausente no armazenamento", extra=log_extra)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_PDF_AUSENTE) from None

    logger.info("nota fiscal entregue", extra=log_extra)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="nota-fiscal-{order_id}.pdf"'},
    )
