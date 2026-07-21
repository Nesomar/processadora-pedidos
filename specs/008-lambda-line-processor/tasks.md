# Tasks: Lambda Line Processor

**Input**: Design documents from `/specs/008-lambda-line-processor/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/lambda-line-processor-calls.md`, `quickstart.md`, `.specify/memory/constitution.md` (v1.0.2)

**Tests**: Included because `spec.md`, `research.md`, and the project constitution require unit tests plus at least one Ministack integration test.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently after the shared foundation is complete. Unlike `007-file-consumer`, no `shared/pedidos_shared/` changes are needed — all raw SQS/idempotency infrastructure this feature needs already exists.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the `lambda-line-processor` service skeleton and local runtime wiring.

- [X] T001 Create the lambda-line-processor package structure with `services/lambda-line-processor/src/lambda_line_processor/__init__.py`, `services/lambda-line-processor/src/lambda_line_processor/domain/__init__.py`, `services/lambda-line-processor/src/lambda_line_processor/adapters/__init__.py`, `services/lambda-line-processor/src/lambda_line_processor/handlers/__init__.py`, and `services/lambda-line-processor/tests/conftest.py`
- [X] T002 Create the service package metadata with Python 3.12, `pedidos-shared`, `httpx`, `pytest`, and `ruff` in `services/lambda-line-processor/pyproject.toml`
- [X] T003 [P] Create the initial service README with consumed queue, environment variables, health endpoint, and test commands in `services/lambda-line-processor/README.md`
- [X] T004 Add `API_GATEWAY_BASE_URL=http://localhost:8000` to `.env.example`, and add the `lambda-line-processor` container service with port `8084:8084`, `API_GATEWAY_BASE_URL=http://api-gateway:8000`, Ministack endpoint, `.env`, and `uv run --package lambda-line-processor python -m lambda_line_processor.main` command (depending on `api-gateway` in addition to `bootstrap`) in `infra/docker-compose.yml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core service plumbing required by all user stories. No `shared/pedidos_shared/` changes needed — reuses `SqsClient.send_raw`/`receive_raw_with_receipt` and `is_message_processed`/`mark_message_processed` as-is from `007-file-consumer`.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Implement `LambdaLineProcessorSettings(Settings)` with a required `api_gateway_base_url: str` field (same pattern as `catalog_products_base_url` in `005-order-validator`) in `services/lambda-line-processor/src/lambda_line_processor/config.py`
- [X] T006 Implement the raw SQS consumer loop (`receive_raw_with_receipt`/`send_raw`-free, since this service never publishes), with `is_message_processed`/`mark_message_processed` keyed by the native SQS `MessageId` (check before the handler, mark only after success or business rejection) in `services/lambda-line-processor/src/lambda_line_processor/adapters/worker_loop.py`
- [X] T007 Implement the composition root with a `/health` server on port 8084 and a consumer thread for `pedido_lines_queue` in `services/lambda-line-processor/src/lambda_line_processor/main.py`

**Checkpoint**: Foundation ready. User stories can now proceed in priority order or in parallel where marked.

---

## Phase 3: User Story 1 - Encaminhar linha de pedido valida para o API Gateway (Priority: P1) MVP

**Goal**: Translate a valid `pedido_lines_queue` message into the matching API Gateway HTTP call and confirm the message on success.

**Independent Test**: Publish a message with `operation="SOLICITAR"` and a complete `parsed` body; verify `POST /pedidos` is called with that body and, on `2xx`, the original message is not redelivered.

### Tests for User Story 1

- [X] T008 [P] [US1] Add unit tests for `montar_chamada` covering `SOLICITAR` (`POST /pedidos`), `EDITAR` (`PUT /pedidos/{order_id}`), `CANCELAR` (`POST /pedidos/{order_id}/cancelamento`), and `ComandoInvalidoError` for an unknown `operation` or missing `order_id` on `EDITAR`/`CANCELAR` in `services/lambda-line-processor/tests/test_chamada_api.py`
- [X] T009 [P] [US1] Add unit tests for the API Gateway client asserting it returns the `httpx.Response` unchanged regardless of status code (the handler decides, not the client) in `services/lambda-line-processor/tests/test_api_gateway_client.py`
- [X] T010 [P] [US1] Add a handler happy-path test that mocks the API Gateway client and asserts a `2xx` response results in no exception and no further action in `services/lambda-line-processor/tests/test_processar_linha.py`

### Implementation for User Story 1

- [X] T011 [US1] Implement `montar_chamada(body) -> tuple[str, str, dict]` and `ComandoInvalidoError` in `services/lambda-line-processor/src/lambda_line_processor/domain/chamada_api.py`
- [X] T012 [US1] Implement `chamar(client, method, path, body) -> httpx.Response` using `httpx.Client` with a 5s timeout and a short retry (2 attempts) for connection/timeout errors only in `services/lambda-line-processor/src/lambda_line_processor/adapters/api_gateway_client.py`
- [X] T013 [US1] Implement happy-path orchestration (`montar_chamada` → `chamar` → treat `< 300` as success) in `services/lambda-line-processor/src/lambda_line_processor/handlers/processar_linha.py`

**Checkpoint**: US1 forwards valid lines to the API Gateway independently.

---

## Phase 4: User Story 2 - Descartar linha com rejeicao de negocio permanente (Priority: P1)

**Goal**: Treat `400`/`404`/`409` responses (and `ComandoInvalidoError`) as permanent business rejections that still confirm the message.

**Independent Test**: Publish a message whose call responds `404` or `409`; verify the original message is not redelivered and the rejection reason is logged.

### Tests for User Story 2

- [X] T014 [P] [US2] Add handler tests asserting `400`/`404`/`409` responses and a `ComandoInvalidoError` (unknown operation, missing `order_id`) all result in a logged rejection and no exception raised (no HTTP call at all for `ComandoInvalidoError`) in `services/lambda-line-processor/tests/test_processar_linha.py`

### Implementation for User Story 2

- [X] T015 [US2] Integrate the permanent-rejection paths (catch `ComandoInvalidoError` before calling the API Gateway; treat `status_code` in `{400, 404, 409}` as a logged rejection) into `services/lambda-line-processor/src/lambda_line_processor/handlers/processar_linha.py`

**Checkpoint**: US2 rejects invalid/refused lines as a permanent business outcome, independent of retries.

---

## Phase 5: User Story 3 - Preservar disponibilidade diante de falha tecnica do API Gateway (Priority: P2)

**Goal**: Avoid publishing a business decision when the API Gateway is unavailable or returns an unexpected error.

**Independent Test**: Simulate a connection error, timeout, or `5xx` from the API Gateway; verify the original message is not confirmed and remains available for retry.

### Tests for User Story 3

- [X] T016 [P] [US3] Add API Gateway client tests for retry-then-propagate behavior on connection/timeout errors in `services/lambda-line-processor/tests/test_api_gateway_client.py`
- [X] T017 [P] [US3] Add worker loop tests proving technical exceptions do not delete or mark the message as processed in `services/lambda-line-processor/tests/test_worker_loop.py`

### Implementation for User Story 3

- [X] T018 [US3] Ensure any `status_code` outside `2xx`/`400`/`404`/`409` (in particular `5xx`) raises instead of being treated as a rejection in `services/lambda-line-processor/src/lambda_line_processor/handlers/processar_linha.py`
- [X] T019 [US3] Ensure the worker loop logs technical failures but does not acknowledge or mark the message in `services/lambda-line-processor/src/lambda_line_processor/adapters/worker_loop.py`

**Checkpoint**: US3 preserves correctness under API Gateway instability by letting SQS redrive handle retries.

---

## Phase 6: User Story 4 - Reprocessar a mesma linha sem duplicar a chamada (Priority: P3)

**Goal**: Guarantee idempotent handling of duplicated `pedido_lines_queue` deliveries by the native SQS `MessageId`.

**Independent Test**: Publish or process the same message twice and verify the API Gateway is called only once.

### Tests for User Story 4

- [X] T020 [P] [US4] Add duplicate-message unit tests for `is_message_processed` short-circuit behavior in `services/lambda-line-processor/tests/test_worker_loop.py`
- [X] T021 [US4] Add a Ministack + real `api-gateway` integration test that sends the same `SOLICITAR` line twice and asserts only one order is created, in `services/lambda-line-processor/tests/test_idempotencia.py`

### Implementation for User Story 4

- [X] T022 [US4] Confirm duplicate-message acknowledgement without handler execution in `services/lambda-line-processor/src/lambda_line_processor/adapters/worker_loop.py`

**Checkpoint**: US4 prevents duplicate API Gateway calls across message redelivery.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Complete service readiness, documentation, and verification required by the constitution.

- [X] T023 [P] Add health endpoint tests for `GET /health` success and unknown path 404 in `services/lambda-line-processor/tests/test_health.py`
- [X] T024 [P] Add README examples for local run, `GET http://localhost:8084/health`, unit tests, and integration tests in `services/lambda-line-processor/README.md`
- [X] T025 Run `uv run --package lambda-line-processor pytest services/lambda-line-processor/tests -v` and fix any failures
- [X] T026 Run `uv run --package lambda-line-processor ruff check/format` and fix any issues
- [X] T027 Validate `docker compose -f infra/docker-compose.yml up -d` starts `lambda-line-processor` after `bootstrap` and `api-gateway`, and fix service wiring in `infra/docker-compose.yml`
- [X] T028 Execute the manual quickstart validation scenarios and record any corrections needed in `specs/008-lambda-line-processor/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion. Blocks all user stories.
- **User Stories (Phase 3+)**: Depend on Foundational completion.
- **Polish (Phase 7)**: Depends on desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2. Provides the call-mapping and HTTP-client path reused by later stories.
- **US2 (P1)**: Can start after Phase 2; touches the same handler file as US1, so should follow it in practice.
- **US3 (P2)**: Can start after Phase 2. Validates client/worker-loop technical-failure behavior; touches the same files as US1.
- **US4 (P3)**: Depends on the worker-loop foundation from Phase 2; benefits from US1 existing so the integration test has a real success path to duplicate.

### Within Each User Story

- Write tests first and confirm they fail before implementation.
- Domain functions before adapter/handler integration.
- Adapter behavior before handler behavior that depends on it.
- Complete each checkpoint before moving to the next priority when working sequentially.

---

## Parallel Opportunities

- T003 can run in parallel with T002 because README work does not modify package metadata.
- US1 tests T008, T009, and T010 can run in parallel; T011 and T012 touch independent modules and can run in parallel before T013 integrates them.
- US3 tests T016 and T017 can run in parallel because they cover different modules.
- US4 unit test T020 can run before the integration test T021.
- Polish tasks T023 and T024 can run in parallel after main behavior exists.

---

## Parallel Example: User Story 1

```bash
Task: "Add unit tests for montar_chamada in services/lambda-line-processor/tests/test_chamada_api.py"
Task: "Add unit tests for the API Gateway client in services/lambda-line-processor/tests/test_api_gateway_client.py"
Task: "Add a handler happy-path test in services/lambda-line-processor/tests/test_processar_linha.py"
```

---

## Implementation Strategy

### MVP First (P1 Stories)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete US1 and US2 because both are P1 and together define a correct forwarding decision
   (success or permanent business rejection).
4. Stop and validate the MVP with unit tests plus a local queue flow using `pedido_lines_queue`
   and a real `api-gateway`.

### Incremental Delivery

1. Deliver Setup + Foundational so the worker can start and consume the queue.
2. Deliver US1 to prove successful forwarding to the API Gateway.
3. Deliver US2 to cover the permanent-rejection path.
4. Deliver US3 to harden API-Gateway-failure behavior.
5. Deliver US4 to guarantee duplicate-message safety.
6. Finish Polish verification before PR.

### MVP Scope

The suggested MVP is Phases 1-4: Setup, Foundational, US1, and US2. These P1 stories provide a
complete forwarder for valid lines and a safe rejection path for permanently invalid ones.

---

## Notes

- `[P]` tasks touch different files or independent modules and can be run in parallel after their
  phase prerequisites.
- `[US#]` labels map tasks to the user stories in `spec.md`.
- The service must never write to `orders` or publish to any queue; its only output is the HTTP
  call to the API Gateway (constitution I.1 v1.0.2 exception).
- Technical API Gateway failures must remain exceptions so the worker loop avoids ack and
  processed-message marking.
- `pedido_lines_queue` never uses `MessageEnvelope` — do not attempt to parse/build one.
- Avoid logging raw `customer_document`; use masking from `pedidos_shared` if document data
  appears in logs.
