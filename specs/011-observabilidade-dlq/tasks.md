# Tasks: Observabilidade e Reprocessamento de DLQ

**Input**: Design documents from `/specs/011-observabilidade-dlq/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/dlq-endpoints.md`, `quickstart.md`, `.specify/memory/constitution.md` (v1.0.2)

**Tests**: Incluídos — a constitution (VII.5) exige cobertura de regras de negócio e caminhos de erro; o `plan.md` prevê testes unitários (SQS mockado) e de integração (Ministack).

**Organization**: Tarefas agrupadas por user story. Extensão do `api-gateway` e do `SqsClient` existentes; nenhuma fila, worker, tabela ou variável de ambiente nova.

## Phase 1: Setup

Nenhuma tarefa — serviço, dependências e DLQs (bootstrap) já existem.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Peças compartilhadas necessárias a todas as stories.

**CRITICAL**: Nenhuma story começa antes desta fase.

- [X] T001 Em `shared/pedidos_shared/src/pedidos_shared/clients/sqs.py`, adicionar `SqsClient.queue_url(name) -> str` (via `get_queue_url`; `QueueDoesNotExist` propaga)
- [X] T002 [P] Teste de `queue_url` (devolve a URL; erro propaga) em `shared/pedidos_shared/tests/clients/test_sqs.py`
- [X] T003 [P] Criar `services/api-gateway/src/api_gateway/domain/dlq.py` (funções puras, sem I/O): constante `FILAS` com as 9 filas de `docs/01-dominio-e-contratos.md` §4, `nome_dlq(fila) -> str` (`{fila}_dlq`), `identificar(body: dict) -> dict` (envelope → `order_id`/`correlation_id`; evento S3 `Records[0].s3.object.key` → `source_file`; linha de lote `source_file`+`line_number` → `source_file`/`source_line`; desconhecido → tudo `None`, nunca levanta) e `mascarar(valor)` (percorre dict/list e aplica `pedidos_shared.mask_document` a toda chave `customer_document`)
- [X] T004 [P] Teste das funções puras (as 9 filas, `nome_dlq`, os 3 formatos de corpo + desconhecido, máscara em qualquer nível, sem alterar o original) em `services/api-gateway/tests/test_dlq_domain.py`
- [X] T005 Em `services/api-gateway/src/api_gateway/schemas.py`, adicionar `DlqResumo`, `ResumoDlqsResponse`, `MensagemDlq`, `ListaMensagensDlqResponse`, `ReprocessamentoRequest` (`message_id: str | None = None`) e `ReprocessamentoResponse` conforme `data-model.md`

**Checkpoint**: `uv run --all-packages python -m pytest shared services/api-gateway` verde.

---

## Phase 3: User Story 1 - Saber se há mensagens paradas em DLQ (Priority: P1) 🎯 MVP

**Goal**: `GET /dlqs` devolve a contagem de mensagens de cada uma das 9 DLQs.

**Independent Test**: Com uma mensagem numa DLQ, `GET /dlqs` mostra `1` naquela fila e `0` nas demais.

### Tests for User Story 1

- [X] T006 [P] [US1] Teste de `SqsClient.message_count` (soma visíveis + em voo + atrasadas a partir de `GetQueueAttributes`) em `shared/pedidos_shared/tests/clients/test_sqs.py`
- [X] T007 [P] [US1] Teste da rota (SQS mockado): `200` com as 9 filas em ordem fixa, contagens corretas, `dlq` = `{fila}_dlq`; `502` quando o SQS falha; log JSON com fila e quantidade em `services/api-gateway/tests/test_dlqs.py`
- [X] T008 [P] [US1] Teste de integração contra Ministack (mensagem enviada à DLQ → `GET /dlqs` conta `1`; as demais `0`; confirmar se a contagem é imediata) em `services/api-gateway/tests/test_dlqs.py`

### Implementation for User Story 1

- [X] T009 [US1] Em `shared/pedidos_shared/src/pedidos_shared/clients/sqs.py`, adicionar `SqsClient.message_count(queue_url) -> int`
- [X] T010 [US1] Criar `services/api-gateway/src/api_gateway/handlers/resumo_dlqs.py` (`GET /dlqs`: para cada fila de `FILAS`, `queue_url(nome_dlq)` + `message_count`; falha técnica → log JSON e `HTTPException(502)`)
- [X] T011 [US1] Registrar o router em `services/api-gateway/src/api_gateway/main.py`

