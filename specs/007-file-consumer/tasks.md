# Tasks: File Consumer

**Input**: Design documents from `/specs/007-file-consumer/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/file-consumer-messages.md`, `quickstart.md`, `.specify/memory/constitution.md`

**Tests**: Included because `spec.md`, `research.md`, and the project constitution require unit tests plus at least one Ministack integration test.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently after the shared foundation is complete. Two foundational tasks (T005-T008) touch `shared/pedidos_shared/` rather than this service's own tree — they fix `file_layout.parse_file` to match its originally documented contract (partial tolerance) and add raw (non-`MessageEnvelope`) send/receive support to `SqsClient`, both required by every user story in this feature.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the `file-consumer` service skeleton and local runtime wiring.

- [X] T001 Create the file-consumer package structure with `services/file-consumer/src/file_consumer/__init__.py`, `services/file-consumer/src/file_consumer/domain/__init__.py`, `services/file-consumer/src/file_consumer/adapters/__init__.py`, `services/file-consumer/src/file_consumer/handlers/__init__.py`, and `services/file-consumer/tests/conftest.py`
- [X] T002 Create the service package metadata with Python 3.12, `pedidos-shared`, `pytest`, and `ruff` in `services/file-consumer/pyproject.toml`
- [X] T003 [P] Create the initial service README with consumed/produced queues, environment variables, health endpoint, and test commands in `services/file-consumer/README.md`
- [X] T004 Add the `file-consumer` container service with port `8083:8083`, Ministack endpoint, `.env`, and `uv run --package file-consumer python -m file_consumer.main` command in `infra/docker-compose.yml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Fix the shared positional-file parser to match its originally documented contract, add raw SQS support to the shared client, and set up this service's core plumbing.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Redesign `parse_file` in `shared/pedidos_shared/src/pedidos_shared/file_layout.py` so only header/trailer-missing or trailer-counter-mismatch conditions raise `ArquivoInvalidoError`; a line with wrong length, an orphan item record, or an order with divergent `item_count` are instead instantiated (`LinhaInvalidaError`/`PedidoInvalidoError`) and appended to a new `ParsedFile.errors: list[Exception]` field, with parsing continuing for the rest of the file (research.md #1)
- [X] T006 Rewrite `test_parse_file_rejects_line_with_wrong_length`, `test_parse_file_rejects_orphan_item_record`, and `test_parse_file_rejects_order_with_divergent_item_count` to assert the tolerant behavior (no exception, error collected in `result.errors`, `result.orders` reflects only valid orders), and add a new test with a multi-order file where one order is invalid and the others still appear in `result.orders`, in `shared/pedidos_shared/tests/test_file_layout.py`
- [X] T007 [P] Add `send_raw(queue_url, body: dict) -> str` and `receive_raw_with_receipt(queue_url, max_messages=10) -> list[tuple[dict, str, str]]` (body, receipt handle, native SQS `MessageId`) to `shared/pedidos_shared/src/pedidos_shared/clients/sqs.py`
- [X] T008 [P] Add unit/integration tests for `send_raw` and `receive_raw_with_receipt` against a real Ministack queue in `shared/pedidos_shared/tests/clients/test_sqs.py`
- [X] T009 Implement file-consumer settings loading with required queue/bucket/table settings in `services/file-consumer/src/file_consumer/config.py`
- [X] T010 Implement the raw SQS consumer loop using `receive_raw_with_receipt`/`send_raw`, with `is_message_processed`/`mark_message_processed` keyed by the native SQS `MessageId` (check before the handler, mark only after success or business rejection) in `services/file-consumer/src/file_consumer/adapters/worker_loop.py`
- [X] T011 Implement the composition root with a `/health` server on port 8083 and a consumer thread for `s3_notifications_queue` in `services/file-consumer/src/file_consumer/main.py`

**Checkpoint**: Foundation ready. User stories can now proceed in priority order or in parallel where marked.

---

## Phase 3: User Story 1 - Processar arquivo batch valido linha a linha (Priority: P1) MVP

**Goal**: Read a valid positional file notified via S3, parse it, and publish one `pedido_lines_queue` message per order (`SOLICITAR`, `EDITAR`, or `CANCELAR`).

**Independent Test**: Upload a valid positional file with header, 1+ orders (with their items), and a consistent trailer; verify one `pedido_lines_queue` message per order, each with correct `source_file`, `line_number`, `operation`, `order_id`, and `parsed`.

### Tests for User Story 1

- [X] T012 [P] [US1] Add unit tests for `montar_linha_pedido` covering `SOLICITAR` (`order_id=None`, `parsed` shaped like `solicitar_pedido_queue`), `EDITAR` (`order_id` filled, `parsed` shaped like `editar_pedido_queue`), and `CANCELAR` (`order_id` filled, `parsed={"reason": "Cancelamento via arquivo batch"}`, items ignored) in `services/file-consumer/tests/test_mensagens.py`
- [X] T013 [P] [US1] Add unit tests for `extrair_notificacoes` covering a real `Records` payload (bucket/key extracted, key URL-decoded) and an `s3:TestEvent` payload (empty list, no error) in `services/file-consumer/tests/test_notificacoes_s3.py`
- [X] T014 [P] [US1] Add a handler happy-path test with a multi-order valid file that mocks `S3Client`/`SqsClient` and captures the messages published to `pedido_lines_queue` in `services/file-consumer/tests/test_processar_notificacao.py`

### Implementation for User Story 1

- [X] T015 [US1] Implement `montar_linha_pedido(source_file, line_number, order, raw_line)` in `services/file-consumer/src/file_consumer/domain/mensagens.py`
- [X] T016 [US1] Implement `extrair_notificacoes(body)` returning an empty list for payloads without `Records` in `services/file-consumer/src/file_consumer/adapters/notificacoes_s3.py`
- [X] T017 [US1] Implement happy-path orchestration (extract notifications, fetch file via `S3Client.get_object`, `parse_file`, publish one message per valid order) in `services/file-consumer/src/file_consumer/handlers/processar_notificacao.py`

**Checkpoint**: US1 processes a fully valid file end to end independently.

---

## Phase 4: User Story 2 - Rejeitar arquivo inteiro estruturalmente invalido (Priority: P1)

**Goal**: Reject a structurally invalid file (missing header/trailer, divergent trailer counters) with zero messages published.

**Independent Test**: Upload a file without a trailer, or with divergent trailer counters; verify no `pedido_lines_queue` message is published and the rejection reason is logged.

### Tests for User Story 2

- [X] T018 [P] [US2] Add handler tests asserting that an `ArquivoInvalidoError` from `parse_file` results in zero published messages, a logged rejection reason, and the SQS message still being acknowledged (business rejection, not a technical failure) in `services/file-consumer/tests/test_processar_notificacao.py`

### Implementation for User Story 2

- [X] T019 [US2] Catch `ArquivoInvalidoError` around the `parse_file` call, log the rejection with `source_file`, and return without publishing or raising in `services/file-consumer/src/file_consumer/handlers/processar_notificacao.py`

**Checkpoint**: US2 rejects structurally invalid files without blocking the queue.

---

## Phase 5: User Story 3 - Rejeitar pedido ou linha individualmente sem interromper o arquivo (Priority: P1)

**Goal**: When only some lines/orders in an otherwise valid file are invalid, publish messages for the valid orders and log the rest without stopping.

**Independent Test**: Upload a file with 3 valid orders and 1 with a divergent `item_count`; verify 3 messages are published and the invalid order is logged without a message.

### Tests for User Story 3

- [X] T020 [P] [US3] Add handler tests for a file with valid and invalid orders mixed, asserting messages are published only for the valid orders and each `ParsedFile.errors` entry is logged with its `line_number` in `services/file-consumer/tests/test_processar_notificacao.py`

### Implementation for User Story 3

- [X] T021 [US3] Iterate `ParsedFile.errors` and log each one (with `source_file` and the line number embedded in the message) alongside publishing a message per entry in `ParsedFile.orders`, in `services/file-consumer/src/file_consumer/handlers/processar_notificacao.py`

**Checkpoint**: US3 tolerates individually invalid lines/orders while still processing the rest of the file.

---

## Phase 6: User Story 4 - Preservar disponibilidade diante de falha tecnica de armazenamento (Priority: P2)

**Goal**: Avoid publishing a business decision when S3 is temporarily unavailable while fetching the notified file.

**Independent Test**: Simulate an S3 failure during `get_object`; verify no response is published and the original notification is not deleted or marked as processed.

### Tests for User Story 4

- [X] T022 [P] [US4] Add handler tests proving an `S3Client.get_object` exception propagates out of the handler instead of being treated as `ArquivoInvalidoError` in `services/file-consumer/tests/test_processar_notificacao.py`
- [X] T023 [P] [US4] Add worker loop tests proving technical exceptions do not delete or mark the notification as processed in `services/file-consumer/tests/test_worker_loop.py`

### Implementation for User Story 4

- [X] T024 [US4] Ensure `S3Client.get_object` failures are not caught alongside `ArquivoInvalidoError` in `services/file-consumer/src/file_consumer/handlers/processar_notificacao.py`
- [X] T025 [US4] Ensure the worker loop logs technical failures but does not acknowledge or mark the notification in `services/file-consumer/src/file_consumer/adapters/worker_loop.py`

**Checkpoint**: US4 preserves correctness under storage instability by letting SQS redrive handle retries.

---

## Phase 7: User Story 5 - Reprocessar a mesma notificacao sem duplicar pedidos (Priority: P3)

**Goal**: Guarantee idempotent handling of duplicated `s3_notifications_queue` deliveries by the native SQS `MessageId`.

**Independent Test**: Publish or process the same S3 notification message twice and verify the orders from that file only generate `pedido_lines_queue` messages once.

### Tests for User Story 5

- [X] T026 [P] [US5] Add duplicate-message unit tests for `is_message_processed` short-circuit behavior (raw loop, native `MessageId`) in `services/file-consumer/tests/test_worker_loop.py`
- [X] T027 [US5] Add a Ministack integration test that uploads a real file, processes its notification twice, and asserts `pedido_lines_queue` receives messages for its orders only once in `services/file-consumer/tests/test_idempotencia.py`

### Implementation for User Story 5

- [X] T028 [US5] Complete duplicate-message acknowledgement without handler execution in `services/file-consumer/src/file_consumer/adapters/worker_loop.py`

**Checkpoint**: US5 prevents duplicate order-line messages across notification redelivery.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Complete service readiness, documentation, and verification required by the constitution.

- [X] T029 [P] Add health endpoint tests for `GET /health` success and unknown path 404 in `services/file-consumer/tests/test_health.py`
- [X] T030 [P] Add README examples for local run, `GET http://localhost:8083/health`, `make seed-file`, unit tests, and integration tests in `services/file-consumer/README.md`
- [X] T031 Run `uv run --package file-consumer pytest services/file-consumer/tests -v` and `uv run --package pedidos-shared pytest shared/pedidos_shared/tests -v`, fixing any failures
- [X] T032 Run `uv run --package file-consumer ruff check/format` and `uv run --package pedidos-shared ruff check/format` on the touched paths, fixing any issues
- [X] T033 Validate `docker compose -f infra/docker-compose.yml up -d` starts `file-consumer` after bootstrap and fix service wiring in `infra/docker-compose.yml`
- [X] T034 Execute the manual quickstart validation scenarios (including `infra/bootstrap/seed_file.py`) and record any corrections needed in `specs/007-file-consumer/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion. Blocks all user stories. Includes the `shared/pedidos_shared` fixes (T005-T008), which must land before any user story test can rely on `ParsedFile.errors` or the raw `SqsClient` methods.
- **User Stories (Phase 3+)**: Depend on Foundational completion.
- **Polish (Phase 8)**: Depends on desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2. Provides the parsing/publishing path reused by later stories.
- **US2 (P1)**: Can start after Phase 2; touches the same handler file as US1, so should follow it in practice.
- **US3 (P1)**: Can start after Phase 2; also touches the same handler file as US1/US2.
- **US4 (P2)**: Can start after Phase 2. Validates handler/worker-loop technical-failure behavior.
- **US5 (P3)**: Depends on the worker-loop foundation from Phase 2; benefits from US1 existing so the integration test has a real success path to duplicate.

### Within Each User Story

- Write tests first and confirm they fail before implementation.
- Domain/adapter functions before handler integration.
- Handler behavior before integration tests.
- Complete each checkpoint before moving to the next priority when working sequentially.

---

## Parallel Opportunities

- T003 can run in parallel with T002 because README work does not modify package metadata.
- T007 and T008 can run in parallel with T005/T006 because they touch independent shared modules (`clients/sqs.py` vs. `file_layout.py`).
- US1 tests T012, T013, and T014 can run in parallel; T015 and T016 can run in parallel before T017 integrates them.
- US4 tests T022 and T023 can run in parallel because they cover different modules.
- Polish tasks T029 and T030 can run in parallel after main behavior exists.

---

## Parallel Example: User Story 1

```bash
Task: "Add unit tests for montar_linha_pedido in services/file-consumer/tests/test_mensagens.py"
Task: "Add unit tests for extrair_notificacoes in services/file-consumer/tests/test_notificacoes_s3.py"
Task: "Add a handler happy-path test in services/file-consumer/tests/test_processar_notificacao.py"
```

## Parallel Example: Foundational shared fixes

```bash
Task: "Redesign parse_file for partial tolerance in shared/pedidos_shared/src/pedidos_shared/file_layout.py"
Task: "Add send_raw/receive_raw_with_receipt to SqsClient in shared/pedidos_shared/src/pedidos_shared/clients/sqs.py"
```

---

## Implementation Strategy

### MVP First (P1 Stories)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (including the shared `file_layout`/`SqsClient` fixes).
3. Complete US1, US2, and US3 because all are P1 and together define a correct file-processing
   decision (valid orders published, invalid file rejected, invalid lines/orders skipped).
4. Stop and validate the MVP with unit tests plus a local queue flow using
   `s3_notifications_queue` and `pedido_lines_queue`.

### Incremental Delivery

1. Deliver Setup + Foundational so the worker can start and consume real S3 notifications.
2. Deliver US1 to prove valid-file processing end to end.
3. Deliver US2 and US3 to cover the core rejection paths (whole file vs. individual line/order).
4. Deliver US4 to harden storage-failure behavior.
5. Deliver US5 to guarantee duplicate-notification safety.
6. Finish Polish verification before PR.

### MVP Scope

The suggested MVP is Phases 1-5: Setup, Foundational, US1, US2, and US3. These P1 stories provide
a complete file consumer for valid processing, whole-file rejection, and per-line/per-order
rejection.

---

## Notes

- `[P]` tasks touch different files or independent modules and can be run in parallel after their
  phase prerequisites.
- `[US#]` labels map tasks to the user stories in `spec.md`.
- The service must never write to `orders` or call the API Gateway; only `pedido_lines_queue` is
  an output.
- Technical S3 failures must remain exceptions so the worker loop avoids ack and
  processed-message marking.
- `s3_notifications_queue` and `pedido_lines_queue` never use `MessageEnvelope` (research.md #2) —
  do not attempt to parse/build one for either queue.
- Avoid logging raw `customer_document`; use masking from `pedidos_shared` if document data appears
  in logs.
