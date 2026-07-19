---

description: "Task list for Fundação Compartilhada (pedidos_shared)"
---

# Tasks: Fundação Compartilhada (pedidos_shared)

**Input**: Design documents from `/specs/001-fundacao-compartilhada/` (realinhado a
`docs/01-dominio-e-contratos.md`)

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/pedidos_shared-api.md, research.md

**Tests**: Incluídas — FR-014 exige testes dos modelos, transições, idempotência e parser.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

```
shared/pedidos_shared/
├── src/pedidos_shared/{models,status,settings,idempotency,masking,logging,file_layout}.py
│                        + clients/{sqs,dynamodb,s3}.py
└── tests/{test_models,test_status,test_settings,test_idempotency,test_masking,test_logging,
          test_file_layout}.py + tests/fixtures/exemplo.txt + tests/clients/test_sqs.py
```

---

## Phase 1: Setup

- [ ] T001 Criar esqueleto em `shared/pedidos_shared/` (`pyproject.toml`, `src/pedidos_shared/`, `tests/`, `tests/fixtures/`, `tests/clients/`) conforme plan.md
- [ ] T002 [P] Configurar workspace `uv` na raiz (`[tool.uv.workspace] members = ["services/*", "shared/pedidos_shared"]`)
- [ ] T003 [P] Configurar `ruff` em `shared/pedidos_shared/pyproject.toml`

**Checkpoint**: `uv sync --package pedidos-shared` roda sem erro

---

## Phase 2: Foundational

- [ ] T004 Criar `shared/pedidos_shared/src/pedidos_shared/__init__.py` vazio (exports adicionados por story)

**Checkpoint**: `import pedidos_shared` funciona

---

## Phase 3: User Story 1 - Contrato de mensagens e máquina de estados únicos (Priority: P1) 🎯 MVP

**Independent Test**: importar o pacote, instanciar `Order`/`MessageEnvelope`, validar payload
inválido rejeitado e transição fora da tabela de `OrderStatus` rejeitada.

### Tests

- [ ] T005 [P] [US1] Teste de `OrderStatus`/`is_valid_transition` cobrindo toda a tabela de data-model.md (válidas aceitas, quaisquer outras rejeitadas) em `shared/pedidos_shared/tests/test_status.py`
- [ ] T006 [P] [US1] Teste de `Order`, `OrderItem`, `MessageEnvelope` (payload válido aceito, campo obrigatório ausente rejeitado, `version`/`Decimal` corretos) em `shared/pedidos_shared/tests/test_models.py`

### Implementation

- [ ] T007 [P] [US1] Implementar `OrderStatus` e `is_valid_transition` em `shared/pedidos_shared/src/pedidos_shared/status.py`
- [ ] T008 [P] [US1] Implementar `Order`, `OrderItem` em `shared/pedidos_shared/src/pedidos_shared/models.py`
- [ ] T009 [US1] Implementar `MessageEnvelope` em `shared/pedidos_shared/src/pedidos_shared/models.py` (depende de T008)
- [ ] T010 [US1] Exportar `Order`, `OrderItem`, `MessageEnvelope`, `OrderStatus`, `is_valid_transition` em `__init__.py` (depende de T007, T009)

**Checkpoint**: MVP pronto e testável

---

## Phase 4: User Story 2 - Configuração e clientes sem valores hardcoded (Priority: P1)

**Independent Test**: com env vars do Ministack, enviar/receber mensagem em qualquer uma das 9
filas sem URL fixa no código.

### Tests