**Checkpoint**: US1 funcional e testável sozinha.

---

## Phase 4: User Story 2 - Inspecionar uma mensagem em DLQ (Priority: P2)

**Goal**: `GET /dlqs/{fila}/mensagens` lista as mensagens sem consumi-las, ligando cada uma ao pedido afetado.

**Independent Test**: Com uma mensagem na DLQ, listar duas vezes devolve a mesma mensagem, com `order_id`/`correlation_id` e documento mascarado.

### Tests for User Story 2

- [X] T012 [P] [US2] Teste de `SqsClient.peek` (recebe com 1 s, libera na hora e devolve `SentTimestamp`; devolve `MessageId`, `Body`, `SentTimestamp`) em `shared/pedidos_shared/tests/clients/test_sqs.py`
- [X] T013 [P] [US2] Testes da rota em `services/api-gateway/tests/test_dlqs.py`: `200` com `order_id`/`correlation_id` e `customer_document` mascarado; deduplicação por `message_id` entre rodadas; `limit` respeitado e `has_more`; corpo não-JSON devolvido como texto truncado; `404` para fila fora das 9; `400` para `limit` fora de 1–50; resposta e log sem documento em claro
- [X] T014 [P] [US2] Teste de integração contra Ministack (duas listagens seguidas devolvem a mesma mensagem e a contagem não muda) em `services/api-gateway/tests/test_dlqs.py`

### Implementation for User Story 2

- [X] T015 [US2] Em `shared/pedidos_shared/src/pedidos_shared/clients/sqs.py`, adicionar `SqsClient.peek(queue_url, max_messages=10) -> list[dict]`
- [X] T016 [US2] Criar `services/api-gateway/src/api_gateway/handlers/listar_mensagens_dlq.py` (`GET /dlqs/{fila}/mensagens?limit=10`: valida `fila` ∈ `FILAS` (404), até 5 rodadas de `peek` deduplicando por `MessageId`, `identificar` + `mascarar`, `sent_at` ISO 8601 UTC, `has_more` pela contagem; corpo não-JSON truncado a 2 000 caracteres; log JSON sem documento)
- [X] T017 [US2] Registrar o router em `services/api-gateway/src/api_gateway/main.py`

**Checkpoint**: US1 e US2 funcionam de forma independente.

---

## Phase 5: User Story 3 - Reprocessar mensagens da DLQ (Priority: P3)

**Goal**: `POST /dlqs/{fila}/reprocessamento` devolve à fila de origem a DLQ inteira ou uma mensagem, sem nunca perder mensagem.

**Independent Test**: Com 2 mensagens na DLQ, reprocessar uma pelo `message_id` move só ela; reprocessar sem corpo move a restante; uma terceira chamada devolve `0`.

### Tests for User Story 3

- [X] T018 [P] [US3] Testes de `SqsClient.receive_raw_messages` (devolve `MessageId`, `Body`, `ReceiptHandle`, visibilidade padrão) e `send_body` (reenvia o corpo exato) em `shared/pedidos_shared/tests/clients/test_sqs.py`
- [X] T019 [P] [US3] Testes da rota em `services/api-gateway/tests/test_dlqs.py`: DLQ inteira (`reprocessed` = N, corpo reenviado idêntico à fila de origem, `delete` só depois do `send`); por `message_id` (só ela se move, as outras ficam); `message_id` inexistente → `404` sem mover nada; DLQ vazia → `200` com `0`; fila fora das 9 → `404`; falha no `send` → `502` e nenhuma mensagem deletada; falha no `delete` não perde mensagem; log JSON com fila e quantidade
- [X] T020 [P] [US3] Teste de integração contra Ministack (2 mensagens na DLQ → reprocessar uma por `message_id`, depois o restante, depois `0`; a mensagem aparece na fila de origem com o mesmo corpo) em `services/api-gateway/tests/test_dlqs.py`

### Implementation for User Story 3

