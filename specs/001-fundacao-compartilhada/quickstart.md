# Quickstart: pedidos_shared

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **Contrato**: [contracts/pedidos_shared-api.md](./contracts/pedidos_shared-api.md)

## Pré-requisitos

- Python 3.12, `uv` instalado
- Ministack rodando localmente (ver `infra/docker-compose.yml`), com fila, tabela e bucket já
  criados por `infra/bootstrap/`

## Setup

```bash
uv sync --package pedidos-shared
```

## Rodar os testes unitários (não requer Ministack)

```bash
uv run --package pedidos-shared pytest shared/pedidos_shared/tests -v
```

**Esperado**: cobre modelos Pydantic, `is_valid_transition`, `mask_document` e
`parse_fixed_width`, todos passando — valida SC-005.

## Validação de integração (requer Ministack local)

Requer o ambiente de `002-infraestrutura-local` rodando (`docker compose up` em `infra/`), que já
cria `.env` com as variáveis abaixo a partir de `.env.example`:

```bash
source .env

uv run --package pedidos-shared python - <<'PY'
from pedidos_shared.settings import Settings
from pedidos_shared.clients.sqs import SqsClient
from pedidos_shared.models import PedidoSolicitado

settings = Settings()
sqs = SqsClient(settings)

msg = PedidoSolicitado(
    order_id="11111111-1111-1111-1111-111111111111",
    correlation_id="22222222-2222-2222-2222-222222222222",
    items=[],
    customer_document="12345678900",
)
sqs.send(settings.pedido_solicitado_queue_url, msg)
print("mensagem enviada e validada pelo contrato Pydantic")
PY
```

**Esperado**: script roda sem exceção, mensagem aparece na fila do Ministack — valida SC-003 (zero
configuração de endpoint no código do serviço) e User Story 2.

## Validar Settings falhando sem variável obrigatória

```bash
unset ORDERS_TABLE_NAME
uv run --package pedidos-shared python -c "from pedidos_shared.settings import Settings; Settings()"
```

**Esperado**: `pydantic.ValidationError` citando `ORDERS_TABLE_NAME` — valida FR-005 / edge case de
variável ausente.

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
