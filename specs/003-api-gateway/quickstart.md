# Quickstart: api-gateway

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **Contrato**: [contracts/api-gateway-http.md](./contracts/api-gateway-http.md)

## Pré-requisitos

- Python 3.12, `uv` instalado
- Ministack rodando localmente com os recursos já criados (`docker compose -f infra/docker-compose.yml up -d`, feature `002-infraestrutura-local`)
- `pedidos_shared` disponível no workspace (feature `001-fundacao-compartilhada`)

## Setup

```bash
uv sync --package api-gateway
```

## Rodar os testes unitários (não requer Ministack)

```bash
uv run --package api-gateway pytest services/api-gateway/tests -v -k "not integration"
```

**Esperado**: cobre validação de payload (FR-002), elegibilidade de edição/cancelamento
(`is_valid_transition`), roteamento e mascaramento — com `SqsClient`/`DynamoDbClient` mockados,
sem rede.

## Subir o serviço localmente

```bash
source .env  # gerado a partir de .env.example (feature 002)
uv run --package api-gateway uvicorn api_gateway.main:app --port 8000
```

## Validar criação de pedido (US1, SC-001)

```bash
curl -s -X POST http://localhost:8000/pedidos \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "CUST00001",
    "customer_name": "Maria Silva",
    "customer_document": "12345678901",
    "items": [{"product_id": 1, "quantity": 50}]
  }'
```

**Esperado**: `202 Accepted` com `order_id` e `correlation_id`, em menos de 1 segundo. Confirmar
que a mensagem chegou na fila:

```bash
uv run --package pedidos-shared python -c "
from pedidos_shared.settings import Settings
from pedidos_shared.clients.sqs import SqsClient
s = Settings()
sqs = SqsClient(s)
print(sqs.receive(s.solicitar_pedido_queue_url))
"
```

## Validar rejeição de payload inválido (US1 cenário 2, SC-002)

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/pedidos \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST00001", "items": []}'
```

**Esperado**: `400`, sem `order_id` gerado.

## Validar consulta e listagem (US5, US6, SC-003, SC-004)

O Order Processor ainda não existe como feature implementada, então semeie um registro de teste
direto na tabela `orders` (prática de "arrange" de teste — research.md #8, não é o serviço quem
escreve):

```bash
uv run --package pedidos-shared python -c "
from pedidos_shared.settings import Settings
from pedidos_shared.clients.dynamodb import DynamoDbClient
from datetime import datetime, timezone
s = Settings()
db = DynamoDbClient(s)
db.put_item(s.orders_table_name, {
    'PK': 'ORDER#11111111-1111-1111-1111-111111111111',
    'SK': 'METADATA',
    'GSI1PK': 'CUSTOMER#CUST00001',
    'GSI1SK': f'{datetime.now(timezone.utc).isoformat()}#11111111-1111-1111-1111-111111111111',
    'order_id': '11111111-1111-1111-1111-111111111111',
    'customer_id': 'CUST00001',
    'customer_name': 'Maria Silva',
    'customer_document': '12345678901',
    'channel': 'HTTP',
    'status': 'RECEIVED',
    'items': [],
    'correlation_id': '22222222-2222-2222-2222-222222222222',
    'created_at': datetime.now(timezone.utc).isoformat(),
    'updated_at': datetime.now(timezone.utc).isoformat(),
    'version': 0,
})
"

curl -s http://localhost:8000/pedidos/11111111-1111-1111-1111-111111111111
curl -s "http://localhost:8000/pedidos?customerId=CUST00001"
```

**Esperado**: ambos retornam o pedido com `customer_document` mascarado (`*******8901`).

## Validar conflito de estado (US3/US4 cenário 2, SC-005)

Repita a consulta acima após alterar manualmente o `status` do item semeado pra `COMPLETED`, depois
tente editar ou cancelar:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X PUT http://localhost:8000/pedidos/11111111-1111-1111-1111-111111111111 \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST00001", "customer_name": "Maria Silva", "customer_document": "12345678901", "items": [{"product_id": 1, "quantity": 1}]}'
```

**Esperado**: `409`.

## Validar `/health`

```bash
curl -s http://localhost:8000/health
```

**Esperado**: `{"status": "ok"}`.
