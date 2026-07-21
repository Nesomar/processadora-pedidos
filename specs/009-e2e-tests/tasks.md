# Tasks: Suite de Testes End-to-End

**Input**: Design documents from `/specs/009-e2e-tests/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `quickstart.md`

**Tests**: This feature *is* the test suite — there is no separate "tests for the tests" layer. Each user story's task is the scenario file itself, run against the real environment per `quickstart.md`.

**Organization**: Tasks are grouped by user story so each scenario can be written and validated independently once the shared utilities and environment check exist.

## Phase 1: Setup (Shared Utilities)

**Purpose**: Add the standalone test helpers `tests/e2e/` needs — no `pyproject.toml`, this is not a workspace member (research.md #1).

- [X] T001 [P] Create `poll_until(fn, timeout=30.0, interval=0.5, description="") -> Any` in `tests/e2e/_poll.py`, raising `AssertionError` with `description` and the last observed value on timeout (research.md #2, FR-003/FR-006)
- [X] T002 [P] Create `montar_arquivo_valido(customer_id, product_id, quantity) -> bytes` (positional file builder: header + 1 `SOLICITAR` order + 1 item + trailer) in `tests/e2e/_file_builder.py` (research.md #4, FR-004)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Environment-availability check and shared fixtures every scenario needs.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Implement `tests/e2e/conftest.py`: a session-scoped `autouse` fixture that `GET /health`s all 6 services (short timeout) and calls `pytest.exit` naming the unreachable service if any fails (research.md #3, FR-006/SC-004); plus `api_gateway` (`httpx.Client`), `s3_client` (`pedidos_shared.S3Client`), and `settings` (`pedidos_shared.Settings`) fixtures

**Checkpoint**: Foundation ready. Scenario files can now be written in priority order or in parallel where marked.

---

## Phase 3: User Story 1 - Confirmar que um pedido online valido chega a completo (Priority: P1) MVP

**Goal**: Prove the full online pipeline (validation, totals, invoice) reaches `COMPLETED`.

**Independent Test**: Run this scenario alone against a live environment; it fails if the created order does not reach `COMPLETED` with an invoice key within 30s.

- [X] T004 [US1] Implement `test_online_happy_path.py`: `POST /pedidos` with a valid CPF and an item above `minimumOrderQuantity` (product 1, quantity 50, research.md #5), then `poll_until` `GET /pedidos/{order_id}` shows `status="COMPLETED"` with `invoice_s3_key` set and enriched item/totals fields populated, in `tests/e2e/test_online_happy_path.py`

**Checkpoint**: US1 proves the main online success path independently.

---

## Phase 4: User Story 2 - Confirmar que um pedido invalido e reprovado com motivo (Priority: P1)

**Goal**: Prove the online rejection path reaches `REJECTED` with a reason.

**Independent Test**: Run this scenario alone; it fails if the order does not reach `REJECTED` with a non-empty reason within 30s.

- [X] T005 [US2] Implement `test_business_rejection.py`: `POST /pedidos` with an invalid CPF (`11111111111`, research.md #5), then `poll_until` `GET /pedidos/{order_id}` shows `status="REJECTED"` with a non-empty `status_reason`, in `tests/e2e/test_business_rejection.py`

**Checkpoint**: US2 proves the rejection path independently of US1.

---

## Phase 5: User Story 3 - Confirmar que o pipeline de arquivo em lote cria o pedido (Priority: P1)

**Goal**: Prove the batch entry point (File Consumer → Lambda Line Processor → API Gateway → Order Processor) creates an order.

**Independent Test**: Run this scenario alone; it fails if no order with the uploaded `customer_id` and `channel="BATCH"` appears within the timeout.

- [X] T006 [US3] Implement `test_batch_happy_path.py`: build a valid file with `montar_arquivo_valido` using a unique `customer_id`, upload it via `s3_client.put_object` to `uploads/`, then `poll_until` `GET /pedidos?customerId=...` returns exactly one order with `channel="BATCH"`, `source_file`, and `source_line` set, in `tests/e2e/test_batch_happy_path.py`

**Checkpoint**: US3 proves the batch pipeline end to end, independent of US1/US2.

---

## Phase 6: User Story 4 - Confirmar que editar um pedido reflete os novos dados (Priority: P2)

**Goal**: Prove editing an existing order updates its data and re-runs validation.

**Independent Test**: Run this scenario alone; it fails if the edited order does not reflect the new items after reprocessing.

- [X] T007 [US4] Implement `test_editar_pedido.py`: create an order (`POST /pedidos`), wait for its first cycle to settle, then `PUT /pedidos/{order_id}` with different items and `poll_until` `GET /pedidos/{order_id}` reflects the new items after a new validation cycle, in `tests/e2e/test_editar_pedido.py`

**Checkpoint**: US4 proves the edit path independently.

---

## Phase 7: User Story 5 - Confirmar que cancelar um pedido o leva a cancelado (Priority: P2)

**Goal**: Prove cancelling an existing order reaches `CANCELLED`.

**Independent Test**: Run this scenario alone; it fails if the order does not reach `CANCELLED` within the timeout.

- [X] T008 [US5] Implement `test_cancelar_pedido.py`: create an order (`POST /pedidos`), then `POST /pedidos/{order_id}/cancelamento` and `poll_until` `GET /pedidos/{order_id}` shows `status="CANCELLED"`, in `tests/e2e/test_cancelar_pedido.py`

**Checkpoint**: US5 proves the cancellation path independently.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verify the suite as a whole and keep root documentation accurate.

- [X] T009 Run `make e2e` against a live `docker-compose` stack and confirm all 5 scenarios pass consistently (SC-001); fix any flakiness found
- [X] T010 Validate SC-004 by stopping one service (e.g. `docker compose -f infra/docker-compose.yml stop api-gateway`), confirming `make e2e` fails within seconds naming the unreachable service, then restarting it; record any correction needed in `specs/009-e2e-tests/quickstart.md`
- [X] T011 [P] Run `uv run --package pedidos-shared ruff check tests/e2e` and `uv run --package pedidos-shared ruff format --check tests/e2e` (shared style config, research.md #1), fixing any issues
- [X] T012 [P] Update `README.md` and `CLAUDE.md` to mention `tests/e2e/`/`make e2e` now exist, consistent with the same accuracy pass done after `008-lambda-line-processor`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (uses nothing from it directly, but conftest.py is the shared blocker for every scenario).
- **User Stories (Phase 3+)**: Depend on Foundational completion.
- **Polish (Phase 8)**: Depends on all desired scenarios being complete.

### User Story Dependencies

- **US1/US2/US3 (P1)**: Each can start after Phase 2, independent of one another (different files, different orders per run).
- **US4/US5 (P2)**: Each can start after Phase 2, independent of US1-US3 and of each other.

### Within Each User Story

- Each scenario file is self-contained: create data via a real entry point, poll for the expected
  outcome, assert. No shared mutable state between scenario files (FR-004).

---

## Parallel Opportunities

- T001 and T002 can run in parallel (independent utility modules).
- T004, T005, T006, T007, and T008 can all be written in parallel once T003 (conftest) exists —
  each is a self-contained scenario file with its own unique test data.
- T011 and T012 can run in parallel in Polish.

---

## Parallel Example: Setup

```bash
Task: "Create poll_until in tests/e2e/_poll.py"
Task: "Create montar_arquivo_valido in tests/e2e/_file_builder.py"
```

## Parallel Example: Scenarios (after Foundational)

```bash
Task: "Implement test_online_happy_path.py"
Task: "Implement test_business_rejection.py"
Task: "Implement test_batch_happy_path.py"
Task: "Implement test_editar_pedido.py"
Task: "Implement test_cancelar_pedido.py"
```

---

## Implementation Strategy

### MVP First (P1 Stories)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete US1, US2, and US3 — all P1, together proving both entry points (online and batch)
   and both outcomes (success and business rejection).
4. Run `make e2e` and confirm all three pass against a live environment.

### Incremental Delivery

1. Deliver Setup + Foundational so the environment check and utilities exist.
2. Deliver US1 to prove the main online success path.
3. Deliver US2 and US3 to cover rejection and the batch entry point.
4. Deliver US4 and US5 to complete order-lifecycle coverage.
5. Finish Polish verification before PR.

### MVP Scope

The suggested MVP is Phases 1-5: Setup, Foundational, US1, US2, and US3. These P1 stories prove
both entry points and both outcomes of the pipeline.

---

## Notes

- `[P]` tasks touch different files and can be run/written in parallel after their phase
  prerequisites.
- `[US#]` labels map tasks to the user stories in `spec.md`.
- The suite never writes to `orders` or any queue directly (FR-007) — every scenario enters
  through a real entry point (HTTP or S3 upload) and only reads back through `GET` endpoints.
- Every scenario must use a unique identifier (UUID-based `customer_id`/document where
  applicable) so repeated runs against the same environment never collide (FR-004, SC-003).
