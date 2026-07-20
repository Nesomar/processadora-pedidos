---

description: "Task list for Order Processor"
---

# Tasks: Order Processor

**Input**: Design documents from `/specs/004-order-processor/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/order-processor-messages.md,
research.md

**Tests**: Incluídas — constitution IX exige testes unitários + ao menos um teste de integração
contra o Ministack.

**Nota de dependência real**: T004/T005 estendem `pedidos_shared.SqsClient` (feature
`001-fundacao-compartilhada`, já mergeada) com um método aditivo `receive_with_receipt` — o
`receive()` atual não devolve `receipt_handle`, o que impede confirmar (`delete`) uma mensagem
específica depois de processá-la. Sem isso, o worker não consegue implementar corretamente
"não confirmar mensagem em falha, deixar o redrive nativo do SQS agir" (research.md #3/#4). É uma
extensão aditiva (não quebra `receive()` nem os consumidores existentes de 003-api-gateway).

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

```
services/order-processor/
├── pyproject.toml
├── src/order_processor/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── handlers/{solicitar_pedido,editar_pedido,cancelar_pedido,validar_pedido_response,
│   │             pdf_response}.py
│   ├── domain/{transicoes,mensagens}.py
│   └── adapters/{worker_loop,orders_repository}.py
└── tests/{test_health,test_worker_loop,test_transicoes,test_orders_repository,
          test_solicitar_pedido,test_editar_pedido,test_cancelar_pedido,
          test_validar_pedido_response,test_pdf_response,test_idempotencia}.py
