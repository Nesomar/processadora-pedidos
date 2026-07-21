# Quickstart: lambda-line-processor

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **Contrato**: [contracts/lambda-line-processor-calls.md](./contracts/lambda-line-processor-calls.md)

## Pré-requisitos

- Python 3.12, `uv` instalado
- Ministack **e** `api-gateway` rodando (`docker compose -f infra/docker-compose.yml up -d`) —
  diferente das demais features, o teste de integração desta bate num serviço real do próprio
  monorepo, não só no Ministack

## Setup

```bash
uv sync --package lambda-line-processor
```

## Testes unitários e de integração (Ministack + api-gateway reais)

```bash
uv run --package lambda-line-processor pytest services/lambda-line-processor/tests -v
```

## Subir o worker localmente

```bash
source .env
uv run --package lambda-line-processor python -m lambda_line_processor.main
```

**Esperado**: `GET http://localhost:8084/health` responde `{"status":"ok"}`; log estruturado
confirma o consumidor de `pedido_lines_queue` iniciado.

## Validar US1 — encaminhar SOLICITAR válido (SC-001)

Com `api-gateway` rodando em `http://localhost:8000`:

```bash
uv run --package pedidos-shared python -c "
from pedidos_shared.settings import Settings
from pedidos_shared.clients.sqs import SqsClient
import json

s = Settings()
sqs = SqsClient(s)
sqs.send_raw(s.pedido_lines_queue_url, {
    'source_file': 'quickstart.txt', 'line_number': 1, 'operation': 'SOLICITAR',
    'raw_line': '...', 'order_id': None,
    'parsed': {
        'customer_id': 'CUST00001', 'customer_name': 'Maria Silva',
        'customer_document': '52998224725', 'channel': 'BATCH',
        'items': [{'product_id': 1, 'quantity': 3}],
        'source_file': 'quickstart.txt', 'source_line': 1,
    },
})
print('mensagem publicada')
"
```

**Esperado**: em segundos, `GET http://localhost:8000/pedidos?customerId=CUST00001` mostra o
pedido criado com `channel=BATCH` e `status=VALIDATING` (ou adiante).

## Validar US2 — recusa de negócio permanente (SC-002)

Repetir com `operation: "EDITAR"` e um `order_id` que não existe.

**Esperado**: nenhuma nova tentativa; log estruturado registra o `404` do API Gateway.

## Validar US4 — idempotência (SC-003)

Reenviar a mesma mensagem do passo US1 (mesmo corpo, nova publicação simula redelivery via
`MessageId` nativo do SQS — ver `specs/007-file-consumer/quickstart.md` para o mesmo padrão).

**Esperado**: nenhuma segunda chamada ao API Gateway; log confirma a duplicidade descartada.
