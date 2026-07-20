# pdf-generator

Worker Python do Sistema de Processamento de Pedidos. Consome `pdf_request_queue`, gera a nota
fiscal em PDF (ReportLab) do pedido aprovado, grava o arquivo no bucket de pedidos e publica o
resultado em `pdf_response_queue`.

Este servico nao expoe API HTTP de negocio e nunca escreve em `orders`. Nao ha nenhuma chamada
HTTP externa (diferente do order-validator) — toda a integracao e SQS + S3 via Ministack.

## Filas

| Consome | Publica |
|---|---|
| `pdf_request_queue` | `pdf_response_queue` |

Contrato: [`specs/006-pdf-generator/contracts/pdf-generator-messages.md`](../../specs/006-pdf-generator/contracts/pdf-generator-messages.md).

## Variaveis de ambiente

Usa `pedidos_shared.Settings` para AWS/Ministack, filas, bucket e idempotencia — nenhuma variavel
nova e necessaria. Requer `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `PROCESSED_MESSAGES_TABLE_NAME`, `PEDIDOS_BUCKET_NAME`,
`PDF_REQUEST_QUEUE_URL` e `PDF_RESPONSE_QUEUE_URL`.

## Rodar localmente

```bash
uv sync --package pdf-generator
source .env
uv run --package pdf-generator python -m pdf_generator.main
```

Health check:

```bash
curl http://localhost:8082/health
```

Resposta esperada: `{"status":"ok"}`.

## Testes

```bash
uv run --package pdf-generator pytest services/pdf-generator/tests -v
uv run --package pdf-generator ruff check services/pdf-generator
uv run --package pdf-generator ruff format --check services/pdf-generator
```

Testes de integracao contra Ministack pulam automaticamente quando `AWS_ENDPOINT_URL` nao esta
acessivel.
