# file-consumer

Worker Python do Sistema de Processamento de Pedidos. Consome `s3_notifications_queue` (evento
nativo do S3, não `MessageEnvelope`), busca o arquivo posicional notificado no bucket de pedidos,
faz o parse via `pedidos_shared.file_layout.parse_file` e publica uma mensagem em
`pedido_lines_queue` por pedido válido do arquivo.

Este serviço não expõe API HTTP de negócio e nunca escreve em `orders` nem chama o API Gateway —
isso é responsabilidade do Lambda Line Processor (fora do escopo). Não há nenhuma chamada HTTP
externa — toda a integração é S3 + SQS via Ministack.

## Filas

| Consome | Publica |
|---|---|
| `s3_notifications_queue` | `pedido_lines_queue` |

Nenhuma das duas usa o `MessageEnvelope` comum — ver
[`specs/007-file-consumer/contracts/file-consumer-messages.md`](../../specs/007-file-consumer/contracts/file-consumer-messages.md).

## Variaveis de ambiente

Usa `pedidos_shared.Settings` para AWS/Ministack, filas, bucket e idempotência — nenhuma variável
nova é necessária. Requer `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `PROCESSED_MESSAGES_TABLE_NAME`, `PEDIDOS_BUCKET_NAME`,
`S3_NOTIFICATIONS_QUEUE_URL` e `PEDIDO_LINES_QUEUE_URL`.

## Rodar localmente

```bash
uv sync --package file-consumer
source .env
uv run --package file-consumer python -m file_consumer.main
```

Health check:

```bash
curl http://localhost:8083/health
```

Resposta esperada: `{"status":"ok"}`.

## Gerar e enviar um arquivo de exemplo

```bash
uv run --package infra-bootstrap python infra/bootstrap/seed_file.py
```

## Testes

```bash
uv run --package file-consumer pytest services/file-consumer/tests -v
uv run --package pedidos-shared pytest shared/pedidos_shared/tests -v
uv run --package file-consumer ruff check services/file-consumer
uv run --package file-consumer ruff format --check services/file-consumer
```

Testes de integração contra Ministack pulam automaticamente quando `AWS_ENDPOINT_URL` não está
acessível.
