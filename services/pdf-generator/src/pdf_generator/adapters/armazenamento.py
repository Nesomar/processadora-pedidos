"""Gravacao da nota fiscal no S3 (data-model.md — adapters/armazenamento.py).

Qualquer excecao de `S3Client.put_object` (indisponibilidade, timeout, erro 5xx) propaga sem
tratamento — e falha tecnica (FR-006), o `worker_loop` decide nao confirmar a mensagem.
"""

from pedidos_shared import S3Client


def salvar_pdf(s3: S3Client, bucket: str, key: str, conteudo: bytes) -> None:
    s3.put_object(bucket, key, conteudo, content_type="application/pdf")
