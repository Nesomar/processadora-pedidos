# Implementation Plan: Observabilidade e Reprocessamento de DLQ

**Branch**: `feature/011-observabilidade-dlq` | **Date**: 2026-10-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-observabilidade-dlq/spec.md`.

## Summary

Três rotas operacionais no `api-gateway` sobre as DLQs que o bootstrap já cria (`{fila}_dlq`):

1. `GET /dlqs` — contagem de mensagens por DLQ (as 9 filas).
2. `GET /dlqs/{fila}/mensagens` — espia mensagens sem consumi-las (`VisibilityTimeout=0`),
   identificando `order_id`/`correlation_id` (envelope) ou `source_file`/`source_line` (filas fora
   do envelope), com `customer_document` mascarado.
3. `POST /dlqs/{fila}/reprocessamento` — devolve à fila de origem a DLQ inteira ou uma mensagem
   (`message_id`), só deletando da DLQ depois de reenviar com sucesso.

`SqsClient` (shared) ganha as primitivas de fila; o gateway ganha handlers finos e uma camada de
domínio pura (nomes das filas, identificação da mensagem, máscara). Nenhuma fila, tabela, worker ou
variável de ambiente nova; nenhuma escrita em `orders` (FR-010).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, `pedidos_shared` (`SqsClient`, `mask_document`, `get_logger`);
nenhuma dependência nova

**Storage**: SQS apenas (DLQs existentes); `orders` não é tocada

**Testing**: pytest; unitário com `SqsClient` mockado (rotas) e `boto3` mockado (métodos novos do
`SqsClient`); função pura de identificação/máscara; integração contra Ministack (mensagem real na
DLQ → resumo, listagem idempotente, reprocessamento move e esvazia); e2e fora de escopo (exigiria
falha técnica provocada)

**Target Platform**: container Docker (Linux), local via Ministack

**Project Type**: web-service (extensão de serviço existente)

**Performance Goals**: SC-001 — resumo em até 3 s (9 chamadas `GetQueueAttributes`)

**Constraints**: listar é somente leitura (FR-003); reprocessar nunca perde mensagem (FR-007);
sem documento em claro em resposta ou log (FR-004/009); sem autenticação (clarificação 1)

**Scale/Scope**: 3 rotas, 1 módulo de domínio, 6 métodos novos em `SqsClient`; listagem limitada a
um lote (padrão 10, máx 50)

## Constitution Check

| Gate (constitution v1.0.2) | Status | Nota |
|---|---|---|
| I.1 Event-driven, sem HTTP entre serviços de processamento | PASS | Só o gateway é tocado; ele já fala com SQS. Nenhuma chamada HTTP nova entre serviços. |
| I.2 Máquina de estados | PASS | Gateway não escreve em `orders`; quem muda estado é o Order Processor ao reconsumir a mensagem (FR-010). |
| I.3 Idempotência | PASS | Reprocessar reenvia o corpo original, com o mesmo `message_id`; consumidores já deduplicam (`is_message_processed`). |
| I.4 DLQ | PASS | Nenhuma fila nova; usa as DLQs existentes. |
| I.5 Falha é dado | PASS | Falha técnica ao mover propaga como 5xx + log estruturado; a mensagem permanece na DLQ. |
| I.6 Local-first | PASS | Ministack SQS. |
| II Stack | PASS | Sem dependência nova. |
| III Contratos em `shared` | PASS | Primitivas de fila nascem em `SqsClient`; schemas HTTP em `api_gateway/schemas.py`. |
| IV Sem infra hardcoded / logs JSON / type hints | PASS | URLs resolvidas por nome via `get_queue_url`; log JSON com contagem e fila. |
| V Git | PASS | Branch `feature/011-observabilidade-dlq`. |
| VII Code review | PASS (guia) | Foco: perda de mensagem no reprocessamento (ordem enviar→deletar) e vazamento de documento. |
| VIII Design de código | PASS | `handlers/` finos, `domain/dlq.py` puro, reuso de `publish`/`deps`. |
| IX Definição de pronto | PASS (guia) | Testes, ruff, README/`examples/`, review, PR. |

Nenhuma violação a justificar.

## Project Structure

### Documentation (this feature)

```text
specs/011-observabilidade-dlq/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── dlq-endpoints.md
└── tasks.md             # /speckit-tasks — NÃO criado aqui
```

### Source Code (repository root)

```text
shared/pedidos_shared/src/pedidos_shared/clients/sqs.py
    # + queue_url(name), message_count(url), peek(url, max), move(src_url, dst_url, message)

services/api-gateway/src/api_gateway/
├── domain/dlq.py                      # FILAS (9 nomes), identificar(body) e mascarar(body) — puros
├── handlers/resumo_dlqs.py            # GET  /dlqs
├── handlers/listar_mensagens_dlq.py   # GET  /dlqs/{fila}/mensagens
├── handlers/reprocessar_dlq.py        # POST /dlqs/{fila}/reprocessamento
├── schemas.py                         # + DlqResumo, MensagemDlq, ReprocessamentoRequest/Response
└── main.py                            # include_router x3

services/api-gateway/tests/
├── test_dlq_domain.py                 # identificar/mascarar (envelope, S3, linha)
└── test_dlqs.py                       # rotas (mock) + integração Ministack

shared/pedidos_shared/tests/clients/test_sqs.py   # métodos novos
README.md, services/api-gateway/README.md, docs/01-dominio-e-contratos.md, CLAUDE.md
```

**Structure Decision**: extensão do `api-gateway` seguindo handler + domain + deps; primitivas de
SQS em `shared`. A lista das 9 filas fica em `domain/dlq.py` (o bootstrap tem a sua própria
`QUEUE_NAMES`, módulo independente fora do workspace de runtime).

## Complexity Tracking

Sem violações.
