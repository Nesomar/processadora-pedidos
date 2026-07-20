# Implementation Plan: API Gateway

**Branch**: `feature/003-api-gateway` | **Date**: 2026-07-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-api-gateway/spec.md`.

## Summary

Serviço FastAPI (`services/api-gateway/`) que expõe a única porta HTTP de entrada do sistema:
criar/editar/cancelar pedido (publicando em `solicitar_pedido_queue`/`editar_pedido_queue`/
`cancelar_pedido_queue` via `pedidos_shared`) e consultar/listar pedidos (lendo a tabela `orders`
via `pedidos_shared.DynamoDbClient`, com `customer_document` sempre mascarado). Nunca escreve em
`orders` — só o Order Processor persiste. Reaproveita `is_valid_transition` de `pedidos_shared`
pra decidir elegibilidade de edição/cancelamento, sem reimplementar a tabela de estados. O mesmo
endpoint de criação atende tanto clientes HTTP externos quanto a chamada interna do Lambda Line
Processor no fluxo BATCH — exceção explícita e documentada a constitution I.1 (ver Constitution
Check e Complexity Tracking).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, Uvicorn (constitution II); Pydantic v2 e boto3 só via
`pedidos_shared` (feature `001-fundacao-compartilhada`) — nenhuma dependência nova

**Storage**: DynamoDB `orders` (feature `002-infraestrutura-local`) — **somente leitura** nesta
feature (`get_item` por `order_id`, `query` em `GSI1` por `customer_id`); nenhuma escrita

**Testing**: pytest + `starlette.testclient`/`httpx` (unitário, clients de `pedidos_shared`
mockados via injeção de dependência do FastAPI) + testes de integração contra Ministack real
(mesma estratégia de 001/002, pula automaticamente se Ministack não estiver acessível)

**Target Platform**: container Docker (Linux), local via Ministack (`002-infraestrutura-local`)

**Project Type**: serviço web (um serviço do monorepo, `services/api-gateway/`)

**Performance Goals**: SC-001 — resposta de aceite de pedido em menos de 1s, sem esperar
processamento completo (constitution I.2, non-blocking)

**Constraints**: nenhuma escrita direta em `orders` (contrato regra 3 de `pedidos_shared`);
nenhum valor de infraestrutura hardcoded (`Settings` de `pedidos_shared`); sem autenticação/
autorização (spec.md Assumptions); endpoint de criação compartilhado entre HTTP e o fluxo BATCH
(exceção documentada a constitution I.1)

**Scale/Scope**: consumido por clientes HTTP externos (volume não especificado) e pelo Lambda
Line Processor (uma chamada por linha de arquivo batch — meta de volume/concorrência
explicitamente não definida nesta feature, ver spec.md Clarifications; tratada como fora de
escopo até um sinal real de necessidade)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution) | Status | Nota |
|---|---|---|
| I.1 Event-driven, sem HTTP entre serviços internos | **EXCEÇÃO DOCUMENTADA** | O mesmo endpoint de criação de pedido aceita a chamada interna do Lambda Line Processor (fluxo BATCH), conforme `docs/01-dominio-e-contratos.md` §1 — decisão explícita do usuário na clarificação de spec.md, priorizando o domínio sobre a leitura restritiva desta regra. Ver Complexity Tracking. |
| I.2 Máquina de estados explícita | PASS | API Gateway nunca escreve em `orders`; toda transição real acontece no Order Processor ao consumir a mensagem (FR-004). Elegibilidade de edição/cancelamento é checada com `is_valid_transition`, não reimplementada. |
| I.3 Idempotência obrigatória | N/A nesta feature | API Gateway não consome fila — só publica. Idempotência de consumo é responsabilidade do Order Processor (`mark_message_processed`). |
| I.4 Toda fila tem DLQ | N/A nesta feature | Filas já criadas com DLQ em `002-infraestrutura-local`; esta feature só publica nelas. |
| I.5 Falha é dado | PASS | Erros de validação (400), conflito de estado (409) e "não encontrado" (404) são respostas HTTP claras, não exceções silenciosas. |
| I.6 Local-first | PASS | Usa `pedidos_shared.Settings`/clients, mesmo Ministack de `002-infraestrutura-local`. |
| II Stack obrigatória | PASS | FastAPI + Uvicorn; Pydantic v2/boto3 só via `pedidos_shared`. |
| III Contratos só em `shared/pedidos_shared` | PASS | Reaproveita `Order`/`OrderItem`/`MessageEnvelope`/`OrderStatus`/`is_valid_transition`/`mask_document`; nenhum redefinido localmente. |
| IV Sem infra hardcoded / logs JSON / type hints / `/health` | PASS | `Settings` de `pedidos_shared`; `get_logger` de `pedidos_shared`; `GET /health` na mesma app FastAPI (não precisa de thread separada — este serviço já é HTTP nativo). |
| VIII Design de código | PASS | `handlers/` (um por operação), `domain/` (validação de payload + elegibilidade de transição, puro), `adapters/` (leitura de `orders`), `config.py`, `main.py` composition root. |
| IX Definição de pronto | PASS (guia a implementação) | Branch `feature/003-api-gateway`, testes unitários + integração, `docker-compose` do serviço, `ruff`, code review, README, PR. |

**Violação a justificar**: I.1 (endpoint HTTP compartilhado com o fluxo BATCH) — ver Complexity
Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/003-api-gateway/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api-gateway-http.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
services/api-gateway/
├── pyproject.toml
├── src/api_gateway/
│   ├── __init__.py
│   ├── main.py                       # composition root: monta FastAPI app, injeta clients, GET /health
│   ├── config.py                     # Settings de pedidos_shared + valida filas que este serviço usa
│   ├── handlers/
│   │   ├── solicitar_pedido.py       # POST /pedidos (US1 + US2)
│   │   ├── editar_pedido.py          # PUT /pedidos/{order_id} (US3)
│   │   ├── cancelar_pedido.py        # POST /pedidos/{order_id}/cancelamento (US4)
│   │   ├── consultar_pedido.py       # GET /pedidos/{order_id} (US5)
│   │   └── listar_pedidos.py         # GET /pedidos?customerId=X (US6)
│   ├── domain/
│   │   ├── validar_payload.py        # regras de FR-002, puro, sem I/O
│   │   └── elegibilidade_transicao.py  # wraps is_valid_transition p/ decidir edição/cancelamento
│   ├── adapters/
│   │   └── orders_repository.py      # leitura de orders (get_by_id, query_by_customer) via DynamoDbClient
│   └── schemas.py                    # Pydantic: request/response da API (não confundir com Order/OrderItem)
└── tests/
    ├── conftest.py                   # fixtures: TestClient com clients mockados; skip sem Ministack
    ├── test_solicitar_pedido.py
    ├── test_editar_pedido.py
    ├── test_cancelar_pedido.py
    ├── test_consultar_pedido.py
    ├── test_listar_pedidos.py
    ├── test_validar_payload.py
    └── test_elegibilidade_transicao.py
```

