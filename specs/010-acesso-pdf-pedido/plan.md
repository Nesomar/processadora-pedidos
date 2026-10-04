# Implementation Plan: Acesso ao PDF da Nota Fiscal do Pedido

**Branch**: `feature/010-acesso-pdf-pedido` | **Date**: 2026-10-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-acesso-pdf-pedido/spec.md`.

## Summary

Novo endpoint `GET /pedidos/{order_id}/nota-fiscal` no `api-gateway` que lê o pedido no DynamoDB
(somente leitura), valida o estado e devolve o PDF direto na resposta (`application/pdf`), lendo o
objeto do S3 via `S3Client.get_object` (já existente em `pedidos_shared`). Nenhum link
pré-assinado. Para não vazar a chave interna (FR-004), `PedidoResponse` troca `invoice_s3_key`
por `invoice_available: bool` (FR-006). Nenhuma mudança em fila, worker, máquina de estados ou
PDF Generator.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI (`Response` com `media_type="application/pdf"`),
`pedidos_shared` (`S3Client`, `DynamoDbClient`, `Settings`); nenhuma dependência nova

**Storage**: lê `orders` (DynamoDB) e o bucket `pedidos-bucket` (S3, `invoices/...`); nenhuma escrita

**Testing**: pytest; unitário com `S3Client`/`DynamoDbClient` mockados (cada status, chave ausente,
objeto ausente, cabeçalhos); integração contra Ministack (put do PDF + pedido semeado, GET devolve
os mesmos bytes); atualizar `tests/e2e` (pedido `COMPLETED` → baixa PDF começando com `%PDF`)

**Target Platform**: container Docker (Linux), local via Ministack

**Project Type**: web-service (extensão de serviço existente)

**Performance Goals**: SC-001 — PDF devolvido em até 3 s

**Constraints**: somente leitura (FR-007); sem chave/URL/credencial do S3 em nenhuma resposta
(FR-004/005); log sem documento em claro (FR-008); PDF pequeno, lido inteiro em memória
(Assumptions) — sem streaming em chunks

**Scale/Scope**: 1 rota nova, 1 método novo de erro tipado em `S3Client`, 1 campo de resposta trocado

## Constitution Check

| Gate (constitution v1.0.2) | Status | Nota |
|---|---|---|
| I.1 Event-driven, sem HTTP entre serviços de processamento | PASS | O gateway lê S3/DynamoDB direto (já faz leitura de `orders` em `GET /pedidos/{id}`); nenhuma chamada HTTP nova entre serviços. |
| I.2 Máquina de estados | PASS | Gateway só lê o status; não escreve em `orders` (VII.2). |
| I.3 Idempotência | N/A | Endpoint de leitura, sem consumo de fila. |
| I.4 DLQ | N/A | Sem fila nova. |
| I.5 Falha é dado | PASS | Falha técnica de S3 (não `NoSuchKey`) propaga como 5xx + log estruturado; ausência do objeto é resposta 404 explícita. |
| I.6 Local-first | PASS | Ministack S3. |
| II Stack | PASS | Sem dependência nova. |
| III Contratos em `shared` | PASS | Erro tipado de objeto ausente nasce em `pedidos_shared` (como `put_object` ganhou `content_type`); schema da resposta fica em `api_gateway/schemas.py`. |
| IV Sem infra hardcoded / logs JSON / type hints | PASS | Bucket vem de `Settings.pedidos_bucket_name`; log JSON com `orderId` e `correlationId`. |
| V Git | PASS | Branch `feature/010-acesso-pdf-pedido` criada. |
| VII Code review | PASS (guia) | Rodar review antes do PR; foco em segurança (sem vazamento de chave) e VII.2. |
| VIII Design de código | PASS | `handlers/baixar_nota_fiscal.py` (rota), `domain/nota_fiscal.py` (função pura de elegibilidade), reuso de `adapters/orders_repository.get_by_id`. |
| IX Definição de pronto | PASS (guia) | Testes, ruff, README/`examples/`, review, PR. |

Nenhuma violação a justificar.

## Project Structure

### Documentation (this feature)

```text
specs/010-acesso-pdf-pedido/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── nota-fiscal-endpoint.md
└── tasks.md             # /speckit-tasks — NÃO criado aqui
```

### Source Code (repository root)

```text
shared/pedidos_shared/src/pedidos_shared/clients/s3.py   # get_object levanta ObjectNotFoundError em NoSuchKey
shared/pedidos_shared/src/pedidos_shared/__init__.py     # exporta ObjectNotFoundError

services/api-gateway/src/api_gateway/
├── deps.py                          # + get_s3_client / S3ClientDep
├── schemas.py                       # PedidoResponse: invoice_s3_key -> invoice_available
├── main.py                          # include_router(baixar_nota_fiscal_router)
├── domain/nota_fiscal.py            # chave_da_nota_fiscal(order) + exceções de negócio (pura)
└── handlers/baixar_nota_fiscal.py   # GET /pedidos/{order_id}/nota-fiscal

services/api-gateway/tests/
├── conftest.py                      # + override get_s3_client com MagicMock
├── test_nota_fiscal.py              # unitário + integração
└── test_consultar_pedido.py         # asserta invoice_available e ausência de invoice_s3_key

tests/e2e/                           # test_online_happy_path / test_editar_pedido: troca assert da chave por GET do PDF
README.md, examples/                 # curl --output nota.pdf
docs/01-dominio-e-contratos.md       # extensão: nota sobre o novo endpoint (spec só estende o contrato)
```

**Structure Decision**: extensão do serviço `api-gateway` existente seguindo o padrão
handler + domain + deps; sem novo serviço ou camada.

## Complexity Tracking

Sem violações.
