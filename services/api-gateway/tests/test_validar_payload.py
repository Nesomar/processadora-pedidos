"""Teste de validar_payload — FR-002 (data-model.md)."""

import pytest

from api_gateway.domain.validar_payload import PayloadInvalidoError, validar_payload


def test_validar_payload_accepts_valid_payload() -> None:
    validar_payload("CUST00001", "12345678901", [50, 10])


@pytest.mark.parametrize(
    "customer_id",
    ["A" * 21, "CUST-00001", "cust 00001", ""],
)
def test_validar_payload_rejects_invalid_customer_id(customer_id: str) -> None:
    with pytest.raises(PayloadInvalidoError):
        validar_payload(customer_id, "12345678901", [1])


@pytest.mark.parametrize("document", ["123.456.789-01", "abcdefghijk", ""])
def test_validar_payload_rejects_non_numeric_document(document: str) -> None:
    with pytest.raises(PayloadInvalidoError):
        validar_payload("CUST00001", document, [1])


def test_validar_payload_rejects_empty_items() -> None:
    with pytest.raises(PayloadInvalidoError):
        validar_payload("CUST00001", "12345678901", [])


def test_validar_payload_rejects_more_than_fifty_items() -> None:
    with pytest.raises(PayloadInvalidoError):
        validar_payload("CUST00001", "12345678901", [1] * 51)


def test_validar_payload_rejects_zero_or_negative_quantity() -> None:
    with pytest.raises(PayloadInvalidoError):
        validar_payload("CUST00001", "12345678901", [1, 0])
    with pytest.raises(PayloadInvalidoError):
        validar_payload("CUST00001", "12345678901", [-1])