**Structure Decision**: serviço único em `services/api-gateway/`, seguindo a subdivisão de
`handlers/`/`domain/`/`adapters/`/`config.py`/`main.py` da constitution VIII. `domain/` não
importa boto3/FastAPI — só `validar_payload` (regras de FR-002) e `elegibilidade_transicao`
(wrapper fino sobre `is_valid_transition` de `pedidos_shared`). `adapters/orders_repository.py` é
o único ponto de leitura em `orders`, mantendo a regra de "nenhuma escrita fora do Order
Processor" trivialmente verificável (o adapter não expõe nenhum método de escrita).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| I.1 — endpoint HTTP de criação de pedido aceita chamada interna do Lambda Line Processor (fluxo BATCH), além de clientes externos | `docs/01-dominio-e-contratos.md` §1 define literalmente esse fluxo: "cada linha vira uma chamada ao mesmo API Gateway". É a fonte de verdade de domínio do projeto, e o usuário resolveu explicitamente a favor dela durante `/speckit-clarify` de spec.md, quando confrontado com o conflito contra esta regra. | Alternativa mais simples seria o Lambda Line Processor publicar direto em `solicitar_pedido_queue` via SQS, sem HTTP — isso obedeceria I.1 à risca, mas diverge do diagrama e do texto de §1, que descrevem explicitamente uma chamada ao API Gateway. Rejeitada porque o usuário, ao ser confrontado com o trade-off, priorizou aderência ao documento de domínio sobre a leitura estrita desta regra da constitution. |

