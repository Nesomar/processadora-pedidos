# Implementation Plan: Infraestrutura Local (Ministack)

**Branch**: `feature/002-infraestrutura-local` | **Date**: 2026-07-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-infraestrutura-local/spec.md`

## Summary

Fornecer `infra/docker-compose.yml` com dois serviços — Ministack e um serviço one-shot de
bootstrap disparado automaticamente via `depends_on: condition: service_healthy` — e
`infra/bootstrap/` (scripts Python idempotentes, boto3) que criam a fila de exemplo
`pedido-solicitado` com sua DLQ (`maxReceiveCount=3`), a tabela DynamoDB `orders` e o bucket S3
`orders-pdf`. Um `.env.example` na raiz do repo é a fonte única de nomes de recurso, lida tanto
pelo bootstrap quanto por `Settings` de qualquer serviço (feature 001). Um único
`docker-compose up` deixa o ambiente pronto, sem segundo comando manual (ver Clarifications em
spec.md e research.md).

## Technical Context

**Language/Version**: Python 3.12 (scripts de bootstrap); Docker Compose (YAML) para o Ministack

**Primary Dependencies**: boto3 (já mandatado pela constitution II); sem dependência nova
(research.md #1 rejeita `awslocal` CLI)

**Storage**: N/A — o bootstrap cria recursos em SQS/DynamoDB/S3 do Ministack; nenhum estado
próprio persistido (data-model.md)

**Testing**: pytest — teste de idempotência do bootstrap (rodar duas vezes, comparar estado)
rodando contra Ministack real; não há caminho de unit test isolado significativo (é
essencialmente um script de integração)

**Target Platform**: Docker (container Linux do Ministack) + máquina do desenvolvedor rodando
`docker compose` e `uv run` (qualquer SO com Docker + Python 3.12)

**Project Type**: ferramenta de infraestrutura (script + compose), não um serviço com `/health`

**Performance Goals**: ambiente sobe e fica saudável "em poucos segundos" (spec SC-001) —
sem orçamento de latência além disso

**Constraints**: local-first (constitution I.6); idempotência obrigatória (FR-005); nenhum nome
de recurso duplicado entre bootstrap e serviços (FR-006/FR-007, research.md #2)

**Scale/Scope**: ambiente de um único desenvolvedor local; não cobre ambiente compartilhado
multi-desenvolvedor nem produção

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution) | Status | Nota |
|---|---|---|
| I.4 Toda fila tem DLQ, `maxReceiveCount=3` | PASS | É o objeto central desta feature (data-model.md, contracts/) |
| I.5 Falha é dado | PASS | Drift de recurso existente vira log de aviso, não erro silencioso (research.md #3) |
| I.6 Local-first | PASS | É a implementação direta deste princípio |
| II Stack obrigatória (boto3, IaC local em `infra/bootstrap/`) | PASS | research.md #1 |
| III Contratos só em `shared/pedidos_shared` | N/A | Esta feature não define contrato de mensagem, só nomes de recurso de infra |
| IV Nenhum valor de infraestrutura hardcoded | PASS | `.env.example` como fonte única (research.md #2) |
| IV Cada serviço expõe `/health` | N/A | Não é um serviço; é tooling de infra |
| VIII Design de código (funções puras, sem God class) | PASS | Uma função "criar ou verificar" por tipo de recurso (SQS/DynamoDB/S3), sem classe acumulando responsabilidades |
| IX Definição de pronto (sobe via docker-compose sem config manual) | PASS (habilita) | Esta feature é o que torna IX possível pras demais features |

Nenhuma violação a justificar — Complexity Tracking fica vazio.

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
.env.example                    # fonte única de nomes de recurso (research.md #2)
infra/
├── docker-compose.yml           # serviço `ministack` + serviço one-shot `bootstrap`
│                                  # (depends_on: ministack: condition: service_healthy)
└── bootstrap/
    ├── pyproject.toml
    ├── main.py                   # composition root: lê env, chama create_or_verify_*
    ├── resources/
    │   ├── __init__.py
    │   ├── queues.py               # create_or_verify_queue(name, dlq_name) -> str (URL)
    │   ├── table.py                  # create_or_verify_table(name) -> None
    │   └── bucket.py                   # create_or_verify_bucket(name) -> None
    └── tests/
        └── test_idempotency.py          # roda bootstrap 2x contra Ministack, compara estado
```

**Structure Decision**: `infra/bootstrap/` como um mini-pacote Python próprio (não uma dependência
do workspace `pedidos_shared` — não há reuso de código entre os dois, são scripts de ciclo de vida
diferente). `resources/` separa por tipo de recurso (um arquivo por responsabilidade, seguindo
constitution VIII), cada um expondo uma função pura de "criar ou verificar" sem estado
compartilhado entre eles; `main.py` é o único lugar que orquestra a ordem de criação e lê `Settings`
de ambiente. O `docker-compose.yml` empacota `infra/bootstrap/` como imagem/serviço one-shot que
roda `python main.py` e sai (sem processo residente), disparado automaticamente após o
healthcheck do Ministack passar.

## Complexity Tracking

*Vazio — nenhuma violação de constitution a justificar.*