```

---

## Phase 1: Setup

- [X] T001 Criar esqueleto em `services/order-processor/` (`pyproject.toml`, `src/order_processor/`, `src/order_processor/{handlers,domain,adapters}/`, `tests/`) conforme plan.md
- [X] T002 [P] Confirmar que `services/order-processor` é coberto pelo glob `services/*` do workspace `uv` na raiz (sem edição necessária, só validar com `uv sync`)
- [X] T003 [P] Configurar `ruff` em `services/order-processor/pyproject.toml`

**Checkpoint**: `uv sync --package order-processor` roda sem erro

---

## Phase 2: Foundational

- [X] T004 Estender `SqsClient` com `receive_with_receipt(queue_url, max_messages=10) -> list[tuple[MessageEnvelope, str]]` (envelope + `ReceiptHandle`), aditivo ao `receive()` existente, em `shared/pedidos_shared/src/pedidos_shared/clients/sqs.py`
- [X] T005 [P] Teste de `receive_with_receipt` (retorna envelope + receipt_handle; `delete(queue_url, receipt_handle)` remove só aquela mensagem) em `shared/pedidos_shared/tests/clients/test_sqs.py` (depende de T004)
- [X] T006 Implementar `config.py` (`Settings` de `pedidos_shared`; valida `solicitar_pedido_queue_url`, `editar_pedido_queue_url`, `cancelar_pedido_queue_url`, `validar_pedido_queue_url`, `validar_pedido_response_queue_url`, `pdf_request_queue_url`, `pdf_response_queue_url`, `orders_table_name`) em `services/order-processor/src/order_processor/config.py` (depende de T001)
- [X] T007 Implementar `adapters/worker_loop.py` (`run_consumer`: `receive_with_receipt` + checa `mark_message_processed` + invoca handler + confirma via `delete` só em sucesso) em `services/order-processor/src/order_processor/adapters/worker_loop.py` (depende de T004, T006)
- [X] T008 [P] Teste de `worker_loop` (mensagem nova → handler chamado e confirmada; mensagem já processada → handler NÃO chamado, confirmada mesmo assim; handler levanta exceção → mensagem NÃO confirmada) em `services/order-processor/tests/test_worker_loop.py` (depende de T007)
- [X] T009 Implementar `main.py` (sobe as 5 threads de consumo — vazias por ora — e a thread `/health` na porta 8080) em `services/order-processor/src/order_processor/main.py` (depende de T006, T007)
- [X] T010 [P] Teste de `GET /health` (200, `{"status":"ok"}`) em `services/order-processor/tests/test_health.py` (depende de T009)

**Checkpoint**: `uv run --package order-processor python -m order_processor.main` sobe e `/health` responde

---

## Phase 3: User Story 1 - Sistema aceita nova solicitação de pedido e dispara validação (Priority: P1) 🎯 MVP

**Independent Test**: publicar uma mensagem válida em `solicitar_pedido_queue`, confirmar que o
registro aparece em `orders` com `status=PROCESSING` e que uma mensagem aparece em
`validar_pedido_queue`.

### Tests

- [X] T011 [P] [US1] Teste de `aplicar_solicitacao` (sempre resulta em `PROCESSING`) em `services/order-processor/tests/test_transicoes.py`
- [X] T012 [P] [US1] Teste de `orders_repository.create` (grava com `version=0`; `ConditionExpression` falha se `order_id` já existir) em `services/order-processor/tests/test_orders_repository.py`
- [X] T013 [P] [US1] Teste de `handlers/solicitar_pedido` (cria registro `PROCESSING`, publica `validar_pedido_queue` com `{customer_document, items}` — clients mockados) em `services/order-processor/tests/test_solicitar_pedido.py`
- [X] T014 [US1] Teste de integração: mensagem real em `solicitar_pedido_queue` resulta em registro em `orders` e mensagem em `validar_pedido_queue` (SC-001) em `services/order-processor/tests/test_solicitar_pedido.py` (depende de T013)

### Implementation

- [X] T015 [P] [US1] Implementar `domain/transicoes.py`: `aplicar_solicitacao` em `services/order-processor/src/order_processor/domain/transicoes.py`
- [X] T016 [P] [US1] Implementar `domain/mensagens.py`: `montar_payload_validacao` em `services/order-processor/src/order_processor/domain/mensagens.py`
- [X] T017 [P] [US1] Implementar `adapters/orders_repository.py`: `create`, `get_by_id` em `services/order-processor/src/order_processor/adapters/orders_repository.py`
- [X] T018 [US1] Implementar `handlers/solicitar_pedido.py` (cria `Order`, publica `validar_pedido_queue`) em `services/order-processor/src/order_processor/handlers/solicitar_pedido.py` (depende de T015, T016, T017)
- [X] T019 [US1] Registrar consumo de `solicitar_pedido_queue` em `main.py` (depende de T018, T009)

**Checkpoint**: MVP pronto e testável

---

## Phase 4: User Story 2 - Sistema conclui ou rejeita conforme resultado da validação (Priority: P1)

### Tests

- [X] T020 [P] [US2] Teste de `aplicar_resposta_validacao` (aprovado→`INVOICING`; reprovado→`REJECTED`) em `services/order-processor/tests/test_transicoes.py`
- [X] T021 [P] [US2] Teste de `orders_repository.update_with_version` (grava com `ConditionExpression` sobre `version`; conflito recarrega e reavalia até 3 tentativas; esgotado levanta `ConflitoDeConcorrenciaError`) em `services/order-processor/tests/test_orders_repository.py`
- [X] T022 [P] [US2] Teste de `handlers/validar_pedido_response` (aprovado: atualiza itens/totais, `INVOICING`, publica `pdf_request_queue`; reprovado: `REJECTED` com `status_reason`) em `services/order-processor/tests/test_validar_pedido_response.py`
- [X] T023 [US2] Teste de integração: resposta de validação real resulta na transição correta em `orders` (SC-002) em `services/order-processor/tests/test_validar_pedido_response.py` (depende de T022)

### Implementation

- [X] T024 [P] [US2] Implementar `domain/transicoes.py`: `aplicar_resposta_validacao` (depende de T015)
- [X] T025 [P] [US2] Implementar `domain/mensagens.py`: `montar_payload_pdf` (depende de T016)
- [X] T026 [US2] Implementar `adapters/orders_repository.py`: `update_with_version` (depende de T017)
- [X] T027 [US2] Implementar `handlers/validar_pedido_response.py` (depende de T024, T025, T026)
- [X] T028 [US2] Registrar consumo de `validar_pedido_response_queue` em `main.py` (depende de T027)

**Checkpoint**: US1+US2 independentes e testáveis

---

## Phase 5: User Story 3 - Sistema emite a nota fiscal e conclui o pedido (Priority: P1)

### Tests

- [X] T029 [P] [US3] Teste de `aplicar_resposta_pdf` (sucesso→`COMPLETED`; falha→`FAILED`) em `services/order-processor/tests/test_transicoes.py`
- [X] T030 [P] [US3] Teste de `handlers/pdf_response` (sucesso: `invoice_s3_key` + `COMPLETED`; falha: `status_reason` + `FAILED`) em `services/order-processor/tests/test_pdf_response.py`
- [X] T031 [US3] Teste de integração: resposta de PDF real conclui o pedido (SC-003) em `services/order-processor/tests/test_pdf_response.py` (depende de T030)

### Implementation

- [X] T032 [P] [US3] Implementar `domain/transicoes.py`: `aplicar_resposta_pdf` (depende de T024)
- [X] T033 [US3] Implementar `handlers/pdf_response.py` (depende de T026, T032)
- [X] T034 [US3] Registrar consumo de `pdf_response_queue` em `main.py` (depende de T033)

**Checkpoint**: US1–US3 independentes e testáveis — fluxo principal completo

---

## Phase 6: User Story 4 - Pedido editado reinicia o ciclo de processamento (Priority: P2)

### Tests

- [X] T035 [P] [US4] Teste de `aplicar_edicao` (aceita `RECEIVED`/`VALIDATED`/`REJECTED`; rejeita os demais estados) em `services/order-processor/tests/test_transicoes.py`
- [X] T036 [P] [US4] Teste de `handlers/editar_pedido` (aceito: atualiza dados, `PROCESSING`, publica `validar_pedido_queue`; rejeitado: erro de negócio, pedido inalterado) em `services/order-processor/tests/test_editar_pedido.py`

### Implementation

- [X] T037 [P] [US4] Implementar `domain/transicoes.py`: `aplicar_edicao` (depende de T032)
- [X] T038 [US4] Implementar `handlers/editar_pedido.py` (depende de T026, T037, T016)
- [X] T039 [US4] Registrar consumo de `editar_pedido_queue` em `main.py` (depende de T038)

**Checkpoint**: US1–US4 independentes e testáveis

---

## Phase 7: User Story 5 - Pedido cancelado é encerrado (Priority: P2)

### Tests

- [X] T040 [P] [US5] Teste de `aplicar_cancelamento` (aceita `RECEIVED`/`PROCESSING`/`VALIDATING`/`VALIDATED`; rejeita os demais estados) em `services/order-processor/tests/test_transicoes.py`
- [X] T041 [P] [US5] Teste de `handlers/cancelar_pedido` (aceito: `CANCELLED` + `status_reason`; rejeitado: erro de negócio, pedido inalterado) em `services/order-processor/tests/test_cancelar_pedido.py`

### Implementation

- [X] T042 [P] [US5] Implementar `domain/transicoes.py`: `aplicar_cancelamento` (depende de T037)
- [X] T043 [US5] Implementar `handlers/cancelar_pedido.py` (depende de T026, T042)
- [X] T044 [US5] Registrar consumo de `cancelar_pedido_queue` em `main.py` (depende de T043)

**Checkpoint**: US1–US5 independentes e testáveis

---

## Phase 8: User Story 6 - Reprocessar a mesma mensagem não duplica nem corrompe (Priority: P3)

### Tests

- [X] T045 [P] [US6] Teste de idempotência (mesmo `message_id` processado duas vezes não duplica registro nem publica mensagem downstream duas vezes — parametrizado pelos 5 handlers) em `services/order-processor/tests/test_idempotencia.py`
- [X] T046 [US6] Teste de integração: reenvio real da mesma mensagem contra Ministack confirma efeito único (SC-004) em `services/order-processor/tests/test_idempotencia.py` (depende de T045)

### Implementation

Nenhuma — já coberta por `worker_loop.py` (T007) + `mark_message_processed`; esta fase só valida
a garantia que as fases anteriores já implementaram.

**Checkpoint**: todas as 6 user stories independentes e testáveis

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T047 [P] Escrever `services/order-processor/README.md` documentando as 5 filas consumidas, as 2 publicadas, variáveis de ambiente e comando de subida
- [X] T048 Rodar `ruff check`/`ruff format --check` em `services/order-processor/`
- [X] T049 Adicionar o serviço `order-processor` a `infra/docker-compose.yml` (build via `uv`, `depends_on` do `bootstrap` concluído, sem porta externa exceto `8080` do `/health`)
- [X] T050 Rodar os cenários de `quickstart.md` ponta a ponta contra o Ministack local
- [X] T051 [P] Executar o code review da constitution seção VII antes de abrir o PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup/Foundational**: bloqueiam tudo — inclui a extensão de `pedidos_shared.SqsClient` (T004/T005)
- **US1, US2, US3**: sequenciais em termos de fluxo de negócio (uma alimenta a próxima), mas cada
  handler é um arquivo independente — US2 pode começar assim que o Foundational fechar, sem
  esperar US1 terminar de verdade, já que os testes usam clients mockados
- **US4, US5**: independentes entre si e das demais; dependem só do Foundational e de
  `orders_repository.update_with_version` (criado em US2) e `domain/transicoes.py` (criado
  progressivamente por US1–US3)
- **US6**: depende de US1–US5 completas (valida a garantia de idempotência em todos os handlers)
- **Polish**: depende de todas as stories desejadas completas

### Parallel Opportunities

- T002/T003 (Setup) em paralelo
- T005 pode rodar em paralelo com T006 (arquivos diferentes)
- Testes de cada story (`[P]`) em paralelo entre si
- Os 5 handlers (`solicitar_pedido`, `editar_pedido`, `cancelar_pedido`,
  `validar_pedido_response`, `pdf_response`) são arquivos independentes — depois que
  `orders_repository.py` e `transicoes.py` tiverem as funções de que cada um precisa, os handlers
  em si podem ser implementados em paralelo

---

## Implementation Strategy

### MVP First (User Story 1)

1. Setup + Foundational (inclui extensão do `SqsClient`)
2. US1 — pedido solicitado é persistido e validação é disparada
3. **PARAR e VALIDAR**: `pytest services/order-processor/tests/test_transicoes.py services/order-processor/tests/test_solicitar_pedido.py -k "not integration"`

### Incremental Delivery

1. Setup + Foundational → `/health` funcional, loop de consumo genérico pronto
2. US1 → solicitação de pedido persistida e validação disparada
3. US2 → resultado da validação processado (aprovar → PDF; reprovar → encerrar)
4. US3 → resultado do PDF processado (concluir ou falhar)
5. US4 → edição reabre o ciclo
6. US5 → cancelamento encerra o pedido
7. US6 → idempotência validada explicitamente em todos os handlers

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente
- Verificar que os testes falham antes de implementar
- Rodar `ruff check`/`ruff format --check` a cada story fechada
- `domain/transicoes.py` e `adapters/orders_repository.py` crescem incrementalmente ao longo de
  US1–US5 (cada story adiciona uma função) — não são reescritos, só estendidos
