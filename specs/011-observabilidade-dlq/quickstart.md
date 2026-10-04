# Quickstart: validar observabilidade e reprocessamento de DLQ

## Pré-requisitos

```bash
make up    # stack completa (Ministack + bootstrap + serviços)
set -a && . ./.env && set +a
```

Para forçar uma mensagem na DLQ, coloque uma mensagem "venenosa" direto na DLQ (o reprocessamento
é o que se quer validar, não a causa da falha):

```bash
uv run python -c "
from pedidos_shared import Settings, SqsClient
SqsClient(Settings()).send_body(
    'http://localhost:4566/000000000000/validar_pedido_queue_dlq',
    '{\"message_id\":\"m-1\",\"correlation_id\":\"c-1\",\"order_id\":\"o-1\",'
    '\"occurred_at\":\"2026-10-03T21:00:00Z\",'
    '\"payload\":{\"customer_document\":\"12345678901\"}}')"
```

## Cenário 1 — resumo (US1)

```bash
curl -s http://localhost:8000/dlqs      # validar_pedido_queue com messages=1, as demais 0
```

## Cenário 2 — inspeção (US2)

```bash
curl -s http://localhost:8000/dlqs/validar_pedido_queue/mensagens   # order_id "o-1", documento "*******8901"
curl -s http://localhost:8000/dlqs/validar_pedido_queue/mensagens   # igual: listar não consome
curl -i http://localhost:8000/dlqs/fila_inexistente/mensagens       # 404
```

## Cenário 3 — reprocessamento (US3)

```bash
curl -s -X POST http://localhost:8000/dlqs/validar_pedido_queue/reprocessamento   # reprocessed: 1
curl -s -X POST http://localhost:8000/dlqs/validar_pedido_queue/reprocessamento   # reprocessed: 0
curl -s -X POST http://localhost:8000/dlqs/validar_pedido_queue/reprocessamento \
  -H 'Content-Type: application/json' -d '{"message_id":"inexistente"}'            # 404
```

Esperado: a mensagem sai da DLQ e o Order Validator a consome (descarta se o pedido `o-1` não
existir — comportamento de negócio, não da feature).

## Testes automatizados

```bash
uv run --all-packages python -m pytest shared/pedidos_shared/tests/clients/test_sqs.py \
  services/api-gateway/tests/test_dlq_domain.py services/api-gateway/tests/test_dlqs.py -v
```

Contrato: [dlq-endpoints.md](./contracts/dlq-endpoints.md).
