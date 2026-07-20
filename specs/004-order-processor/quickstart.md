# Quickstart: order-processor

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **Contrato**: [contracts/order-processor-messages.md](./contracts/order-processor-messages.md)

## Pré-requisitos

- Python 3.12, `uv` instalado
- Ministack rodando com os recursos já criados (`docker compose -f infra/docker-compose.yml up -d`, feature `002-infraestrutura-local`)

## Setup

```bash
uv sync --package order-processor
```

## Testes unitários (não requerem Ministack)

```bash
uv run --package order-processor pytest services/order-processor/tests -v -k "not integration"
```

## Subir o worker localmente

```bash
source .env
uv run --package order-processor python -m order_processor.main
```

**Esperado**: `GET http://localhost:8080/health` responde `{"status":"ok"}`; os 5 threads de
consumo iniciam sem erro (log estruturado confirmando).

## Validar US1 — solicitação de pedido dispara validação (SC-001)

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
    message_id=str(uuid.uuid4()),
    correlation_id=str(uuid.uuid4()),
    order_id=order_id,
    occurred_at=datetime.now(timezone.utc),
    payload={
        'customer_id': 'CUST00001', 'customer_name': 'Maria Silva',
        'customer_document': '12345678901', 'channel': 'HTTP',
        'items': [{'product_id': 1, 'quantity': 50}],
        'source_file': None, 'source_line': None,
    },
)
sqs.send(s.solicitar_pedido_queue_url, envelope)
print('order_id:', order_id)
"
```

**Esperado**: em segundos, o registro aparece em `orders` com `status=VALIDATING`, e uma mensagem
aparece em `validar_pedido_queue` com `{customer_document, items}`.

## Validar US2 — resposta de validação aprovada dispara PDF (SC-002)

Publicar em `validar_pedido_response_queue` uma resposta com `approved: true`, `order_id` igual ao
do passo anterior, `enriched_items`/`subtotal`/`discount_total`/`total` preenchidos (§5).

**Esperado**: o pedido passa para `INVOICING`, com os totais armazenados; uma mensagem aparece em
`pdf_request_queue`.

## Validar US3 — resposta de PDF conclui o pedido (SC-003)

Publicar em `pdf_response_queue` uma resposta com `success: true`, `order_id` igual, `s3_key`
preenchido.

**Esperado**: o pedido passa para `COMPLETED`, com `invoice_s3_key` preenchido.

## Validar US6 — idempotência (SC-004)

Reenviar a mesma mensagem de solicitação de pedido (mesmo `message_id`) do passo US1.

**Esperado**: nenhum segundo registro é criado, nenhuma segunda mensagem de validação é
publicada; log em nível `info` confirma a duplicidade descartada.

## Validar US4/US5 — edição e cancelamento rejeitados em estado incompatível (SC-006)

Publicar uma edição ou cancelamento para o `order_id` já `COMPLETED` do passo US3.

**Esperado**: nenhuma alteração no registro; log estruturado registra a rejeição como erro de
negócio.
