# Tasks: Order Validator

**Input**: Design documents from `/specs/005-order-validator/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/order-validator-messages.md`, `quickstart.md`, `.specify/memory/constitution.md`

**Tests**: Included because `spec.md`, `research.md`, and the project constitution require unit tests plus at least one Ministack integration test.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently after the shared foundation is complete.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the `order-validator` service skeleton and local runtime wiring.

- [X] T001 Create the order-validator package structure with `services/order-validator/src/order_validator/__init__.py`, `services/order-validator/src/order_validator/domain/__init__.py`, `services/order-validator/src/order_validator/adapters/__init__.py`, `services/order-validator/src/order_validator/handlers/__init__.py`, and `services/order-validator/tests/conftest.py`
- [X] T002 Create the service package metadata with Python 3.12, `pedidos-shared`, `httpx`, `pytest`, and `ruff` in `services/order-validator/pyproject.toml`
- [X] T003 [P] Create the initial service README with consumed/produced queues, environment variables, health endpoint, and test commands in `services/order-validator/README.md`
- [X] T004 Add `CATALOG_PRODUCTS_BASE_URL=https://dummyjson.com` and document the order-validator health port in `.env.example`
- [X] T005 Add the `order-validator` container service with port `8081:8081`, Ministack endpoint, `.env`, and `uv run --package order-validator python -m order_validator.main` command in `infra/docker-compose.yml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core service plumbing and shared data structures required by all user stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Implement order-validator settings loading with required queue/table settings and `catalog_products_base_url` default in `services/order-validator/src/order_validator/config.py`
- [X] T007 [P] Define `Produto`, `ItemValidacao`, `ErroValidacao`, and `ItemEnriquecido` dataclasses in `services/order-validator/src/order_validator/domain/modelos.py`
- [X] T008 [P] Implement approved and rejected response payload builders with JSON-safe decimal string conversion in `services/order-validator/src/order_validator/domain/mensagens.py`
- [X] T009 [P] Create the catalog adapter skeleton with `ProdutoNaoEncontradoError`, `CatalogoCache`, and `buscar_produto` placeholders in `services/order-validator/src/order_validator/adapters/catalogo_produtos.py`
- [X] T010 Implement the SQS consumer loop with `is_message_processed` before handler execution and `mark_message_processed` only after successful handling in `services/order-validator/src/order_validator/adapters/worker_loop.py`
- [X] T011 Implement the composition root with a `/health` server on port 8081 and a consumer thread for `validar_pedido_queue` in `services/order-validator/src/order_validator/main.py`

**Checkpoint**: Foundation ready. User stories can now proceed in priority order or in parallel where marked.

---

## Phase 3: User Story 1 - Aprovar pedido com itens disponiveis (Priority: P1) MVP

**Goal**: Approve valid orders by enriching items with catalog data and calculating monetary totals.

**Independent Test**: Publish a validation message with valid document, existing product, sufficient stock, minimum quantity satisfied, and total within the limit; verify `approved=true`, enriched item fields, and correct `subtotal`, `discount_total`, and `total`.

### Tests for User Story 1

- [X] T012 [P] [US1] Add unit tests for `calcular_item` and `calcular_totais` decimal behavior in `services/order-validator/tests/test_calculo.py`
- [X] T013 [P] [US1] Add a handler happy-path test that mocks catalog lookup and captures the response published to SQS in `services/order-validator/tests/test_validar_pedido.py`

### Implementation for User Story 1

- [X] T014 [P] [US1] Implement `calcular_item` and `calcular_totais` pure functions in `services/order-validator/src/order_validator/domain/calculo.py`
- [X] T015 [US1] Implement successful product response parsing from dummyjson fields into `Produto` in `services/order-validator/src/order_validator/adapters/catalogo_produtos.py`
- [X] T016 [US1] Implement happy-path validation orchestration and approved response publication in `services/order-validator/src/order_validator/handlers/validar_pedido.py`

**Checkpoint**: US1 approves valid orders and produces enriched items and totals independently.

---

## Phase 4: User Story 2 - Reprovar pedido com documento invalido (Priority: P1)

**Goal**: Reject orders whose `customer_document` is not a valid CPF or CNPJ, without relying on catalog calls for that decision.

**Independent Test**: Publish a validation message with structurally invalid or verifier-digit-invalid document; verify `approved=false`, `INVALID_DOCUMENT`, `product_id=null`, and null totals/items.

### Tests for User Story 2

- [X] T017 [P] [US2] Add CPF/CNPJ unit tests for valid documents, invalid sizes, invalid verifier digits, and repeated digits in `services/order-validator/tests/test_documento.py`
- [X] T018 [P] [US2] Add handler tests for invalid document rejection and invalid-document-plus-item-error aggregation in `services/order-validator/tests/test_validar_pedido.py`

### Implementation for User Story 2

- [X] T019 [P] [US2] Implement `validar_documento(document: str) -> bool` with CPF/CNPJ modulo 11 verifier logic in `services/order-validator/src/order_validator/domain/documento.py`
- [X] T020 [US2] Integrate document validation and `INVALID_DOCUMENT` error creation into `services/order-validator/src/order_validator/handlers/validar_pedido.py`

**Checkpoint**: US2 rejects invalid documents and can aggregate the document error with item errors.

---

## Phase 5: User Story 3 - Reprovar item indisponivel ou abaixo do minimo (Priority: P1)

**Goal**: Reject orders with items that violate stock availability or minimum order quantity rules, reporting every applicable item error.

**Independent Test**: Publish a validation message with an item below `minimumOrderQuantity` or above available stock; verify `approved=false`, specific item error code, product id, and null totals/items.

### Tests for User Story 3

- [X] T021 [P] [US3] Add stock rule unit tests for sufficient stock, insufficient stock, and `Out of Stock` status in `services/order-validator/tests/test_estoque.py`
- [X] T022 [P] [US3] Add minimum quantity rule unit tests for allowed quantity and below-minimum quantity in `services/order-validator/tests/test_quantidade_minima.py`
- [X] T023 [P] [US3] Add handler tests for multiple item errors and multiple errors on the same item in `services/order-validator/tests/test_validar_pedido.py`

### Implementation for User Story 3

- [X] T024 [P] [US3] Implement `validar_estoque(quantity, produto)` returning `INSUFFICIENT_STOCK` errors in `services/order-validator/src/order_validator/domain/estoque.py`
- [X] T025 [P] [US3] Implement `validar_quantidade_minima(quantity, produto)` returning `BELOW_MINIMUM_ORDER_QUANTITY` errors in `services/order-validator/src/order_validator/domain/quantidade_minima.py`
- [X] T026 [US3] Integrate item rule aggregation and rejected response publication in `services/order-validator/src/order_validator/handlers/validar_pedido.py`

**Checkpoint**: US3 rejects invalid items with all applicable per-item errors.

---

## Phase 6: User Story 4 - Reprovar pedido que excede limite de valor (Priority: P1)

**Goal**: Reject otherwise valid orders when the calculated total exceeds `100000.00`.

**Independent Test**: Publish a validation message whose enriched items calculate to more than R$ 100,000.00; verify `approved=false`, `ORDER_TOTAL_EXCEEDS_LIMIT`, `product_id=null`, and null totals/items.

### Tests for User Story 4

- [X] T027 [P] [US4] Add total limit unit tests for below, equal, and above `100000.00` in `services/order-validator/tests/test_limite_total.py`
- [X] T028 [P] [US4] Add handler tests that apply the limit only after document and item validation pass in `services/order-validator/tests/test_validar_pedido.py`

### Implementation for User Story 4

- [X] T029 [P] [US4] Implement `validar_limite_total(total: Decimal)` with exclusive `> Decimal("100000.00")` rejection in `services/order-validator/src/order_validator/domain/limite_total.py`
- [X] T030 [US4] Integrate total limit validation after successful item enrichment in `services/order-validator/src/order_validator/handlers/validar_pedido.py`

**Checkpoint**: US4 rejects high-value orders only after a valid total can be computed.

---

## Phase 7: User Story 5 - Reprovar produto inexistente (Priority: P2)

**Goal**: Treat catalog `404` as a business rejection, not as a technical failure or retry case.

**Independent Test**: Publish a validation message for a nonexistent product id; verify `approved=false`, `PRODUCT_NOT_FOUND`, product id filled, and the original message confirmed.

### Tests for User Story 5

- [X] T031 [P] [US5] Add catalog adapter tests for `404` mapping to `ProdutoNaoEncontradoError` in `services/order-validator/tests/test_catalogo_produtos.py`
- [X] T032 [P] [US5] Add handler tests for `PRODUCT_NOT_FOUND` response and no stock/minimum checks after missing product in `services/order-validator/tests/test_validar_pedido.py`

### Implementation for User Story 5

- [X] T033 [US5] Implement `404` handling as `ProdutoNaoEncontradoError` in `services/order-validator/src/order_validator/adapters/catalogo_produtos.py`
- [X] T034 [US5] Integrate `ProdutoNaoEncontradoError` into rejected response generation in `services/order-validator/src/order_validator/handlers/validar_pedido.py`

**Checkpoint**: US5 rejects nonexistent products without triggering SQS redrive.

---

## Phase 8: User Story 6 - Preservar disponibilidade diante de falha tecnica da API externa (Priority: P2)

**Goal**: Avoid publishing a business decision when the catalog is unavailable due to timeout or server error.

**Independent Test**: Simulate timeout or 5xx from the catalog; verify no response is published and the original message is not deleted or marked as processed.

### Tests for User Story 6

- [X] T035 [P] [US6] Add catalog adapter tests for timeout retry behavior and 5xx technical failure propagation in `services/order-validator/tests/test_catalogo_produtos.py`
- [X] T036 [P] [US6] Add worker loop tests proving technical exceptions do not delete or mark messages in `services/order-validator/tests/test_worker_loop.py`

### Implementation for User Story 6

- [X] T037 [US6] Implement `httpx.Client` calls with 5s timeout, two retry attempts for connection/timeout errors, and technical failure propagation in `services/order-validator/src/order_validator/adapters/catalogo_produtos.py`
- [X] T038 [US6] Ensure the worker loop logs technical failures but does not acknowledge or mark messages in `services/order-validator/src/order_validator/adapters/worker_loop.py`

**Checkpoint**: US6 preserves correctness under catalog instability by letting SQS redrive handle retries.

---

## Phase 9: User Story 7 - Reduzir consultas repetidas ao catalogo externo (Priority: P3)

**Goal**: Cache product catalog lookups for 5 minutes per product id within the process.

**Independent Test**: Process two validation messages for the same product id and verify the second processing uses cached data without a new external call.

### Tests for User Story 7

- [X] T039 [P] [US7] Add cache tests for hit, miss, and TTL expiry using controlled monotonic time in `services/order-validator/tests/test_catalogo_produtos.py`
- [X] T040 [P] [US7] Add handler-level cache reuse test across two validation messages for the same product id in `services/order-validator/tests/test_validar_pedido.py`

### Implementation for User Story 7

- [X] T041 [US7] Implement `CatalogoCache` hit/miss/expiry behavior with 300-second TTL in `services/order-validator/src/order_validator/adapters/catalogo_produtos.py`
- [X] T042 [US7] Use `CatalogoCache` inside `buscar_produto` before and after external catalog calls in `services/order-validator/src/order_validator/adapters/catalogo_produtos.py`

**Checkpoint**: US7 avoids repeated external calls within the configured TTL window.

---

## Phase 10: User Story 8 - Reprocessar a mesma mensagem sem duplicar resposta (Priority: P3)

**Goal**: Guarantee idempotent handling of duplicated SQS deliveries by `message_id`.

**Independent Test**: Publish or process the same `MessageEnvelope.message_id` twice and verify only one response is published.

### Tests for User Story 8

- [X] T043 [P] [US8] Add duplicate-message unit tests for `is_message_processed` short-circuit behavior in `services/order-validator/tests/test_worker_loop.py`
- [X] T044 [US8] Add a Ministack integration test that sends the same message twice and asserts one response in `validar_pedido_response_queue` in `services/order-validator/tests/test_idempotencia.py`

### Implementation for User Story 8

- [X] T045 [US8] Complete duplicate-message acknowledgement without handler execution in `services/order-validator/src/order_validator/adapters/worker_loop.py`
- [X] T046 [US8] Wire `message_id`, `order_id`, and `correlation_id` preservation in response envelopes in `services/order-validator/src/order_validator/handlers/validar_pedido.py`

**Checkpoint**: US8 prevents duplicate validation responses across message redelivery.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Complete service readiness, documentation, and verification required by the constitution.

- [X] T047 [P] Add health endpoint tests for `GET /health` success and unknown path 404 in `services/order-validator/tests/test_health.py`
- [X] T048 [P] Add README examples for local run, `GET http://localhost:8081/health`, unit tests, integration tests, and manual dummyjson validation in `services/order-validator/README.md`
- [X] T049 Run `uv run --package order-validator pytest services/order-validator/tests -v` and fix any failures in `services/order-validator/`
- [X] T050 Run `uv run --package order-validator ruff check services/order-validator` and `uv run --package order-validator ruff format --check services/order-validator`, then fix any issues in `services/order-validator/`
- [X] T051 Validate `docker compose -f infra/docker-compose.yml up -d` starts `order-validator` after bootstrap and fix service wiring in `infra/docker-compose.yml`
- [X] T052 Execute the manual quickstart validation scenarios and record any corrections needed in `specs/005-order-validator/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion. Blocks all user stories.
- **User Stories (Phase 3+)**: Depend on Foundational completion.
- **Polish (Phase 11)**: Depends on desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2. Provides approved response and calculation path for later total-limit checks.
- **US2 (P1)**: Can start after Phase 2. Independent of US1 except for shared rejected response builder.
- **US3 (P1)**: Can start after Phase 2. Independent item rule validation.
- **US4 (P1)**: Depends on US1 calculation behavior because the limit applies to computed totals.
- **US5 (P2)**: Can start after Phase 2. Integrates with the same item loop used by US3.
- **US6 (P2)**: Can start after Phase 2. Validates adapter and worker-loop technical failure behavior.
- **US7 (P3)**: Depends on catalog adapter shape from US1/US5/US6.
- **US8 (P3)**: Depends on worker-loop foundation from Phase 2.

### Within Each User Story

- Write tests first and confirm they fail before implementation.
- Domain functions before handler integration.
- Adapter behavior before handler behavior that depends on it.
- Handler behavior before integration tests.
- Complete each checkpoint before moving to the next priority when working sequentially.

---

## Parallel Opportunities

- T003 can run in parallel with T002 because README work does not modify package metadata.
- T007, T008, and T009 can run in parallel after T001 because they touch independent modules.
- US1 tests T012 and T013 can run in parallel; T014 can run in parallel with T015 before T016 integrates them.
- US2 tests T017 and T018 can run in parallel; T019 can run before T020 integrates it.
- US3 tests T021, T022, and T023 can run in parallel; T024 and T025 can run in parallel before T026 integrates them.
- US4 tests T027 and T028 can run in parallel; T029 can run before T030 integrates it.
- US5 tests T031 and T032 can run in parallel before T033 and T034.
- US6 tests T035 and T036 can run in parallel because they cover different modules.
- US7 tests T039 and T040 can run in parallel; T041 and T042 then complete adapter caching.
- US8 unit test T043 can run before the integration test T044.
- Polish tasks T047 and T048 can run in parallel after main behavior exists.

---

## Parallel Example: User Story 3

```bash
Task: "Add stock rule unit tests for sufficient stock, insufficient stock, and Out of Stock status in services/order-validator/tests/test_estoque.py"
Task: "Add minimum quantity rule unit tests for allowed quantity and below-minimum quantity in services/order-validator/tests/test_quantidade_minima.py"
Task: "Implement validar_estoque(quantity, produto) returning INSUFFICIENT_STOCK errors in services/order-validator/src/order_validator/domain/estoque.py"
Task: "Implement validar_quantidade_minima(quantity, produto) returning BELOW_MINIMUM_ORDER_QUANTITY errors in services/order-validator/src/order_validator/domain/quantidade_minima.py"
```

## Parallel Example: User Story 6

```bash
Task: "Add catalog adapter tests for timeout retry behavior and 5xx technical failure propagation in services/order-validator/tests/test_catalogo_produtos.py"
Task: "Add worker loop tests proving technical exceptions do not delete or mark messages in services/order-validator/tests/test_worker_loop.py"
```

## Parallel Example: User Story 7

```bash
Task: "Add cache tests for hit, miss, and TTL expiry using controlled monotonic time in services/order-validator/tests/test_catalogo_produtos.py"
Task: "Add handler-level cache reuse test across two validation messages for the same product id in services/order-validator/tests/test_validar_pedido.py"
```

---

## Implementation Strategy

### MVP First (P1 Stories)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete US1, US2, US3, and US4 because all are P1 and together define a correct validation decision.
4. Stop and validate the MVP with unit tests plus a local queue flow using `validar_pedido_queue` and `validar_pedido_response_queue`.

### Incremental Delivery

1. Deliver Setup + Foundational so the worker can start and consume one queue.
2. Deliver US1 to prove successful approval and totals.
3. Deliver US2 and US3 to cover core business rejection cases.
4. Deliver US4 to enforce the total limit.
5. Deliver US5 and US6 to harden catalog boundary behavior.
6. Deliver US7 and US8 to improve efficiency and duplicate-message safety.
7. Finish Polish verification before PR.

### MVP Scope

The suggested MVP is Phases 1-6: Setup, Foundational, US1, US2, US3, and US4. These P1 stories provide a complete validator for valid approval, invalid document rejection, invalid item rejection, and high-value order rejection.

---

## Notes

- `[P]` tasks touch different files or independent modules and can be run in parallel after their phase prerequisites.
- `[US#]` labels map tasks to the user stories in `spec.md`.
- The service must never write to `orders`; only `validar_pedido_response_queue` is an output.
- Technical catalog failures must remain exceptions so the worker loop avoids ack and processed-message marking.
- Use `Decimal` for monetary calculations and serialize decimal values as strings in response payloads.
- Avoid logging raw `customer_document`; use masking from `pedidos_shared` if document data appears in logs.
