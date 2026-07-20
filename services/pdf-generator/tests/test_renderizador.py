from decimal import Decimal

from pdf_generator.domain.renderizador import (
    ItemNotaFiscal,
    montar_dados_nota_fiscal,
    renderizar_nota_fiscal,
)

_PAYLOAD = {
    "customer_name": "Maria Silva",
    "customer_document": "52998224725",
    "items": [
        {
            "product_id": 1,
            "quantity": 3,
            "unit_price": "9.99",
            "discount_percentage": "10.48",
            "line_total": "26.82",
            "product_title": "Essence Mascara Lash Princess",
            "product_sku": "BEA-ESS-ESS-001",
        }
    ],
    "subtotal": "29.97",
    "discount_total": "3.15",
    "total": "26.82",
}


def test_montar_dados_nota_fiscal_parses_decimals_and_items() -> None:
    dados = montar_dados_nota_fiscal(_PAYLOAD)

    assert dados.customer_name == "Maria Silva"
    assert dados.total == Decimal("26.82")
    assert dados.items == [
        ItemNotaFiscal(
            product_title="Essence Mascara Lash Princess",
            product_sku="BEA-ESS-ESS-001",
            quantity=3,
            unit_price=Decimal("9.99"),
            discount_percentage=Decimal("10.48"),
            line_total=Decimal("26.82"),
        )
    ]


def test_montar_dados_nota_fiscal_uses_fallback_for_missing_title_and_sku() -> None:
    payload = {
        **_PAYLOAD,
        "items": [{**_PAYLOAD["items"][0], "product_title": None, "product_sku": None}],
    }

    dados = montar_dados_nota_fiscal(payload)

    assert dados.items[0].product_title == "—"
    assert dados.items[0].product_sku == "—"


def test_renderizar_nota_fiscal_produces_non_empty_pdf() -> None:
    dados = montar_dados_nota_fiscal(_PAYLOAD)

    pdf_bytes = renderizar_nota_fiscal(dados)

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 0


def test_renderizar_nota_fiscal_with_multiple_items() -> None:
    payload = {
        **_PAYLOAD,
        "items": [_PAYLOAD["items"][0], {**_PAYLOAD["items"][0], "product_id": 2}],
    }
    dados = montar_dados_nota_fiscal(payload)

    pdf_bytes = renderizar_nota_fiscal(dados)

    assert pdf_bytes.startswith(b"%PDF-")
