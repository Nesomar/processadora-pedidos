# lambda-line-processor

Worker Python do Sistema de Processamento de Pedidos. Consome `pedido_lines_queue` (sem
`MessageEnvelope`, mesmo formato de `007-file-consumer`) e, para cada mensagem, chama o endpoint
HTTP correspondente do `api-gateway` já existente — fechando o pipeline de entrada em lote.

Este serviço não escreve em `orders` nem publica em nenhuma fila. A chamada HTTP ao `api-gateway`
é a segunda exceção documentada ao princípio I.1 da constitution (v1.0.2): o API Gateway é a porta
de entrada HTTP única do sistema, tanto pro fluxo online quanto pro batch.

## Fila consumida

| Consome | Chama |
|---|---|
| `pedido_lines_queue` | `POST /pedidos`, `PUT /pedidos/{order_id}` ou `POST /pedidos/{order_id}/cancelamento` no `api-gateway` |

Não usa o `MessageEnvelope` comum — ver
[`specs/008-lambda-line-processor/contracts/lambda-line-processor-calls.md`](../../specs/008-lambda-line-processor/contracts/lambda-line-processor-calls.md).

## Variaveis de ambiente

Usa `pedidos_shared.Settings` para AWS/Ministack, filas e idempotência, mais:

| Variavel | Papel |
|---|---|
| `API_GATEWAY_BASE_URL` | URL base do `api-gateway`. Obrigatória (sem default). |

Requer também `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`PROCESSED_MESSAGES_TABLE_NAME` e `PEDIDO_LINES_QUEUE_URL`.

## Rodar localmente

```bash
uv sync --package lambda-line-processor
source .env
uv run --package lambda-line-processor python -m lambda_line_processor.main
```

Health check:

```bash
curl http://localhost:8084/health
```

Resposta esperada: `{"status":"ok"}`.

## Testes

```bash
uv run --package lambda-line-processor pytest services/lambda-line-processor/tests -v
uv run --package lambda-line-processor ruff check services/lambda-line-processor
uv run --package lambda-line-processor ruff format --check services/lambda-line-processor
```

O teste de integração (`test_idempotencia.py`) bate num `api-gateway` real — pula automaticamente
se `AWS_ENDPOINT_URL` ou o `api-gateway` não estiverem acessíveis.
