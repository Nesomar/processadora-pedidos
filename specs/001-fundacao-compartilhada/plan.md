# Implementation Plan: Fundação Compartilhada (pedidos_shared)

**Branch**: `feature/001-fundacao-compartilhada` | **Date**: 2026-07-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-fundacao-compartilhada/spec.md`

## Summary

Criar o pacote Python `pedidos_shared`, ponto único de verdade para: contratos de mensagem
(Pydantic v2), o enum `StatusPedido` e suas transições válidas, `Settings` de infraestrutura
lido de variáveis de ambiente, clientes finos SQS/DynamoDB/S3 (boto3, `endpoint_url` do
Ministack), um logger JSON estruturado com `orderId`/`correlationId`, mascaramento de documento
do cliente e um parser de arquivo posicional genérico. Nenhum outro serviço pode redefinir esses
contratos localmente (constitution III). Abordagem técnica: funções puras em `domain/`-equivalente
sem I/O, wrappers finos e síncronos sobre boto3, `logging` da stdlib com formatter JSON custom —
sem dependências novas além das já obrigatórias pela constitution (ver research.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Pydantic v2, boto3 (todos já mandatados pela constitution seção II); sem
dependências novas — logging via stdlib (ver research.md #1)

**Storage**: N/A diretamente (o pacote é cliente de DynamoDB/S3/SQS, não persiste estado próprio)

**Testing**: pytest, pytest-asyncio (não usado nesta feature — sem I/O concorrente real), moto ou
Ministack para os testes de integração dos clientes

**Target Platform**: biblioteca Python consumida em containers Linux (ECS) e Lambda; desenvolvida
localmente em qualquer SO com Python 3.12 + uv

**Project Type**: biblioteca compartilhada (single project) dentro do monorepo — consumida via
workspace `uv` por todos os demais serviços

**Performance Goals**: N/A — chamadas em processo (funções puras, wrappers síncronos), sem
orçamento de latência próprio; latência de I/O é dominada pelo Ministack/SQS/DynamoDB, fora do
escopo desta biblioteca

**Constraints**: local-first (Ministack, constitution I.6); nenhuma dependência nova fora da stack
da constitution seção II (YAGNI); nenhum valor de infraestrutura hardcoded (constitution IV)

**Scale/Scope**: consumida por 6 serviços (api-gateway, order-processor, order-validator,
pdf-generator, file-consumer, lambda-line-processor); volume de chamadas dominado pelo volume de
pedidos do sistema, não é um gargalo isolado

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution) | Status | Nota |
|---|---|---|
| I.1 Event-driven, sem HTTP entre serviços | PASS | Pacote não expõe HTTP; clientes SQS/DynamoDB/S3 apenas |
| I.2 Máquina de estados explícita | PASS | `StatusPedido` + `is_valid_transition()` são a única fonte de verdade (data-model.md) |
| I.3 Idempotência obrigatória | PASS (habilita) | Pacote fornece o enum/estado que consumidores usam em `ConditionExpression`; a idempotência do consumo em si é responsabilidade de cada serviço consumidor, fora do escopo desta feature |
| I.4 Toda fila tem DLQ | N/A nesta feature | Criação de fila/DLQ é `infra/bootstrap/`, não este pacote |
| I.5 Falha é dado | PASS | `Pedido.status_reason` modelado; exceções de domínio (`LinhaCurtaError`) em vez de genéricas |
| I.6 Local-first | PASS | `Settings.ministack_endpoint_url` único ponto de configuração de endpoint |
| II Stack obrigatória | PASS | Só usa Pydantic v2 + boto3, já mandatados; nenhuma lib nova |
| III Contratos só em `shared/pedidos_shared` | PASS (é o objeto desta feature) | — |
| IV Sem infra hardcoded / logs JSON / type hints / `/health` | PASS exceto `/health` | `/health` é responsabilidade de cada serviço (thread HTTP própria), não da biblioteca — N/A aqui |
| VIII Design de código (funções puras, DI explícita, sem God class) | PASS | `is_valid_transition`, `mask_document`, `parse_fixed_width` são funções puras; clientes recebem `Settings` por construtor |

Nenhuma violação a justificar — Complexity Tracking fica vazio.

## Project Structure

### Documentation (this feature)

```text
specs/001-fundacao-compartilhada/
├── plan.md              # Este arquivo
├── research.md           # Fase 0
├── data-model.md          # Fase 1
├── quickstart.md           # Fase 1
├── contracts/                # Fase 1
│   └── pedidos_shared-api.md
└── tasks.md                   # Fase 2 (/speckit-tasks, ainda não gerado)
```

### Source Code (repository root)

```text
shared/
└── pedidos_shared/
    ├── pyproject.toml
    ├── src/
    │   └── pedidos_shared/
    │       ├── __init__.py
    │       ├── models.py        # Pedido, ItemPedido, contratos de mensagem (Pydantic)
    │       ├── status.py         # StatusPedido, is_valid_transition
    │       ├── settings.py        # Settings (Pydantic)
    │       ├── masking.py          # mask_document
    │       ├── logging.py           # get_logger, JsonFormatter
    │       ├── parsing.py            # FieldSpec, parse_fixed_width, LinhaCurtaError
    │       └── clients/
    │           ├── __init__.py
    │           ├── sqs.py
    │           ├── dynamodb.py
    │           └── s3.py
    └── tests/
        ├── test_models.py
        ├── test_status.py
        ├── test_settings.py
        ├── test_masking.py
        ├── test_logging.py
        ├── test_parsing.py
        └── clients/
            └── test_sqs.py       # contra Ministack (integração)
```

**Structure Decision**: biblioteca única em `shared/pedidos_shared/`, layout `src/` conforme a
estrutura do monorepo definida na constitution seção III/VIII. Sem `handlers/`, `domain/` ou
`adapters/` separados — essa subdivisão de seção VIII é para *serviços* (que têm handlers de
fila); aqui `status.py`, `masking.py` e `parsing.py` já são o equivalente a `domain/` (funções
puras, sem I/O) e `clients/` é o equivalente a `adapters/` (integração externa via boto3),
mantendo a mesma separação de responsabilidades da constitution sem repetir os nomes de pasta
genéricos de um serviço que não existe aqui.

## Complexity Tracking

*Vazio — nenhuma violação de constitution a justificar.*
