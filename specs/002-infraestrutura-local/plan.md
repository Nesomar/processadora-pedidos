# Implementation Plan: Infraestrutura Local (Ministack)

**Branch**: `feature/002-infraestrutura-local` | **Date**: 2026-07-18 (revisado) | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-infraestrutura-local/spec.md`, realinhada a
`docs/01-dominio-e-contratos.md`.

## Summary

`infra/docker-compose.yml` com dois serviços — `ministack` e um one-shot `bootstrap`
(`depends_on: condition: service_healthy`) — e `infra/bootstrap/` (boto3, idempotente) criando: as
9 filas de §4 (cada uma + DLQ, `maxReceiveCount=3`), a tabela `orders` (com `GSI1`/`GSI2`), a
tabela `processed_messages` (com TTL), e o bucket `pedidos-bucket` (com notificação de evento
`uploads/*.txt` → `s3_notifications_queue`). `.env.example` na raiz usa as variáveis nativas do
Ministack (`AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) como
fonte única, lida também por `Settings` de `pedidos_shared`. Um `Makefile` expõe os atalhos de §8.

## Technical Context

**Language/Version**: Python 3.12 (bootstrap); Docker Compose (YAML)

**Primary Dependencies**: boto3; sem dependência nova (research.md #1)

**Storage**: N/A — bootstrap cria recursos no Ministack, sem estado próprio

**Testing**: pytest — idempotência (rodar 2x, comparar estado) e notificação de evento do bucket,
contra Ministack real

**Target Platform**: Docker (Ministack) + máquina do desenvolvedor (`docker compose`, `uv run`,
`make`)

**Project Type**: ferramenta de infraestrutura

**Performance Goals**: ambiente saudável "em poucos segundos" (SC-001)

**Constraints**: local-first; idempotência obrigatória (FR-006); nomes batendo com `Settings` de
`pedidos_shared` (FR-007); GSIs da tabela `orders` só podem ser definidos na criação (research.md #6)

**Scale/Scope**: ambiente de um único desenvolvedor local

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution) | Status | Nota |
|---|---|---|
| I.4 Toda fila tem DLQ, `maxReceiveCount=3` | PASS | 9 filas, todas com DLQ (data-model.md) |
| I.5 Falha é dado | PASS | Drift vira log de aviso (research.md #3, #5) |
| I.6 Local-first | PASS | Implementação direta do princípio |
| II Stack obrigatória | PASS | boto3, `infra/bootstrap/` (research.md #1) |
| III Contratos só em `shared/pedidos_shared` | N/A | Esta feature só cria infra, não contrato de mensagem |
| IV Nenhum valor hardcoded | PASS | `.env.example` fonte única (research.md #2) |
| IV `/health` por serviço | N/A | Não é serviço |
| VIII Design de código | PASS | Uma função por tipo de recurso (research.md #6), sem God class |
| IX Definição de pronto | PASS (habilita) | Esta feature torna IX possível pras demais |

Nenhuma violação a justificar.

## Project Structure

### Documentation (this feature)

```text
specs/002-infraestrutura-local/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── bootstrap-resources.md
└── tasks.md
```

### Source Code (repository root)

```text
.env.example
Makefile                          # up, down, bootstrap, test, e2e, seed-file (§8)
infra/
├── docker-compose.yml             # `ministack` + one-shot `bootstrap`
└── bootstrap/
    ├── pyproject.toml
    ├── main.py                     # composition root
    ├── resources/
    │   ├── __init__.py
    │   ├── queues.py                 # create_or_verify_queue(name, dlq_name) -> str, x9 no main.py
    │   ├── orders_table.py             # create_or_verify_orders_table() -> None (PK/SK + GSI1 + GSI2)
    │   ├── processed_messages_table.py   # create_or_verify_processed_messages_table() -> None (TTL)
    │   └── bucket.py                       # create_or_verify_bucket() + notificação de evento
    └── tests/
        ├── test_idempotency.py                # roda bootstrap 2x, compara estado
        └── test_bucket_notification.py          # notificação criada e idempotente
```

**Structure Decision**: `infra/bootstrap/` mini-pacote Python próprio. `resources/` separado por
tipo de recurso — `orders_table.py` e `processed_messages_table.py` são módulos distintos
(research.md #6, schemas incompatíveis demais pra uma função genérica). `bucket.py` inclui a lógica
de notificação de evento (mesma responsabilidade de "o bucket e sua config de evento", não vale
separar em módulo próprio só por isso). `docker-compose.yml` empacota `infra/bootstrap/` como
serviço one-shot.

## Complexity Tracking

*Vazio — nenhuma violação de constitution a justificar.*
