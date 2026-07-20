# api-gateway

Serviço FastAPI: única porta HTTP de entrada do Sistema de Processamento de Pedidos
(`docs/01-dominio-e-contratos.md` §1). Aceita clientes HTTP externos e a chamada interna do
Lambda Line Processor no fluxo BATCH — exceção documentada a constitution I.1, ver
[`specs/003-api-gateway/plan.md`](../../specs/003-api-gateway/plan.md).

## Rotas

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/pedidos` | Cria pedido (HTTP direto ou linha de arquivo batch) |
| `PUT` | `/pedidos/{order_id}` | Edita pedido existente |
| `POST` | `/pedidos/{order_id}/cancelamento` | Cancela pedido existente |
| `GET` | `/pedidos/{order_id}` | Consulta pedido (`customer_document` mascarado) |
| `GET` | `/pedidos?customerId=X` | Lista pedidos do cliente, mais recentes primeiro |
| `GET` | `/health` | Liveness check |

Contrato completo: [`specs/003-api-gateway/contracts/api-gateway-http.md`](../../specs/003-api-gateway/contracts/api-gateway-http.md).

Este serviço **nunca escreve** na tabela `orders` — só publica mensagens (`solicitar_pedido_queue`,
`editar_pedido_queue`, `cancelar_pedido_queue`) e lê (`GET`). Toda escrita real é feita pelo Order
Processor ao consumir a mensagem.

## Variáveis de ambiente

Usa `pedidos_shared.Settings` (feature `001-fundacao-compartilhada`) — mesmo `.env` do resto do
sistema. Este serviço requer, no mínimo: `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `PROCESSED_MESSAGES_TABLE_NAME`, `ORDERS_TABLE_NAME`,
`SOLICITAR_PEDIDO_QUEUE_URL`, `EDITAR_PEDIDO_QUEUE_URL`, `CANCELAR_PEDIDO_QUEUE_URL`.

## Rodar localmente

```bash
uv sync --package api-gateway
source .env  # gerado a partir de .env.example (feature 002), com Ministack já rodando
uv run --package api-gateway uvicorn api_gateway.main:app --port 8000
```

## Testes

```bash
# unitários (não requerem Ministack)
uv run --package api-gateway pytest services/api-gateway/tests -v -k "not integration"

# lint/format
uv run --package api-gateway ruff check services/api-gateway
uv run --package api-gateway ruff format --check services/api-gateway
```

O teste de integração (`test_solicitar_pedido_integration_publishes_real_message_under_one_second`)
é pulado automaticamente quando o Ministack local não está rodando.