- [X] T021 [US3] Em `shared/pedidos_shared/src/pedidos_shared/clients/sqs.py`, adicionar `SqsClient.receive_raw_messages(queue_url, max_messages=10) -> list[dict]` e `SqsClient.send_body(queue_url, body: str) -> str`
- [X] T022 [US3] Criar `services/api-gateway/src/api_gateway/handlers/reprocessar_dlq.py` (`POST /dlqs/{fila}/reprocessamento`, corpo opcional `ReprocessamentoRequest`: valida `fila` (404); lotes de 10 recebidos da DLQ, para cada mensagem `send_body` na fila de origem e só então `delete` na DLQ; pára ao esvaziar ou após 20 rodadas sem progresso; com `message_id`, procura o `MessageId` em rodadas e devolve `404` se não achar; falha técnica → log JSON + `502`, mensagens ainda não movidas permanecem na DLQ)
- [X] T023 [US3] Registrar o router em `services/api-gateway/src/api_gateway/main.py`

**Checkpoint**: Todas as stories independentes.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T024 [P] Atualizar `README.md` (seção operacional "Observando e reprocessando DLQs" com os 3 `curl`, aviso de que não há autenticação, e linhas em "Problemas comuns") e `services/api-gateway/README.md` (3 rotas novas na tabela)
- [X] T025 [P] Documentar em `docs/01-dominio-e-contratos.md` §4 que as DLQs são consultáveis via API Gateway (referência ao contrato) e atualizar `CLAUDE.md` com a seção "DLQ operations" (ordem enviar→deletar, receber+liberar (Ministack ignora `VisibilityTimeout=0`), sem autenticação)
- [X] T026 Rodar `uv run --all-packages python -m pytest shared services` com `.env` carregado e Ministack no ar, `uv run ruff check` e `uv run ruff format --check` em `shared/` e `services/api-gateway/`
- [X] T027 Recriar o api-gateway (`docker compose -f infra/docker-compose.yml up -d --force-recreate api-gateway`) e executar os cenários de `specs/011-observabilidade-dlq/quickstart.md`; rodar `make e2e` para garantir que nada regrediu
- [X] T028 Code review (constitution VII, skill `code-review`) com foco em perda de mensagem no reprocessamento (SC-005), somente leitura da listagem (FR-003), vazamento de `customer_document` (FR-004) e não escrita em `orders` (FR-010); corrigir apontamentos antes do PR
- [ ] T029 Abrir PR de `feature/011-observabilidade-dlq` para `develop`

---

## Dependencies & Execution Order

### Phase Dependencies

- Foundational (T001–T005) bloqueia todas as stories.
- US1 → US2 → US3: as três estendem `sqs.py`, `main.py` e `test_dlqs.py`, então são sequenciais na prática.
- Polish depende de US1–US3.

### Within Each Story

- Testes primeiro (devem falhar), depois `SqsClient`, handler e registro do router.
- T009 antes de T010; T015 antes de T016; T021 antes de T022.

### Parallel Opportunities

- T002, T003/T004 em paralelo entre si (arquivos distintos); T005 em paralelo a T003.
- Dentro de cada story, os testes marcados `[P]` (T006–T008, T012–T014, T018–T020); os de `test_dlqs.py` e `test_sqs.py` compartilham arquivo, então escrever em sequência.
- T024 e T025 em paralelo.

## Parallel Example: User Story 1

```text
# Testes juntos:
T006 test_sqs.py (message_count)
T007 test_dlqs.py (rota, mock)
# Depois:
T009 sqs.py message_count  →  T010 resumo_dlqs.py  →  T011 main.py
```

## Implementation Strategy

### MVP First (US1)

1. Foundational (T001–T005).
2. US1 (T006–T011): `GET /dlqs`.
3. Validar com o cenário 1 do `quickstart.md`.

### Incremental Delivery

1. US1 → saber que há mensagens paradas.
2. US2 → saber de qual pedido.
3. US3 → recuperar.
4. Polish (docs, review, PR).

## Notes

- `[P]` = arquivos diferentes e sem dependência pendente; `[US#]` mapeia a story de `spec.md`.
- Nunca deletar da DLQ antes de reenviar com sucesso (FR-007); listar nunca consome (FR-003).
- Nunca logar nem devolver `customer_document` em claro; usar `mask_document` de `pedidos_shared`.
- O api-gateway não escreve em `orders` (FR-010); só o Order Processor muda estado, ao reconsumir.
- Containers montam o código por volume e não têm `--reload`: recriar o serviço depois de editar (T027).
