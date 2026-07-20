# Quickstart: order-validator

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **Contrato**: [contracts/order-validator-messages.md](./contracts/order-validator-messages.md)

## Pré-requisitos

- Python 3.12, `uv` instalado
- Ministack rodando com os recursos já criados (`docker compose -f infra/docker-compose.yml up -d`)
- Acesso à internet para validar contra a API real do dummyjson.com (só nesta validação manual —
  a suíte automatizada não depende disso, research.md #6)

## Setup

```bash
uv sync --package order-validator
```

## Testes unitários e de integração (Ministack real, catálogo mockado)

```bash
uv run --package order-validator pytest services/order-validator/tests -v
```

## Subir o worker localmente

```bash
source .env
uv run --package order-validator python -m order_validator.main
```

**Esperado**: `GET http://localhost:8081/health` responde `{"status":"ok"}`; log estruturado
confirma o consumidor de `validar_pedido_queue` iniciado.

## Validar US1 — pedido aprovado com totais corretos (SC-001)

```bash
uv run --package pedidos-shared python -c "
from pedidos_shared.settings import Settings
from pedidos_shared.clients.sqs import SqsClient
from pedidos_shared.models import MessageEnvelope
from datetime import datetime, timezone
import uuid

s = Settings()
sqs = SqsClient(s)
order_id = str(uuid.uuid4())
envelope = MessageEnvelope(
    message_id=str(uuid.uuid4()), correlation_id=str(uuid.uuid4()), order_id=order_id,
    occurred_at=datetime.now(timezone.utc),
    payload={'customer_document': '52998224725', 'items': [{'product_id': 1, 'quantity': 3}]},
)
sqs.send(s.validar_pedido_queue_url, envelope)
print('order_id:', order_id)
"
```

**Esperado**: em segundos, uma mensagem aparece em `validar_pedido_response_queue` com
`approved=true`, o item enriquecido com dados reais do produto 1 do dummyjson.com, e
`subtotal`/`discount_total`/`total` calculados. `52998224725` é um CPF com dígito verificador
válido (uso comum em exemplos de teste).

## Validar US2 — documento inválido (SC-002)

Repetir o passo anterior com `customer_document: "11111111111"` (CPF estruturalmente válido em
tamanho, mas reprovado pelo dígito verificador — todos os dígitos iguais).

**Esperado**: resposta com `approved=false`, erro `INVALID_DOCUMENT` (`product_id: null`).

## Validar US3 — item abaixo do mínimo ou sem estoque (SC-002)

Repetir com `items: [{"product_id": 1, "quantity": 1}]` — a maioria dos produtos do dummyjson
tem `minimumOrderQuantity` acima de 1.

**Esperado**: resposta com `approved=false`, erro `BELOW_MINIMUM_ORDER_QUANTITY` referenciando
`product_id: 1`.

## Validar US4 — limite de total excedido (SC-002)

Repetir com uma quantidade grande o suficiente para o `total` calculado superar R$ 100.000,00
(ex.: `quantity` alto em um produto de preço mais alto do catálogo).

**Esperado**: resposta com `approved=false`, erro `ORDER_TOTAL_EXCEEDS_LIMIT` (`product_id:
null`).

## Validar US5 — produto inexistente (SC-002)

Repetir com `items: [{"product_id": 999999, "quantity": 1}]`.

**Esperado**: resposta com `approved=false`, erro `PRODUCT_NOT_FOUND` referenciando
`product_id: 999999`.

## Validar US8 — idempotência (SC-004)

Reenviar a mesma mensagem do passo US1 (mesmo `message_id`).

**Esperado**: nenhuma segunda mensagem em `validar_pedido_response_queue`; log em nível `info`
confirma a duplicidade descartada.
