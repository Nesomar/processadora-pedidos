"""Regras puras de DLQ: filas do pipeline, identificação da mensagem e máscara (011)."""

import re
from typing import Any

from pedidos_shared import mask_document

# As 9 filas de docs/01-dominio-e-contratos.md §4; a DLQ de cada uma é `{fila}_dlq`.
FILAS = (
    "solicitar_pedido_queue",
    "editar_pedido_queue",
    "cancelar_pedido_queue",
    "validar_pedido_queue",
    "validar_pedido_response_queue",
    "pdf_request_queue",
    "pdf_response_queue",
    "s3_notifications_queue",
    "pedido_lines_queue",
)


def nome_dlq(fila: str) -> str:
    return f"{fila}_dlq"


def _texto(valor: Any) -> str | None:
    """Corpo de DLQ não é confiável: tipo errado vira `None`, não quebra a listagem."""
    return valor if isinstance(valor, str) else None


def identificar(body: Any) -> dict[str, Any]:
    """Extrai o que liga a mensagem ao pedido/arquivo; nunca levanta (corpo desconhecido → None)."""
    ident: dict[str, Any] = {
        "order_id": None,
        "correlation_id": None,
        "source_file": None,
        "source_line": None,
    }
    if not isinstance(body, dict):
        return ident

    if "order_id" in body and "correlation_id" in body:
        ident["order_id"] = _texto(body["order_id"])
        ident["correlation_id"] = _texto(body["correlation_id"])
    elif "source_file" in body and "line_number" in body:
        ident["source_file"] = _texto(body["source_file"])
        linha = body["line_number"]
        ident["source_line"] = (
            linha if isinstance(linha, int) and not isinstance(linha, bool) else None
        )
    else:
        try:
            ident["source_file"] = _texto(body["Records"][0]["s3"]["object"]["key"])
        except (KeyError, IndexError, TypeError):
            pass
    return ident


_DOCUMENTO_EM_TEXTO = re.compile(r"\d{11,14}")


def mascarar_texto(texto: str) -> str:
    """Corpo que não é JSON: mascara qualquer sequência de 11–14 dígitos (CPF/CNPJ) (FR-004)."""
    return _DOCUMENTO_EM_TEXTO.sub(lambda m: mask_document(m.group()), texto)


def mascarar(valor: Any) -> Any:
    """Cópia de `valor` com `customer_document` mascarado em qualquer nível (FR-004)."""
    if isinstance(valor, dict):
        return {
            chave: mask_document(item)
            if chave == "customer_document" and isinstance(item, str)
            else mascarar(item)
            for chave, item in valor.items()
        }
    if isinstance(valor, list):
        return [mascarar(item) for item in valor]
    return valor
