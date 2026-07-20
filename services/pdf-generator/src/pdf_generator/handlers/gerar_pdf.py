"""Handler de pdf_request_queue."""

import uuid
from datetime import UTC, datetime

from pedidos_shared import MessageEnvelope, S3Client, Settings, SqsClient

from pdf_generator.adapters.armazenamento import salvar_pdf
from pdf_generator.domain.chave_s3 import montar_chave_invoice
from pdf_generator.domain.mensagens import montar_resposta_falha, montar_resposta_sucesso
from pdf_generator.domain.renderizador import montar_dados_nota_fiscal, renderizar_nota_fiscal
from pdf_generator.domain.validacao import validar_solicitacao


def _response_envelope(envelope: MessageEnvelope, payload: dict) -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=envelope.correlation_id,
        order_id=envelope.order_id,
        occurred_at=datetime.now(UTC),
        payload=payload,
    )


def _publish_response(envelope: MessageEnvelope, settings: Settings, payload: dict) -> None:
    if settings.pdf_response_queue_url is None:
        raise ValueError("PDF_RESPONSE_QUEUE_URL nao configurada")
    SqsClient(settings).send(
        settings.pdf_response_queue_url,
        _response_envelope(envelope, payload),
    )


def handle(envelope: MessageEnvelope, settings: Settings) -> None:
    payload = envelope.payload

    erro = validar_solicitacao(payload)
    if erro is not None:
        _publish_response(envelope, settings, montar_resposta_falha(erro))
        return

    dados = montar_dados_nota_fiscal(payload)
    pdf_bytes = renderizar_nota_fiscal(dados)
    chave = montar_chave_invoice(envelope.order_id, datetime.now(UTC))

    salvar_pdf(S3Client(settings), settings.pedidos_bucket_name, chave, pdf_bytes)

    _publish_response(envelope, settings, montar_resposta_sucesso(chave))
