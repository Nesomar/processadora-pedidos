"""Montagem da chave S3 da nota fiscal (data-model.md, research.md #3)."""

from datetime import datetime


def montar_chave_invoice(order_id: str, momento: datetime) -> str:
    return f"invoices/{momento.year:04d}/{momento.month:02d}/{momento.day:02d}/{order_id}.pdf"
