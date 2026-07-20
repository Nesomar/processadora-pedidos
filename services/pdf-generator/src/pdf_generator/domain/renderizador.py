"""Renderizacao da nota fiscal em PDF (data-model.md, research.md #1).

Assume que o payload ja passou por `domain.validacao.validar_solicitacao` — nao reexecuta
validacao de presenca de campos aqui.
"""

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FALLBACK = "—"


@dataclass
class ItemNotaFiscal:
    product_title: str
    product_sku: str
    quantity: int
    unit_price: Decimal
    discount_percentage: Decimal
    line_total: Decimal


@dataclass
class DadosNotaFiscal:
    customer_name: str
    customer_document: str
    items: list[ItemNotaFiscal]
    subtotal: Decimal
    discount_total: Decimal
    total: Decimal


def montar_dados_nota_fiscal(payload: dict) -> DadosNotaFiscal:
    items = [
        ItemNotaFiscal(
            product_title=item.get("product_title") or _FALLBACK,
            product_sku=item.get("product_sku") or _FALLBACK,
            quantity=item["quantity"],
            unit_price=Decimal(str(item["unit_price"])),
            discount_percentage=Decimal(str(item["discount_percentage"])),
            line_total=Decimal(str(item["line_total"])),
        )
        for item in payload["items"]
    ]
    return DadosNotaFiscal(
        customer_name=payload["customer_name"],
        customer_document=payload["customer_document"],
        items=items,
        subtotal=Decimal(str(payload["subtotal"])),
        discount_total=Decimal(str(payload["discount_total"])),
        total=Decimal(str(payload["total"])),
    )


def renderizar_nota_fiscal(dados: DadosNotaFiscal) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Nota Fiscal", styles["Title"]),
        Paragraph(f"Cliente: {dados.customer_name}", styles["Normal"]),
        Paragraph(f"Documento: {dados.customer_document}", styles["Normal"]),
        Spacer(1, 12),
    ]

    table_data = [["Produto", "SKU", "Qtd", "Preco unit.", "Desconto %", "Total item"]]
    table_data += [
        [
            item.product_title,
            item.product_sku,
            str(item.quantity),
            f"{item.unit_price:.2f}",
            f"{item.discount_percentage:.2f}",
            f"{item.line_total:.2f}",
        ]
        for item in dados.items
    ]
    table = Table(table_data)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Subtotal: {dados.subtotal:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Desconto total: {dados.discount_total:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Total: {dados.total:.2f}", styles["Normal"]))

    doc.build(elements)
    return buffer.getvalue()
