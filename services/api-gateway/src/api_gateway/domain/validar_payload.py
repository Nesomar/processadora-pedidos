"""Validação de payload de criação/edição de pedido (FR-002) — pura, sem I/O nem framework."""

import re

_CUSTOMER_ID_RE = re.compile(r"^[A-Za-z0-9]{1,20}$")
_DOCUMENT_RE = re.compile(r"^\d+$")
_MIN_ITEMS = 1
_MAX_ITEMS = 50


class PayloadInvalidoError(Exception):
    """Payload de pedido não atende às regras de FR-002."""


def validar_payload(customer_id: str, customer_document: str, quantities: list[int]) -> None:
    """Levanta `PayloadInvalidoError` se `customer_id`, `customer_document` ou `quantities`
    (uma entrada por item, na ordem recebida) violarem FR-002."""
    if not _CUSTOMER_ID_RE.match(customer_id):
        raise PayloadInvalidoError("customer_id deve ser alfanumérico com até 20 caracteres")
    if not _DOCUMENT_RE.match(customer_document):
        raise PayloadInvalidoError("customer_document deve conter somente dígitos")
    if not (_MIN_ITEMS <= len(quantities) <= _MAX_ITEMS):
        raise PayloadInvalidoError(f"items deve conter entre {_MIN_ITEMS} e {_MAX_ITEMS} itens")
    if any(quantity <= 0 for quantity in quantities):
        raise PayloadInvalidoError("quantity de cada item deve ser maior que zero")
