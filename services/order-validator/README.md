# order-validator

Worker Python do Sistema de Processamento de Pedidos. Consome `validar_pedido_queue`, consulta o
catalogo externo `dummyjson.com`, aplica regras de documento, estoque, quantidade minima e limite
de total, e publica a decisao em `validar_pedido_response_queue`.

Este servico nao expoe API HTTP de negocio e nunca escreve em `orders`. A unica chamada HTTP de
saida e para o catalogo externo de produtos.

## Filas

| Consome | Publica |
|---|---|
| `validar_pedido_queue` | `validar_pedido_response_queue` |

Contrato: [`specs/005-order-validator/contracts/order-validator-messages.md`](../../specs/005-order-validator/contracts/order-validator-messages.md).

## Variaveis de ambiente

Usa `pedidos_shared.Settings` para AWS/Ministack, filas e idempotencia, mais:

| Variavel | Papel |
|---|---|
| `CATALOG_PRODUCTS_BASE_URL` | URL base do catalogo externo. Default: `https://dummyjson.com` |

Tambem requer `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`PROCESSED_MESSAGES_TABLE_NAME`, `VALIDAR_PEDIDO_QUEUE_URL` e
`VALIDAR_PEDIDO_RESPONSE_QUEUE_URL`.

## Rodar localmente

```bash
uv sync --package order-validator
source .env
uv run --package order-validator python -m order_validator.main
```

Health check:

```bash
curl http://localhost:8081/health
```

Resposta esperada: `{"status":"ok"}`.

## Testes

```bash
uv run --package order-validator pytest services/order-validator/tests -v
uv run --package order-validator ruff check services/order-validator
uv run --package order-validator ruff format --check services/order-validator
```

Testes de integracao contra Ministack pulam automaticamente quando `AWS_ENDPOINT_URL` nao esta
acessivel.
