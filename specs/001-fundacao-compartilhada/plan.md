# Implementation Plan: Fundação Compartilhada (pedidos_shared)

**Branch**: `feature/001-fundacao-compartilhada` | **Date**: 2026-07-18 (revisado) | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-fundacao-compartilhada/spec.md`, realinhada a
`docs/01-dominio-e-contratos.md`.

## Summary

Criar o pacote `pedidos_shared`: `Order`/`OrderItem`/`MessageEnvelope` (Pydantic v2), o enum
`OrderStatus` (9 estados) com `is_valid_transition`, `Settings` de infraestrutura (env vars
nativas do Ministack: `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`), clientes finos SQS/DynamoDB/S3, `mark_message_processed` (idempotência
via tabela `processed_messages`), logger JSON, `mask_document` e um parser dedicado ao layout
posicional fixo de `docs/01-dominio-e-contratos.md` §6. Todos os nomes, estados e formatos vêm
literalmente desse documento — nenhuma invenção nesta feature.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Pydantic v2, boto3 (constitution II); sem dependência nova — logging via
stdlib (research.md #1)

**Storage**: N/A diretamente — cliente de DynamoDB (`orders`, `processed_messages`) e S3
(`pedidos-bucket`), não persiste estado próprio

**Testing**: pytest; testes de idempotência e clientes rodam contra Ministack (integração)

**Target Platform**: biblioteca Python consumida em containers Linux (ECS) e Lambda

**Project Type**: biblioteca compartilhada (single project) via workspace `uv`

**Performance Goals**: N/A — funções puras + wrappers síncronos, sem orçamento de latência próprio

**Constraints**: local-first (Ministack); nenhuma dependência nova fora da stack; nenhum valor de
infraestrutura hardcoded; nomes/estados/layout devem bater exatamente com
`docs/01-dominio-e-contratos.md`

**Scale/Scope**: consumida por 6 serviços; volume de chamadas dominado pelo volume de pedidos

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution) | Status | Nota |
|---|---|---|
| I.1 Event-driven, sem HTTP entre serviços | PASS | Só clientes SQS/DynamoDB/S3 |
| I.2 Máquina de estados explícita | PASS | `OrderStatus` + `is_valid_transition()` (data-model.md) |
| I.3 Idempotência obrigatória | PASS | `mark_message_processed` implementa o mecanismo (research.md #4) |
| I.4 Toda fila tem DLQ | N/A nesta feature | Criação de fila é `002-infraestrutura-local` |
| I.5 Falha é dado | PASS | `Order.status_reason`; exceções de domínio no parser |
| I.6 Local-first | PASS | `Settings.aws_endpoint_url` único ponto de configuração |
| II Stack obrigatória | PASS | Só Pydantic v2 + boto3 |
| III Contratos só em `shared/pedidos_shared` | PASS (é o objeto desta feature) | — |
| IV Sem infra hardcoded / logs JSON / type hints | PASS | `/health` N/A (biblioteca, não serviço) |
| VIII Design de código | PASS | Funções puras (`is_valid_transition`, `mask_document`,
  `mark_message_processed`, parser); DI explícita nos clientes |

Nenhuma violação a justificar.

## Project Structure

### Documentation (this feature)

```text
specs/001-fundacao-compartilhada/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── pedidos_shared-api.md
└── tasks.md
```

### Source Code (repository root)

```text
shared/
└── pedidos_shared/
    ├── pyproject.toml
    ├── src/
    │   └── pedidos_shared/
    │       ├── __init__.py
    │       ├── models.py         # Order, OrderItem, MessageEnvelope
    │       ├── status.py          # OrderStatus, is_valid_transition
    │       ├── settings.py         # Settings (Pydantic)
    │       ├── idempotency.py       # mark_message_processed
    │       ├── masking.py            # mask_document
    │       ├── logging.py             # get_logger, JsonFormatter
    │       ├── file_layout.py          # parse_file + exceções de domínio
    │       └── clients/
    │           ├── __init__.py
    │           ├── sqs.py
    │           ├── dynamodb.py
    │           └── s3.py
    └── tests/
        ├── fixtures/
        │   └── exemplo.txt          # arquivo posicional de exemplo (§6.9)
        ├── test_models.py
        ├── test_status.py
        ├── test_settings.py
        ├── test_idempotency.py
        ├── test_masking.py
        ├── test_logging.py
        ├── test_file_layout.py
        └── clients/
            └── test_sqs.py          # contra Ministack (integração)
```

**Structure Decision**: biblioteca única em `shared/pedidos_shared/`, layout `src/`. `status.py`,
`masking.py`, `file_layout.py` e `idempotency.py` (lógica condicional pura antes da chamada boto3)
equivalem ao `domain/` da constitution VIII; `clients/` equivale a `adapters/`. Sem
`handlers/`/`domain/`/`adapters/` nomeados literalmente porque essa subdivisão é para *serviços*
com handlers de fila — esta é uma biblioteca, não um serviço.

## Complexity Tracking

*Vazio — nenhuma violação de constitution a justificar.*
