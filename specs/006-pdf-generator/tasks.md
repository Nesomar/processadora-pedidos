# Tasks: PDF Generator

**Input**: Design documents from `/specs/006-pdf-generator/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/pdf-generator-messages.md`, `quickstart.md`, `.specify/memory/constitution.md`

**Tests**: Included because `spec.md`, `research.md`, and the project constitution require unit tests plus at least one Ministack integration test.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently after the shared foundation is complete.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the `pdf-generator` service skeleton and local runtime wiring.

- [X] T001 Create the pdf-generator package structure with `services/pdf-generator/src/pdf_generator/__init__.py`, `services/pdf-generator/src/pdf_generator/domain/__init__.py`, `services/pdf-generator/src/pdf_generator/adapters/__init__.py`, `services/pdf-generator/src/pdf_generator/handlers/__init__.py`, and `services/pdf-generator/tests/conftest.py`
- [X] T002 Create the service package metadata with Python 3.12, `pedidos-shared`, `reportlab`, `pytest`, and `ruff` in `services/pdf-generator/pyproject.toml`
- [X] T003 [P] Create the initial service README with consumed/produced queues, environment variables, health endpoint, and test commands in `services/pdf-generator/README.md`
- [X] T004 Add the `pdf-generator` container service with port `8082:8082`, Ministack endpoint, `.env`, and `uv run --package pdf-generator python -m pdf_generator.main` command in `infra/docker-compose.yml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core service plumbing and shared client changes required by all user stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Extend `S3Client.put_object` with an optional `content_type: str | None = None` parameter (backward-compatible, no other caller exists yet) and add a unit test covering both the default and explicit `content_type` calls in `shared/pedidos_shared/src/pedidos_shared/clients/s3.py` and `shared/pedidos_shared/tests/test_s3.py`
- [X] T006 Implement pdf-generator settings loading with required queue/bucket/table settings in `services/pdf-generator/src/pdf_generator/config.py`
- [X] T007 [P] Implement approved and rejected response payload builders (`montar_resposta_sucesso`, `montar_resposta_falha`) in `services/pdf-generator/src/pdf_generator/domain/mensagens.py`
- [X] T008 [P] Implement `montar_chave_invoice(order_id, momento)` pure function in `services/pdf-generator/src/pdf_generator/domain/chave_s3.py`
- [X] T009 [P] Create the storage adapter skeleton with `salvar_pdf(s3, bucket, key, conteudo)` wrapping `S3Client.put_object` in `services/pdf-generator/src/pdf_generator/adapters/armazenamento.py`
- [X] T010 Implement the SQS consumer loop with `is_message_processed` before handler execution and `mark_message_processed` only after successful or business-rejected handling in `services/pdf-generator/src/pdf_generator/adapters/worker_loop.py`
- [X] T011 Implement the composition root with a `/health` server on port 8082 and a consumer thread for `pdf_request_queue` in `services/pdf-generator/src/pdf_generator/main.py`

**Checkpoint**: Foundation ready. User stories can now proceed in priority order or in parallel where marked.

---

## Phase 3: User Story 1 - Emitir nota fiscal de pedido aprovado (Priority: P1) MVP

**Goal**: Generate the invoice PDF for an approved order, store it in S3, and publish a success response with the S3 key.

**Independent Test**: Publish a `pdf_request_queue` message with customer name, document, 1+ items, and complete totals; verify a PDF appears in S3 under `invoices/{year}/{month}/{day}/{order_id}.pdf` and `pdf_response_queue` receives `success=true` with the matching `s3_key`.

### Tests for User Story 1

- [X] T012 [P] [US1] Add unit tests for `montar_chave_invoice` (date formatting, no internal clock) in `services/pdf-generator/tests/test_chave_s3.py`
- [X] T013 [P] [US1] Add unit tests for `renderizar_nota_fiscal` asserting the output starts with `%PDF-`, is non-empty, and reflects customer/items/totals in `services/pdf-generator/tests/test_renderizador.py`
- [X] T014 [P] [US1] Add a handler happy-path test that mocks `S3Client` and captures the response published to SQS in `services/pdf-generator/tests/test_gerar_pdf.py`

### Implementation for User Story 1

- [X] T015 [US1] Implement `DadosNotaFiscal`/`ItemNotaFiscal` dataclasses, payload parsing, and `renderizar_nota_fiscal` (ReportLab `platypus`, no recalculation of monetary values) in `services/pdf-generator/src/pdf_generator/domain/renderizador.py`
- [X] T016 [US1] Implement `salvar_pdf` calling `S3Client.put_object(..., content_type="application/pdf")` in `services/pdf-generator/src/pdf_generator/adapters/armazenamento.py`
- [X] T017 [US1] Implement happy-path orchestration (parse payload, build S3 key, render PDF, store, publish success response) in `services/pdf-generator/src/pdf_generator/handlers/gerar_pdf.py`

**Checkpoint**: US1 generates and stores invoices, and publishes approved responses independently.

---

## Phase 4: User Story 2 - Reportar falha de geração sem travar o pedido (Priority: P1)

**Goal**: Reject `pdf_request_queue` messages with incomplete data (no items, missing document, or missing name) as a business outcome, without retry.

**Independent Test**: Publish a message with an empty items list or missing `customer_document`; verify `pdf_response_queue` receives `success=false` with a descriptive `error_message` and no object is written to S3.

### Tests for User Story 2

- [X] T018 [P] [US2] Add unit tests for `validar_solicitacao` covering empty items, missing `customer_document`, missing `customer_name`, missing totals, and an item missing `quantity`/`unit_price`/`discount_percentage`/`line_total` (Clarifications) in `services/pdf-generator/tests/test_validacao.py`
- [X] T019 [P] [US2] Add handler tests asserting `success=false` responses and no S3 write for incomplete requests in `services/pdf-generator/tests/test_gerar_pdf.py`

### Implementation for User Story 2

- [X] T020 [P] [US2] Implement `validar_solicitacao(payload) -> str | None`, checking customer name/document, non-empty items, totals, and per-item numeric fields (Clarifications) in `services/pdf-generator/src/pdf_generator/domain/validacao.py`
- [X] T021 [US2] Integrate the validation short-circuit (publish `success=false`, skip rendering/storage) into `services/pdf-generator/src/pdf_generator/handlers/gerar_pdf.py`

**Checkpoint**: US2 rejects incomplete requests as a permanent business outcome, independent of storage.

---

## Phase 5: User Story 3 - Preservar disponibilidade diante de falha técnica de armazenamento (Priority: P2)

**Goal**: Avoid publishing a business decision when S3 is temporarily unavailable while storing the PDF.

**Independent Test**: Simulate an S3 failure during `put_object`; verify no response is published to `pdf_response_queue` and the original message is not deleted or marked as processed.

### Tests for User Story 3

- [X] T022 [P] [US3] Add adapter tests proving `salvar_pdf` propagates `S3Client` exceptions instead of swallowing them in `services/pdf-generator/tests/test_armazenamento.py`
- [X] T023 [P] [US3] Add worker loop tests proving technical exceptions do not delete or mark messages in `services/pdf-generator/tests/test_worker_loop.py`

### Implementation for User Story 3

- [X] T024 [US3] Ensure `salvar_pdf` does not catch or convert `S3Client` exceptions into a business response in `services/pdf-generator/src/pdf_generator/adapters/armazenamento.py`
- [X] T025 [US3] Ensure the worker loop logs technical failures but does not acknowledge or mark messages in `services/pdf-generator/src/pdf_generator/adapters/worker_loop.py`

**Checkpoint**: US3 preserves correctness under storage instability by letting SQS redrive handle retries.

---

## Phase 6: User Story 4 - Reprocessar a mesma mensagem sem duplicar a nota fiscal (Priority: P3)

**Goal**: Guarantee idempotent handling of duplicated SQS deliveries by `message_id`.

**Independent Test**: Publish or process the same `MessageEnvelope.message_id` twice and verify only one PDF is stored and only one response is published in `pdf_response_queue`.

### Tests for User Story 4

- [X] T026 [P] [US4] Add duplicate-message unit tests for `is_message_processed` short-circuit behavior in `services/pdf-generator/tests/test_worker_loop.py`
- [X] T027 [US4] Add a Ministack integration test that sends the same message twice and asserts one response in `pdf_response_queue` plus one object in S3 in `services/pdf-generator/tests/test_idempotencia.py`

### Implementation for User Story 4

- [X] T028 [US4] Complete duplicate-message acknowledgement without handler execution in `services/pdf-generator/src/pdf_generator/adapters/worker_loop.py`
- [X] T029 [US4] Wire `message_id`, `order_id`, and `correlation_id` preservation in response envelopes in `services/pdf-generator/src/pdf_generator/handlers/gerar_pdf.py`

**Checkpoint**: US4 prevents duplicate invoice generation and responses across message redelivery.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Complete service readiness, documentation, and verification required by the constitution.

- [X] T030 [P] Add health endpoint tests for `GET /health` success and unknown path 404 in `services/pdf-generator/tests/test_health.py`
- [X] T031 [P] Add README examples for local run, `GET http://localhost:8082/health`, unit tests, and integration tests in `services/pdf-generator/README.md`
- [X] T032 Run `uv run --package pdf-generator pytest services/pdf-generator/tests -v` and fix any failures in `services/pdf-generator/`
- [X] T033 Run `uv run --package pdf-generator ruff check services/pdf-generator` and `uv run --package pdf-generator ruff format --check services/pdf-generator`, then fix any issues in `services/pdf-generator/`
- [X] T034 Validate `docker compose -f infra/docker-compose.yml up -d` starts `pdf-generator` after bootstrap and fix service wiring in `infra/docker-compose.yml`
- [X] T035 Execute the manual quickstart validation scenarios and record any corrections needed in `specs/006-pdf-generator/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion. Blocks all user stories.
- **User Stories (Phase 3+)**: Depend on Foundational completion.
- **Polish (Phase 7)**: Depends on desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2. Provides the rendering/storage path reused by later stories.
- **US2 (P1)**: Can start after Phase 2. Independent of US1 except for the shared handler file.
- **US3 (P2)**: Can start after Phase 2. Validates adapter and worker-loop technical failure behavior; touches the same files as US1 (`armazenamento.py`, `worker_loop.py`) so should follow US1 in practice even though the rule itself is independent.
- **US4 (P3)**: Depends on the worker-loop foundation from Phase 2; benefits from US1/US2 existing so the integration test has a real success path to duplicate.

### Within Each User Story

- Write tests first and confirm they fail before implementation.
- Domain functions before handler integration.
- Adapter behavior before handler behavior that depends on it.
- Handler behavior before integration tests.
- Complete each checkpoint before moving to the next priority when working sequentially.

---

## Parallel Opportunities

- T003 can run in parallel with T002 because README work does not modify package metadata.
- T007, T008, and T009 can run in parallel after T006 because they touch independent modules.
- US1 tests T012, T013, and T014 can run in parallel; T015 must complete before T016 and T017 (same file dependency chain: render → store → orchestrate).
- US2 tests T018 and T019 can run in parallel; T020 can run before T021 integrates it.
- US3 tests T022 and T023 can run in parallel because they cover different modules.
- US4 unit test T026 can run before the integration test T027.
- Polish tasks T030 and T031 can run in parallel after main behavior exists.

---

## Parallel Example: User Story 1

```bash
Task: "Add unit tests for montar_chave_invoice in services/pdf-generator/tests/test_chave_s3.py"
Task: "Add unit tests for renderizar_nota_fiscal in services/pdf-generator/tests/test_renderizador.py"
Task: "Add a handler happy-path test in services/pdf-generator/tests/test_gerar_pdf.py"
```

## Parallel Example: User Story 3

```bash
Task: "Add adapter tests proving salvar_pdf propagates S3Client exceptions in services/pdf-generator/tests/test_armazenamento.py"
Task: "Add worker loop tests proving technical exceptions do not delete or mark messages in services/pdf-generator/tests/test_worker_loop.py"
```

---

## Implementation Strategy

### MVP First (P1 Stories)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete US1 and US2 because both are P1 and together define a correct emission decision
   (success or permanent business rejection).
4. Stop and validate the MVP with unit tests plus a local queue flow using `pdf_request_queue`
   and `pdf_response_queue`.

### Incremental Delivery

1. Deliver Setup + Foundational so the worker can start and consume the queue.
2. Deliver US1 to prove successful invoice generation and storage.
3. Deliver US2 to cover the incomplete-data rejection path.
4. Deliver US3 to harden storage-failure behavior.
5. Deliver US4 to guarantee duplicate-message safety.
6. Finish Polish verification before PR.

### MVP Scope

The suggested MVP is Phases 1-4: Setup, Foundational, US1, and US2. These P1 stories provide a
complete emitter for valid invoices and a safe rejection path for incomplete requests.

---

## Notes

- `[P]` tasks touch different files or independent modules and can be run in parallel after their
  phase prerequisites.
- `[US#]` labels map tasks to the user stories in `spec.md`.
- The service must never write to `orders`; only `pdf_response_queue` (plus the S3 object itself)
  is an output.
- Technical storage failures must remain exceptions so the worker loop avoids ack and
  processed-message marking.
- Use `Decimal` for monetary values already present in the payload; this service never recalculates
  them.
- Avoid logging raw `customer_document`; use masking from `pedidos_shared` if document data appears
  in logs.
