---

description: "Task list for API Gateway"
---

# Tasks: API Gateway

**Input**: Design documents from `/specs/003-api-gateway/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/api-gateway-http.md, research.md

**Tests**: Incluídas — constitution IX exige testes unitários + ao menos um teste de integração
contra o Ministack.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

```
services/api-gateway/
├── pyproject.toml
├── src/api_gateway/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── handlers/{solicitar_pedido,editar_pedido,cancelar_pedido,consultar_pedido,listar_pedidos}.py
│   ├── domain/{validar_payload,elegibilidade_transicao}.py
│   └── adapters/orders_repository.py
└── tests/{test_health,test_validar_payload,test_solicitar_pedido,test_elegibilidade_transicao,
          test_editar_pedido,test_cancelar_pedido,test_consultar_pedido,test_listar_pedidos}.py
```

---

## Phase 1: Setup

- [X] T001 Criar esqueleto em `services/api-gateway/` (`pyproject.toml`, `src/api_gateway/`, `src/api_gateway/{handlers,domain,adapters}/`, `tests/`) conforme plan.md
- [X] T002 [P] Adicionar `services/api-gateway` ao workspace `uv` na raiz (`pyproject.toml`)
- [X] T003 [P] Configurar `ruff` em `services/api-gateway/pyproject.toml`

**Checkpoint**: `uv sync --package api-gateway` roda sem erro

---

## Phase 2: Foundational

- [X] T004 Implementar `config.py` (`Settings` de `pedidos_shared`; valida que `solicitar_pedido_queue_url`, `editar_pedido_queue_url`, `cancelar_pedido_queue_url` e `orders_table_name` estão setados) em `services/api-gateway/src/api_gateway/config.py` (depende de T001)
- [X] T005 Implementar `main.py` (FastAPI app, composition root, `GET /health`) em `services/api-gateway/src/api_gateway/main.py` (depende de T004)
- [X] T006 [P] Teste de `GET /health` (200, `{"status":"ok"}`) em `services/api-gateway/tests/test_health.py` (depende de T005)

**Checkpoint**: `uv run --package api-gateway uvicorn api_gateway.main:app` sobe e `/health` responde

---

## Phase 3: User Story 1 - Cliente solicita um novo pedido (Priority: P1) 🎯 MVP

**Independent Test**: enviar payload válido pra `POST /pedidos`, confirmar `202` com `order_id`/
`correlation_id` e mensagem em `solicitar_pedido_queue`.

### Tests

- [X] T007 [P] [US1] Teste de `validar_payload` (aceita payload válido; rejeita `customer_id` >20 chars ou não-alfanumérico, `customer_document` não-numérico, 0 ou >50 itens, `quantity` ≤0) em `services/api-gateway/tests/test_validar_payload.py`
- [X] T008 [P] [US1] Teste de `POST /pedidos` com payload válido (202, `order_id`/`correlation_id`, `SqsClient` mockado via DI) em `services/api-gateway/tests/test_solicitar_pedido.py`
- [X] T009 [P] [US1] Teste de falha técnica ao publicar (`SqsClient.send` mockado levanta exceção) — resposta 5xx, nenhum `order_id` retornado como aceito (spec.md Edge Cases) em `services/api-gateway/tests/test_solicitar_pedido.py`
- [X] T010 [US1] Teste de integração: `POST /pedidos` publica `MessageEnvelope` real em `solicitar_pedido_queue` contra Ministack, respondendo em menos de 1s (SC-001) em `services/api-gateway/tests/test_solicitar_pedido.py` (depende de T008)

### Implementation

- [X] T011 [P] [US1] Implementar `schemas.py`: `ItemRequest`, `SolicitarPedidoRequest`, `AceitePedidoResponse`, `ErrorResponse` em `services/api-gateway/src/api_gateway/schemas.py`
- [X] T012 [P] [US1] Implementar `domain/validar_payload.py` (regras de FR-002, puro) em `services/api-gateway/src/api_gateway/domain/validar_payload.py`
- [X] T013 [US1] Implementar `handlers/solicitar_pedido.py` (gera `order_id`/`correlation_id`, valida payload, publica em `solicitar_pedido_queue`, propaga falha de publicação como erro técnico) em `services/api-gateway/src/api_gateway/handlers/solicitar_pedido.py` (depende de T011, T012)
- [X] T014 [US1] Registrar `POST /pedidos` em `main.py` (depende de T013)

**Checkpoint**: MVP pronto e testável

---

## Phase 4: User Story 2 - Sistema aceita pedidos do processamento de arquivo batch (Priority: P1)

**Depende de**: US1 completa (mesmo endpoint/handler, reaproveitado).

### Tests

- [X] T015 [P] [US2] Teste de `POST /pedidos` com `channel="BATCH"` + `source_file`/`source_line` preenchidos — mesma validação e formato de mensagem que o cenário HTTP de T008 em `services/api-gateway/tests/test_solicitar_pedido.py`

### Implementation

- [X] T016 [US2] Garantir que `handlers/solicitar_pedido.py` propaga `channel`/`source_file`/`source_line` corretamente ao `MessageEnvelope` publicado (depende de T013)

**Checkpoint**: US1+US2 independentes e testáveis

---

## Phase 5: User Story 3 - Cliente edita um pedido existente (Priority: P2)

### Tests

- [X] T017 [P] [US3] Teste de `elegibilidade_transicao` (aceita `RECEIVED`/`VALIDATED`/`REJECTED` como editáveis; rejeita os demais estados terminais) em `services/api-gateway/tests/test_elegibilidade_transicao.py`
- [X] T018 [P] [US3] Teste de `PUT /pedidos/{order_id}` (202 válido, 404 inexistente, 409 estado inválido) em `services/api-gateway/tests/test_editar_pedido.py`
- [X] T019 [P] [US3] Teste de falha técnica ao publicar edição (`SqsClient.send` mockado levanta exceção) — resposta 5xx, sem alterar o registro em `orders` em `services/api-gateway/tests/test_editar_pedido.py`

### Implementation

- [X] T020 [P] [US3] Implementar `domain/elegibilidade_transicao.py` (`pode_editar`/`pode_cancelar` via `is_valid_transition` de `pedidos_shared`) em `services/api-gateway/src/api_gateway/domain/elegibilidade_transicao.py`
- [X] T021 [P] [US3] Implementar `adapters/orders_repository.py`: `get_by_id(order_id)` em `services/api-gateway/src/api_gateway/adapters/orders_repository.py`
- [X] T022 [US3] Adicionar `EditarPedidoRequest` em `schemas.py` (depende de T011)
- [X] T023 [US3] Implementar `handlers/editar_pedido.py` (busca pedido, checa elegibilidade, publica em `editar_pedido_queue`, propaga falha de publicação como erro técnico) em `services/api-gateway/src/api_gateway/handlers/editar_pedido.py` (depende de T020, T021, T022)
- [X] T024 [US3] Registrar `PUT /pedidos/{order_id}` em `main.py` (depende de T023)

**Checkpoint**: US1–US3 independentes e testáveis

---

## Phase 6: User Story 4 - Cliente cancela um pedido existente (Priority: P2)

### Tests

- [X] T025 [P] [US4] Teste de `POST /pedidos/{order_id}/cancelamento` (202 com `reason`, 400 sem `reason`, 404, 409) em `services/api-gateway/tests/test_cancelar_pedido.py`
- [X] T026 [P] [US4] Teste de falha técnica ao publicar cancelamento (`SqsClient.send` mockado levanta exceção) — resposta 5xx, sem alterar o registro em `orders` em `services/api-gateway/tests/test_cancelar_pedido.py`

### Implementation

- [X] T027 [P] [US4] Adicionar `CancelarPedidoRequest` em `schemas.py` (depende de T011)
- [X] T028 [US4] Implementar `handlers/cancelar_pedido.py` (busca pedido, checa elegibilidade, publica em `cancelar_pedido_queue` com `reason`, propaga falha de publicação como erro técnico) em `services/api-gateway/src/api_gateway/handlers/cancelar_pedido.py` (depende de T020, T021, T027)
- [X] T029 [US4] Registrar `POST /pedidos/{order_id}/cancelamento` em `main.py` (depende de T028)

**Checkpoint**: US1–US4 independentes e testáveis

---

## Phase 7: User Story 5 - Cliente consulta um pedido específico (Priority: P3)

### Tests

- [X] T030 [P] [US5] Teste de `GET /pedidos/{order_id}` (200 com `customer_document` mascarado, 404 inexistente) em `services/api-gateway/tests/test_consultar_pedido.py`

### Implementation

- [X] T031 [P] [US5] Adicionar `PedidoResponse` em `schemas.py` (aplica `mask_document` de `pedidos_shared`) em `services/api-gateway/src/api_gateway/schemas.py`
- [X] T032 [US5] Implementar `handlers/consultar_pedido.py` (usa `orders_repository.get_by_id`) em `services/api-gateway/src/api_gateway/handlers/consultar_pedido.py` (depende de T021, T031)
- [X] T033 [US5] Registrar `GET /pedidos/{order_id}` em `main.py` (depende de T032)

**Checkpoint**: US1–US5 independentes e testáveis

---

## Phase 8: User Story 6 - Cliente lista os próprios pedidos (Priority: P3)

### Tests

- [X] T034 [P] [US6] Teste de `GET /pedidos?customerId=X` (lista ordenada mais recente primeiro; lista vazia sem erro quando não há pedidos) em `services/api-gateway/tests/test_listar_pedidos.py`

### Implementation

- [X] T035 [US6] Implementar `query_by_customer` em `adapters/orders_repository.py` (`GSI1`, `ScanIndexForward=False`) em `services/api-gateway/src/api_gateway/adapters/orders_repository.py` (depende de T021)
- [X] T036 [P] [US6] Adicionar `ListaPedidosResponse` em `schemas.py` (depende de T031)
- [X] T037 [US6] Implementar `handlers/listar_pedidos.py` em `services/api-gateway/src/api_gateway/handlers/listar_pedidos.py` (depende de T035, T036)
- [X] T038 [US6] Registrar `GET /pedidos` em `main.py` (depende de T037)

**Checkpoint**: todas as 6 user stories independentes e testáveis

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T039 [P] Escrever `services/api-gateway/README.md` documentando rotas, variáveis de ambiente e comando de subida
- [X] T040 Rodar `ruff check`/`ruff format --check` em `services/api-gateway/`
- [X] T041 Adicionar o serviço `api-gateway` a `infra/docker-compose.yml` (build via `uv`, expõe porta, `depends_on` do `bootstrap` concluído)
- [X] T042 Rodar os cenários de `quickstart.md` ponta a ponta contra o Ministack local
- [X] T043 [P] Executar o code review da constitution seção VII antes de abrir o PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup/Foundational**: bloqueiam tudo
- **US1**: núcleo real da feature — MVP
- **US2**: depende de US1 completa (reaproveita o mesmo handler)
- **US3, US4**: independentes entre si; ambas dependem só do Foundational (usam `elegibilidade_transicao`/`orders_repository` compartilhados, criados na primeira que rodar)
- **US5**: depende de `orders_repository.get_by_id` (criado em US3) — reaproveita, não reimplementa
- **US6**: depende de US5 (reaproveita `PedidoResponse` de `schemas.py`) e estende `orders_repository`
- **Polish**: depende de todas as stories desejadas completas

### Parallel Opportunities

- T002/T003 (Setup) em paralelo
- Depois do Foundational: testes de cada story (`[P]`) em paralelo entre si
- US3 e US4 podem ser desenvolvidas em paralelo (arquivos diferentes: `editar_pedido.py` vs
  `cancelar_pedido.py`), desde que `elegibilidade_transicao.py`/`orders_repository.py` (T020/T021)
  já estejam prontos
- US5 e US6 podem começar em paralelo com US3/US4, desde que T021 já exista

---

## Implementation Strategy

### MVP First (User Story 1)

1. Setup + Foundational
2. US1 — pedido criado e publicado, endpoint funcional
3. **PARAR e VALIDAR**: `pytest services/api-gateway/tests/test_validar_payload.py services/api-gateway/tests/test_solicitar_pedido.py -k "not integration"`

### Incremental Delivery

1. Setup + Foundational → `/health` funcional
2. US1 → criação de pedido via HTTP
3. US2 → mesmo endpoint aceita canal BATCH
4. US3 → edição de pedido
5. US4 → cancelamento de pedido
6. US5 → consulta individual
7. US6 → listagem por cliente

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente
- Verificar que os testes falham antes de implementar
- Rodar `ruff check`/`ruff format --check` a cada story fechada
- `elegibilidade_transicao.py` e `orders_repository.py` (T020/T021) são infraestrutura
  compartilhada entre US3–US6 — implementar uma vez, reaproveitar
- T009/T019/T026 e T010 cobrem os achados C2/C1 da análise `/speckit-analyze`: falha técnica de
  publicação (edge case da spec) e verificação de latência (SC-001), respectivamente
