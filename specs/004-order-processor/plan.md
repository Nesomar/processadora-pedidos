# Implementation Plan: Order Processor

**Branch**: `feature/004-order-processor` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-order-processor/spec.md`.

## Summary

Worker Python (`services/order-processor/`) sem porta HTTP de negócio — consome 5 filas
(`solicitar_pedido_queue`, `editar_pedido_queue`, `cancelar_pedido_queue`,
`validar_pedido_response_queue`, `pdf_response_queue`) e publica em 2
(`validar_pedido_queue`, `pdf_request_queue`), todas via `pedidos_shared`. É o único
componente do sistema que escreve na tabela `orders` (contrato regra 3 de
`pedidos_shared-api.md`). Toda mutação de status passa por `is_valid_transition`; toda
mensagem consumida passa por `mark_message_processed` antes de qualquer efeito colateral;
toda escrita em `orders` usa `ConditionExpression` sobre `version` com até 3 tentativas em
caso de conflito de concorrência (`docs/01-dominio-e-contratos.md` §3).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: boto3 e Pydantic v2 só via `pedidos_shared` (feature
`001-fundacao-compartilhada`) — nenhuma dependência nova; consumo de fila via `threading` da
stdlib (um thread por fila, ver research.md #1)

**Storage**: DynamoDB `orders` (feature `002-infraestrutura-local`) — **único escritor** do
sistema nesta tabela; `processed_messages` (idempotência, via `mark_message_processed`)

**Testing**: pytest + testes de integração contra Ministack real (mesma estratégia de
001/002/003, pula automaticamente se Ministack não estiver acessível)

**Target Platform**: container Docker (Linux), local via Ministack

**Project Type**: worker assíncrono (um serviço do monorepo, `services/order-processor/`, sem
interface HTTP de negócio)

**Performance Goals**: SC-001/002/003 exigem progresso automático "sem intervenção manual" — sem
meta de latência numérica nesta spec; cada mensagem é processada assim que consumida, sem espera
artificial

**Constraints**: nenhuma escrita em `orders` fora deste serviço; toda transição via
`is_valid_transition`; idempotência obrigatória em toda mensagem consumida (constitution I.3);
até 3 tentativas em conflito de concorrência otimista (`docs/01-dominio-e-contratos.md` §3);
nunca bloqueia esperando resposta síncrona de outro serviço (constitution I.2)

**Scale/Scope**: consome 5 filas, publica em 2 — volume dominado pelo volume de pedidos do
sistema, sem meta própria definida nesta feature

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution) | Status | Nota |
|---|---|---|
| I.1 Event-driven, sem HTTP entre serviços | PASS | Worker puro, sem endpoint de negócio; só a thread de `/health` expõe HTTP (IV). |
| I.2 Máquina de estados explícita | PASS | Toda transição passa por `is_valid_transition` de `pedidos_shared`; nenhuma tabela própria. |
| I.3 Idempotência obrigatória | PASS | `mark_message_processed` chamado antes de qualquer efeito colateral, em toda mensagem de toda fila consumida. |
| I.4 Toda fila tem DLQ | N/A nesta feature | Filas e DLQs já criadas em `002-infraestrutura-local`; este serviço só consome/publica. |
| I.5 Falha é dado | PASS | `status_reason` armazenado em rejeição/falha; erro técnico (mensagem malformada, `order_id` inexistente) vira log estruturado, mensagem não é confirmada (redrive nativo do SQS). |
| I.6 Local-first | PASS | Usa `pedidos_shared.Settings`/clients, mesmo Ministack das features anteriores. |
| II Stack obrigatória | PASS | boto3/Pydantic v2 só via `pedidos_shared`; `threading` é stdlib, não é dependência nova. |
| III Contratos só em `shared/pedidos_shared` | PASS | Reaproveita `Order`/`OrderItem`/`MessageEnvelope`/`OrderStatus`/`is_valid_transition`/`mark_message_processed`; nenhum redefinido. |
| IV Sem infra hardcoded / logs JSON / type hints / `/health` | PASS | `Settings`/`get_logger` de `pedidos_shared`; thread HTTP simples na porta 8080 servindo `/health` (constitution IV, "mesmo os workers"). |
| VIII Design de código | PASS | `handlers/` (um por fila consumida), `domain/` (transições e montagem de payload, puro), `adapters/` (`orders_repository`, factory de clients), `config.py`, `main.py` (composition root: sobe as 5 threads de consumo + a thread de health). |
| IX Definição de pronto | PASS (guia a implementação) | Branch `feature/004-order-processor`, testes unitários + integração, `docker-compose`, `ruff`, code review, README, PR. |

Nenhuma violação a justificar.

## Project Structure

### Documentation (this feature)

```text
specs/004-order-processor/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── order-processor-messages.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
services/order-processor/
├── pyproject.toml
├── src/order_processor/
│   ├── __init__.py
│   ├── main.py                          # composition root: 5 threads de consumo + thread /health
│   ├── config.py                        # Settings de pedidos_shared + valida filas/tabela usadas
│   ├── handlers/
│   │   ├── solicitar_pedido.py          # consome solicitar_pedido_queue (US1)
│   │   ├── editar_pedido.py             # consome editar_pedido_queue (US4)
│   │   ├── cancelar_pedido.py           # consome cancelar_pedido_queue (US5)
│   │   ├── validar_pedido_response.py   # consome validar_pedido_response_queue (US2)
│   │   └── pdf_response.py              # consome pdf_response_queue (US3)
│   ├── domain/
│   │   ├── transicoes.py                # wrappers finos sobre is_valid_transition p/ cada operação
│   │   └── mensagens.py                 # monta payload de validar_pedido_queue/pdf_request_queue
│   └── adapters/
│       ├── orders_repository.py         # get_by_id, criar, atualizar-com-versão (único escritor)
│       └── worker_loop.py               # loop de consumo genérico (idempotência + ack) reaproveitado pelos 5 handlers
└── tests/
    ├── test_solicitar_pedido.py
    ├── test_editar_pedido.py
    ├── test_cancelar_pedido.py
    ├── test_validar_pedido_response.py
    ├── test_pdf_response.py
    ├── test_transicoes.py
    ├── test_orders_repository.py
    └── test_idempotencia.py
```

**Structure Decision**: serviço único em `services/order-processor/`, mesma subdivisão
`handlers/`/`domain/`/`adapters/`/`config.py`/`main.py` das demais features de serviço.
`adapters/worker_loop.py` centraliza o padrão comum a todo handler (checar idempotência, invocar
a lógica do handler, confirmar/não-confirmar a mensagem) — sem isso, os 5 handlers duplicariam o
mesmo esqueleto de consumo. `domain/` não importa boto3 nem `pedidos_shared.clients` — só
`is_valid_transition`/`OrderStatus` (dados puros de domínio, não infraestrutura).

## Complexity Tracking

*Vazio — nenhuma violação de constitution a justificar.*
