# Quickstart: pedidos_shared

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **Contrato**: [contracts/pedidos_shared-api.md](./contracts/pedidos_shared-api.md)

## Pré-requisitos

- Python 3.12, `uv` instalado
- Ministack rodando localmente, com filas/tabelas/bucket já criados (feature
  `002-infraestrutura-local`)

## Setup

```bash
uv sync --package pedidos-shared
```

## Rodar os testes unitários (não requer Ministack)

```bash
uv run --package pedidos-shared pytest shared/pedidos_shared/tests -v
```

**Esperado**: cobre `Order`/`OrderItem`/`MessageEnvelope`, `is_valid_transition`,
`mark_message_processed` (com mock de condição), `mask_document` e o parser posicional (incluindo
as 5 regras de rejeição) — valida SC-006.

## Validação de integração (requer Ministack local)

Requer o ambiente de `002-infraestrutura-local` rodando (`docker compose up` em `infra/`), que já
cria `.env` com as variáveis abaixo a partir de `.env.example`:

```bash
source .env

uv run --package pedidos-shared python - <<'PY'
from pedidos_shared.settings import Settings
from pedidos_shared.clients.sqs import SqsClient
from pedidos_shared.models import Order, OrderItem, MessageEnvelope
from datetime import datetime, timezone
import uuid

settings = Settings()
sqs = SqsClient(settings)

order = Order(
    order_id=str(uuid.uuid4()),
    customer_id="CUST00001",
    customer_name="Maria Silva",
    customer_document="12345678901",
    channel="HTTP",
    items=[OrderItem(product_id=1, quantity=50)],
    status="RECEIVED",
    correlation_id=str(uuid.uuid4()),
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
    version=0,
)
envelope = MessageEnvelope(
    message_id=str(uuid.uuid4()),
    correlation_id=order.correlation_id,
    order_id=order.order_id,
    occurred_at=datetime.now(timezone.utc),
    payload=order.model_dump(mode="json"),
)
sqs.send(settings.solicitar_pedido_queue_url, envelope)
print("mensagem enviada e validada pelo contrato Pydantic")
PY
```

**Esperado**: script roda sem exceção, mensagem aparece em `solicitar_pedido_queue` — valida SC-003
e User Story 2.

## Validar idempotência

```bash
uv run --package pedidos-shared python -c "
from pedidos_shared.settings import Settings
from pedidos_shared.idempotency import mark_message_processed
s = Settings()
mid = 'quickstart-test-1'
print('primeira chamada (deve processar):', mark_message_processed(mid, 'quickstart', s) is False)
print('segunda chamada (já processada):', mark_message_processed(mid, 'quickstart', s) is True)
"
```

**Esperado**: primeira chamada retorna `False` (processar), segunda retorna `True` (já processada)
— valida SC-005.

## Validar Settings falhando sem variável obrigatória

```bash
unset AWS_ENDPOINT_URL
uv run --package pedidos-shared python -c "from pedidos_shared.settings import Settings; Settings()"
```

**Esperado**: `pydantic.ValidationError` citando `AWS_ENDPOINT_URL`.

## Validar logging estruturado

```bash
uv run --package pedidos-shared python -c "
from pedidos_shared.logging import get_logger
logger = get_logger('quickstart')
logger.info('teste', extra={'order_id': '111', 'correlation_id': '222'})
"
```

**Esperado**: uma linha de stdout, JSON válido, contendo `orderId` e `correlationId` — valida
SC-004.

## Validar o parser posicional

```bash
uv run --package pedidos-shared python -c "
from pedidos_shared.file_layout import parse_file
with open('shared/pedidos_shared/tests/fixtures/exemplo.txt') as f:
    resultado = parse_file(f.readlines())
print(resultado)
"
```

**Esperado**: retorna os pedidos e itens do arquivo de exemplo (mesmo do §6.9 de
`docs/01-dominio-e-contratos.md`), sem erro.
