"""Handler de validar_pedido_queue."""

import uuid
from datetime import UTC, datetime

import httpx
from pedidos_shared import MessageEnvelope, Settings, SqsClient, mask_document

from order_validator.adapters.catalogo_produtos import (
    DEFAULT_BASE_URL,
    CatalogoCache,
    ProdutoNaoEncontradoError,
    buscar_produto,
)
from order_validator.domain.calculo import calcular_item, calcular_totais
from order_validator.domain.documento import validar_documento
from order_validator.domain.estoque import validar_estoque
from order_validator.domain.limite_total import validar_limite_total
from order_validator.domain.mensagens import montar_resposta_aprovada, montar_resposta_reprovada
from order_validator.domain.modelos import ErroValidacao, ItemEnriquecido, ItemValidacao, Produto
from order_validator.domain.quantidade_minima import validar_quantidade_minima

CATALOG_CACHE = CatalogoCache()


def _base_url(settings: Settings) -> str:
    return getattr(settings, "catalog_products_base_url", DEFAULT_BASE_URL)


def _response_envelope(envelope: MessageEnvelope, payload: dict) -> MessageEnvelope:
    return MessageEnvelope(
        message_id=str(uuid.uuid4()),
        correlation_id=envelope.correlation_id,
        order_id=envelope.order_id,
        occurred_at=datetime.now(UTC),
        payload=payload,
    )


def _publish_response(envelope: MessageEnvelope, settings: Settings, payload: dict) -> None:
    if settings.validar_pedido_response_queue_url is None:
        raise ValueError("VALIDAR_PEDIDO_RESPONSE_QUEUE_URL nao configurada")
    SqsClient(settings).send(
        settings.validar_pedido_response_queue_url,
        _response_envelope(envelope, payload),
    )


def _item_error(product_id: int, code: str, message: str) -> ErroValidacao:
    return ErroValidacao(code=code, product_id=product_id, message=message)


def _validar_item(quantity: int, produto: Produto) -> list[ErroValidacao]:
    errors = []
    estoque_error = validar_estoque(quantity, produto)
    if estoque_error is not None:
        errors.append(estoque_error)
    quantidade_error = validar_quantidade_minima(quantity, produto)
    if quantidade_error is not None:
        errors.append(quantidade_error)
    return errors


def handle(
    envelope: MessageEnvelope,
    settings: Settings,
    client: httpx.Client | None = None,
    cache: CatalogoCache = CATALOG_CACHE,
) -> None:
    payload = envelope.payload
    document = payload["customer_document"]
    items = [ItemValidacao(**item) for item in payload["items"]]
    if not items:
        raise ValueError("payload sem itens")

    errors: list[ErroValidacao] = []
    if not validar_documento(document):
        errors.append(
            ErroValidacao(
                code="INVALID_DOCUMENT",
                product_id=None,
                message=f"customer_document '{mask_document(document)}' nao e um CPF/CNPJ valido",
            )
        )

    produtos: dict[int, Produto] = {}
    owns_client = client is None
    http_client = client or httpx.Client()
    try:
        for item in items:
            try:
                produto = buscar_produto(http_client, cache, item.product_id, _base_url(settings))
            except ProdutoNaoEncontradoError:
                errors.append(
                    _item_error(
                        item.product_id,
                        "PRODUCT_NOT_FOUND",
                        f"Produto {item.product_id} nao encontrado",
                    )
                )
                continue
            produtos[item.product_id] = produto
            errors.extend(_validar_item(item.quantity, produto))
    finally:
        if owns_client:
            http_client.close()

    if errors:
        _publish_response(envelope, settings, montar_resposta_reprovada(errors))
        return

    enriched: list[ItemEnriquecido] = [
        calcular_item(item, produtos[item.product_id]) for item in items
    ]
    subtotal, discount_total, total = calcular_totais(enriched)
    limit_error = validar_limite_total(total)
    if limit_error is not None:
        _publish_response(envelope, settings, montar_resposta_reprovada([limit_error]))
        return

    _publish_response(
        envelope,
        settings,
        montar_resposta_aprovada(enriched, subtotal, discount_total, total),
    )
