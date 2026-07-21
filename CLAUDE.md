# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Event-driven order processing system built with a spec-driven workflow (GitHub Spec Kit — see
`.specify/`). Full domain contract, message payloads, DynamoDB schema, positional file layout, and
Ministack setup live in `docs/01-dominio-e-contratos.md` — read it before touching any queue
payload, state transition, or file format. Governance/conventions live in
`.specify/memory/constitution.md` (stack, monorepo layout, git workflow, code design rules,
definition of done) — it takes precedence over anything else in the repo, including this file.

Two entry points converge into the same event-driven pipeline: an HTTP client hitting the API
Gateway directly, and a positional `.txt` file uploaded to S3 (each line becomes an HTTP call via
the batch pipeline).

## Commands

```bash
make up          # docker compose up -d (Ministack + bootstrap + all services)
make down        # docker compose down
make bootstrap   # (re)create queues/tables/bucket against a running Ministack
make test        # uv run --all-packages pytest across shared/, infra/, services/
make e2e         # pytest tests/e2e (no-op until that suite exists)
make seed-file   # generate + upload a sample positional file to uploads/
```

Per-package commands (uv workspace — root `pyproject.toml` lists members under `services/*`,
`shared/pedidos_shared`, `infra/bootstrap`):

```bash
uv sync --package <name> --extra dev        # pull in pytest/ruff for one member
uv sync --all-packages                      # restore the full shared venv after a scoped sync
uv run --package <name> pytest <path> -v    # run one package's tests (or a single test file/node)
uv run --package <name> ruff check <path>
uv run --package <name> ruff format <path>
```

`uv sync --package X` only installs `X`'s own deps into the shared `.venv` — it silently drops
other members' dependencies from the environment. Run `uv sync --all-packages` afterward if you
need another service to import cleanly again.

Bringing up just the infra to poke at it manually:

```bash
docker compose -f infra/docker-compose.yml up -d ministack bootstrap
```

Health checks once a service is running: `curl http://localhost:<port>/health` — ports are
`8000` api-gateway, `8080` order-processor, `8081` order-validator, `8082` pdf-generator, `8083`
file-consumer (each new worker takes the next free port).

## Architecture

### Pipeline

```
[HTTP client] ──────────────┐
                            ▼
[.txt file] → S3 → s3_notifications_queue → File Consumer → pedido_lines_queue → Lambda Line Processor (not yet built)
                                                                                          │
                                                                                          ▼
                                                                                   API Gateway
                                                                                          │
                             ┌─────────────────┬───────────────────┤
                             ▼                 ▼                   ▼
                   solicitar_pedido_q   editar_pedido_q    cancelar_pedido_q
                             └─────────────────┴───────────────────┘
                                               │
                                               ▼
                                   Order Processor (orchestrator)
                                         │              ▲    ▲
                                validar_pedido_q         validar_pedido_response_q
                                         ▼              │    │
                                   Order Validator       │    pdf_response_q
                                                         │              ▲
                                                    pdf_request_q       │
                                                         └──────► PDF Generator → S3 (invoice)
```

Order Processor is the only writer of the `orders` table and the only owner of state transitions
— every other service either validates, renders, or ferries messages, and communicates back only
by publishing to a response queue. No service calls another service directly over HTTP; the one
exception is Order Validator calling the external product catalog (`dummyjson.com`).

### Two queue "dialects"

Most queues carry the common `MessageEnvelope` (`message_id`, `correlation_id`, `order_id`,
`occurred_at`, `payload`) defined in `pedidos_shared.models`. **`s3_notifications_queue`** (native
S3 event JSON) and **`pedido_lines_queue`** (its own flat shape) do not — a `SOLICITAR` line from
a batch file has no `order_id` yet, so it can't fit the envelope's non-optional `order_id: str`.
Consuming/producing on these two queues goes through `SqsClient.receive_raw_with_receipt` /
`send_raw` instead of the typed `receive`/`send`, and idempotency is keyed by the raw SQS
`MessageId` rather than an application-level `message_id` (see `services/file-consumer/`).

### Shared package (`shared/pedidos_shared`)

Single source of truth for message contracts, the `Order`/`OrderStatus` state machine
(`is_valid_transition`), thin sync wrappers over boto3 (`SqsClient`, `DynamoDbClient`, `S3Client`),
idempotency helpers (`is_message_processed`/`mark_message_processed`, keyed by any string id +
consumer name), structured JSON logging, `mask_document`, and the positional file parser
(`file_layout.parse_file`). No service redefines any of this locally — extend it here first
(constitution III/VIII) when a new service needs something it doesn't yet expose, the way
`S3Client.put_object` gained `content_type` and `SqsClient` gained the raw send/receive pair.

`file_layout.parse_file` is intentionally tolerant: only a missing/invalid header or trailer, or a
trailer counter that disagrees with the raw count of type-1/type-2 records physically in the file,
raises `ArquivoInvalidoError` (whole file rejected). A single malformed line, an orphan item
record, or one order whose `item_count` doesn't match its actual items is instead collected into
`ParsedFile.errors` and parsing continues — matching `docs/01-dominio-e-contratos.md` §6 exactly.

### Idempotency and technical-vs-business failure

Every consumer follows the same `worker_loop` shape (`adapters/worker_loop.py` in each service):
check `is_message_processed` before running the handler, only call `mark_message_processed` +
delete the SQS message *after* the handler completes without raising. A handler that raises
propagates the exception and leaves the message unacked — that's the only signal for "this was a
transient/technical failure, let SQS redrive retry it." A handler that catches a business-rejection
condition (invalid document, product not found, malformed file) and responds with an error payload
instead of raising is a *permanent* rejection — it still gets acked, because redriving it will
never produce a different outcome. Getting this distinction backwards (marking-before-handling,
or treating a business rejection as an exception) was a real bug caught in review during
`004-order-processor` and is the thing to double-check whenever touching a worker loop.

### Spec-driven workflow

Each feature lives under `specs/NNN-feature-name/` (spec → plan → research → data-model →
contracts → tasks, via the `/speckit-*` skills) and a matching `feature/NNN-feature-name` branch.
`docs/01-dominio-e-contratos.md` is the frozen domain contract every spec references; a spec only
extends it (new error codes, new assumptions) rather than restating it. When a spec's requirements
reveal that already-merged shared code doesn't actually match this contract (as happened with
`parse_file` in `007-file-consumer`), fix the shared code and its tests rather than working around
it in the new service.
