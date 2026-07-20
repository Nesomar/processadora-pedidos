# Quickstart: pdf-generator

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **Contrato**: [contracts/pdf-generator-messages.md](./contracts/pdf-generator-messages.md)

## Pré-requisitos

- Python 3.12, `uv` instalado
- Ministack rodando com os recursos já criados (`docker compose -f infra/docker-compose.yml up -d`)
- Sem dependência de rede externa — todo o fluxo (SQS + S3) roda local via Ministack
  (research.md #6)

## Setup

```bash
uv sync --package pdf-generator
```

## Testes unitários e de integração (Ministack real)

```bash
uv run --package pdf-generator pytest services/pdf-generator/tests -v
```

## Subir o worker localmente

```bash
source .env
uv run --package pdf-generator python -m pdf_generator.main
```

**Esperado**: `GET http://localhost:8082/health` responde `{"status":"ok"}`; log estruturado
confirma o consumidor de `pdf_request_queue` iniciado.

## Validar US1 — nota fiscal emitida com sucesso (SC-001)

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
    payload={
        'customer_name': 'Maria Silva',
        'customer_document': '52998224725',
        'items': [{
            'product_id': 1, 'quantity': 3, 'unit_price': '9.99',
            'discount_percentage': '10.48', 'line_total': '26.82',
            'product_title': 'Essence Mascara Lash Princess', 'product_sku': 'BEA-ESS-ESS-001',
        }],
        'subtotal': '29.97', 'discount_total': '3.15', 'total': '26.82',
    },
)
sqs.send(s.pdf_request_queue_url, envelope)
print('order_id:', order_id)
"
```

**Esperado**: em segundos, uma mensagem aparece em `pdf_response_queue` com `success=true` e
`s3_key` no formato `invoices/{ano}/{mes}/{dia}/{order_id}.pdf`; o objeto existe no bucket
configurado (`Settings.pedidos_bucket_name`) e começa com o cabeçalho `%PDF-`.

## Validar US2 — dados incompletos (SC-002)

Repetir o passo anterior com `items: []` (lista vazia).

**Esperado**: resposta com `success=false`, `s3_key` nulo e `error_message` explicando a
ausência de itens; nenhum objeto novo é gravado no S3.

## Validar US4 — idempotência (SC-003)

Reenviar a mesma mensagem do passo US1 (mesmo `message_id`).

**Esperado**: nenhuma segunda mensagem em `pdf_response_queue`; log em nível `info` confirma a
duplicidade descartada; nenhum novo objeto é gravado no S3.
