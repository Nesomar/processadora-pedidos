"""Testes de mask_document (data-model.md — Função de mascaramento; FR-011)."""

import pytest

from pedidos_shared.masking import mask_document


@pytest.mark.parametrize(
    "document,expected",
    [
        ("12345678901", "*******8901"),
        ("12345678000199", "**********0199"),
        ("12345", "*2345"),
    ],
)
def test_mask_document_preserves_last_four_chars(document: str, expected: str) -> None:
    assert mask_document(document) == expected


@pytest.mark.parametrize("document", ["1234", "123", "1", ""])
def test_mask_document_masks_entirely_when_four_chars_or_fewer(document: str) -> None:
    result = mask_document(document)
    assert result == "*" * len(document)


def test_mask_document_preserves_original_length() -> None:
    document = "98765432100"
    assert len(mask_document(document)) == len(document)