- [ ] T011 [P] [US2] Teste de `Settings` (carrega valores válidos; falha clara quando falta `AWS_ENDPOINT_URL`/`AWS_REGION`/`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`PROCESSED_MESSAGES_TABLE_NAME`) em `shared/pedidos_shared/tests/test_settings.py`
- [ ] T012 [P] [US2] Teste de integração `SqsClient` (send + receive contra Ministack, envelope completo) em `shared/pedidos_shared/tests/clients/test_sqs.py`

### Implementation

- [ ] T013 [P] [US2] Implementar `Settings` (campos de data-model.md) em `shared/pedidos_shared/src/pedidos_shared/settings.py`
- [ ] T014 [US2] Implementar `SqsClient(settings)` em `shared/pedidos_shared/src/pedidos_shared/clients/sqs.py` (depende de T013)
- [ ] T015 [US2] Implementar `DynamoDbClient(settings)` em `shared/pedidos_shared/src/pedidos_shared/clients/dynamodb.py` (depende de T013)
- [ ] T016 [US2] Implementar `S3Client(settings)` em `shared/pedidos_shared/src/pedidos_shared/clients/s3.py` (depende de T013)
- [ ] T017 [US2] Exportar `Settings`, `SqsClient`, `DynamoDbClient`, `S3Client` em `__init__.py` (depende de T013–T016)

**Checkpoint**: US1+US2 independentes e testáveis

---

## Phase 5: User Story 3 - Idempotência via `processed_messages` (Priority: P2)

**Independent Test**: chamar `mark_message_processed` duas vezes com o mesmo `message_id` contra
Ministack; segunda chamada indica "já processado".

**Depende de**: US2 (usa `DynamoDbClient`/`Settings`).

### Tests

- [ ] T018 [P] [US3] Teste de `mark_message_processed` (primeira chamada processa, segunda indica duplicata, sem exceção) em `shared/pedidos_shared/tests/test_idempotency.py`

### Implementation

- [ ] T019 [US3] Implementar `mark_message_processed(message_id, consumer, settings)` (write condicional + TTL, research.md #4) em `shared/pedidos_shared/src/pedidos_shared/idempotency.py` (depende de T015)
- [ ] T020 [US3] Exportar `mark_message_processed` em `__init__.py` (depende de T019)

**Checkpoint**: US1–US3 independentes e testáveis

---

## Phase 6: User Story 4 - Logging estruturado + mascaramento de documento (Priority: P2)

**Independent Test**: log com `orderId`/`correlationId` → JSON válido; `mask_document` expõe só
últimos 4 dígitos.

### Tests

- [ ] T021 [P] [US4] Teste de `mask_document` (>4 chars mostra últimos 4; ≤4 chars mascarado integral) em `shared/pedidos_shared/tests/test_masking.py`
- [ ] T022 [P] [US4] Teste do logger (com/sem `orderId` → sempre JSON válido) em `shared/pedidos_shared/tests/test_logging.py`

### Implementation

- [ ] T023 [P] [US4] Implementar `mask_document` em `shared/pedidos_shared/src/pedidos_shared/masking.py`
- [ ] T024 [P] [US4] Implementar `JsonFormatter`/`get_logger` em `shared/pedidos_shared/src/pedidos_shared/logging.py`
- [ ] T025 [US4] Exportar `get_logger`, `mask_document` em `__init__.py`; docstring documentando que `Order.customer_document` MUST passar por `mask_document` antes de qualquer log (depende de T023, T024)

**Checkpoint**: US1–US4 independentes e testáveis

---

## Phase 7: User Story 5 - Parser do layout posicional (Priority: P3)

**Independent Test**: parsear arquivo de exemplo válido; testar cada uma das 5 regras de rejeição
isoladamente.

### Tests

- [ ] T026 [P] [US5] Criar `shared/pedidos_shared/tests/fixtures/exemplo.txt` (header + 1 pedido com 2 itens + trailer, conforme §6.9)
- [ ] T027 [US5] Teste de `parse_file` (arquivo válido; linha ≠200 chars; header/trailer ausente; contadores do trailer divergentes; item órfão; `item_count` divergente) em `shared/pedidos_shared/tests/test_file_layout.py` (depende de T026)

### Implementation

- [ ] T028 [P] [US5] Implementar `parse_file` + `ArquivoInvalidoError`/`LinhaInvalidaError`/`PedidoInvalidoError` (layout de data-model.md, as 5 regras) em `shared/pedidos_shared/src/pedidos_shared/file_layout.py`
- [ ] T029 [US5] Exportar `parse_file` e as 3 exceções em `__init__.py` (depende de T028)

**Checkpoint**: todas as 5 user stories independentes e testáveis

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T030 [P] Escrever `shared/pedidos_shared/README.md` documentando env vars de `Settings` e os contratos de mensagem expostos
- [ ] T031 Rodar `ruff check`/`ruff format --check` em `shared/pedidos_shared/` sem apontamentos
- [ ] T032 Rodar os cenários de `quickstart.md` ponta a ponta contra o Ministack local (feature `002-infraestrutura-local`)
- [ ] T033 [P] Executar o code review da constitution seção VII antes de abrir o PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup/Foundational**: bloqueiam tudo
- **US1, US2**: independentes entre si, ambas P1
- **US3**: depende de US2 (`DynamoDbClient`)
- **US4**: independente de US1–US3 (só usa `Order.customer_document` como referência de docstring, não import)
- **US5**: independente de US1–US4
- **Polish**: depende de todas as stories desejadas completas

### Parallel Opportunities

- Depois do Foundational: US1 e US2 em paralelo; depois que US2 fecha, US3 pode iniciar; US4 e US5
  podem rodar em paralelo com qualquer uma das outras a qualquer momento

---

## Implementation Strategy

### MVP First (User Story 1)

1. Setup + Foundational
2. US1 — contrato único disponível pros demais serviços
3. **PARAR e VALIDAR**: `pytest shared/pedidos_shared/tests/test_status.py shared/pedidos_shared/tests/test_models.py`

### Incremental Delivery

1. Setup + Foundational → base pronta
2. US1 → contrato/enum disponíveis
3. US2 → clientes de infraestrutura disponíveis
4. US3 → idempotência disponível (todo consumidor pode usar)
5. US4 → observabilidade + proteção de dado sensível
6. US5 → parser disponível pro fluxo BATCH

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente
- Verificar que os testes falham antes de implementar
- Rodar `ruff check`/`ruff format --check` a cada story fechada
