"""Extracao de notificacoes de arquivo do evento nativo do S3 (research.md #4)."""

from dataclasses import dataclass
from urllib.parse import unquote_plus


@dataclass
class NotificacaoArquivo:
    bucket: str
    key: str


def extrair_notificacoes(body: dict) -> list[NotificacaoArquivo]:
    """Lista vazia para mensagens sem `Records` (ex.: `s3:TestEvent`) — nada a processar."""
    records = body.get("Records")
    if not records:
        return []
    return [
        NotificacaoArquivo(
            bucket=record["s3"]["bucket"]["name"],
            key=unquote_plus(record["s3"]["object"]["key"]),
        )
        for record in records
    ]
