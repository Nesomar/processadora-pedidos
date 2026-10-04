# Tasks: Acesso ao PDF da Nota Fiscal do Pedido

**Input**: Design documents from `/specs/010-acesso-pdf-pedido/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/nota-fiscal-endpoint.md`, `quickstart.md`, `.specify/memory/constitution.md` (v1.0.2)

**Tests**: Incluídos — a constitution (VII.5) exige cobertura de regras de negócio e caminhos de erro; `quickstart.md` prevê testes unitários, de integração (Ministack) e e2e.

**Organization**: Tarefas agrupadas por user story. Extensão do `api-gateway` existente; nenhuma fila, worker ou tabela nova.

## Phase 1: Setup

Nenhuma tarefa — serviço, dependências (`pedidos-shared`, FastAPI) e bucket já existem.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Peças compartilhadas necessárias a todas as stories.

**CRITICAL**: Nenhuma story começa antes desta fase.

- [X] T001 Em `shared/pedidos_shared/src/pedidos_shared/clients/s3.py`, criar `ObjectNotFoundError` e fazer `S3Client.get_object` levantá-la quando o `ClientError` tiver código `NoSuchKey` (demais erros propagam); exportá-la em `shared/pedidos_shared/src/pedidos_shared/__init__.py`
- [X] T002 [P] Teste de `get_object` (objeto existente devolve bytes; `NoSuchKey` levanta `ObjectNotFoundError`; outro `ClientError` propaga) em `shared/pedidos_shared/tests/test_s3_client.py`
- [X] T003 Em `services/api-gateway/src/api_gateway/deps.py`, adicionar `get_s3_client` e `S3ClientDep`; em `services/api-gateway/tests/conftest.py`, adicionar fixture `fake_s3_client` (MagicMock) e o override de `get_s3_client` na fixture `client`
- [X] T004 Confirmar que `file-consumer` continua tratando falha de `get_object` como técnica (`ObjectNotFoundError` não pode virar rejeição de negócio silenciosa); ajustar `services/file-consumer/src/file_consumer/handlers/processar_notificacao.py` e seu teste somente se necessário

**Checkpoint**: `uv run --all-packages pytest shared services/file-consumer` verde.

---

## Phase 3: User Story 1 - Baixar o PDF de um pedido concluído (Priority: P1) 🎯 MVP

**Goal**: `GET /pedidos/{order_id}/nota-fiscal` devolve o PDF direto para pedidos `COMPLETED`; `GET /pedidos` indica `invoice_available`.

**Independent Test**: Semear pedido `COMPLETED` + objeto no Ministack, `GET` devolve `200 application/pdf` com os mesmos bytes e `Content-Disposition` correto.

### Tests for User Story 1

- [X] T005 [P] [US1] Teste unitário da função pura `chave_da_nota_fiscal` para `COMPLETED` com chave em `services/api-gateway/tests/test_nota_fiscal_domain.py`
- [X] T006 [P] [US1] Teste do endpoint (S3 mockado): `200`, `Content-Type: application/pdf`, `Content-Disposition: inline; filename="nota-fiscal-{order_id}.pdf"`, corpo igual aos bytes, bucket de `Settings.pedidos_bucket_name`, e log sem `customer_document` em `services/api-gateway/tests/test_nota_fiscal.py`
- [X] T007 [P] [US1] Teste de integração contra Ministack (put do PDF + pedido semeado → GET devolve os mesmos bytes) em `services/api-gateway/tests/test_nota_fiscal.py`

### Implementation for User Story 1

- [X] T008 [US1] Criar `chave_da_nota_fiscal(order) -> str` e as exceções de negócio (`NotaFiscalEmAndamentoError`, `NotaFiscalIndisponivelError`, `NotaFiscalAusenteError`) conforme `data-model.md` em `services/api-gateway/src/api_gateway/domain/nota_fiscal.py` (função pura, sem I/O)
- [X] T009 [US1] Criar o handler `GET /pedidos/{order_id}/nota-fiscal` (`get_by_id` → `chave_da_nota_fiscal` → `S3Client.get_object` → `Response(media_type="application/pdf")` com `Content-Disposition`; log JSON com `orderId`/`correlationId`) em `services/api-gateway/src/api_gateway/handlers/baixar_nota_fiscal.py`
- [X] T010 [US1] Registrar o router em `services/api-gateway/src/api_gateway/main.py`
- [X] T011 [US1] Em `services/api-gateway/src/api_gateway/schemas.py`, remover `invoice_s3_key` de `PedidoResponse` e adicionar `invoice_available: bool` (`True` só quando `COMPLETED` com chave) calculado em `from_order`; atualizar `services/api-gateway/tests/test_consultar_pedido.py` e `test_listar_pedidos.py` para assertar `invoice_available` e a ausência de `invoice_s3_key`

**Checkpoint**: US1 funcional e testável sozinha.

---

## Phase 4: User Story 2 - Resposta clara quando o PDF ainda não existe (Priority: P2)

**Goal**: Cada situação sem PDF devolve resposta distinta (404/409/410).

**Independent Test**: Pedir o PDF de pedido inexistente, em andamento, `REJECTED`/`FAILED`/`CANCELLED` e `COMPLETED` com objeto ausente; cada caso retorna o status/detalhe do contrato.

### Tests for User Story 2

- [X] T012 [P] [US2] Estender `services/api-gateway/tests/test_nota_fiscal_domain.py` com um caso por estado (`RECEIVED`, `PROCESSING`, `VALIDATING`, `VALIDATED`, `INVOICING` → em andamento; `REJECTED`, `FAILED`, `CANCELLED` → indisponível; `COMPLETED` sem chave → ausente)
- [X] T013 [P] [US2] Testes do endpoint em `services/api-gateway/tests/test_nota_fiscal.py`: `404` pedido inexistente, `409` em andamento, `410` rejeitado/falho/cancelado, `404` com detalhe `PDF não encontrado no armazenamento` quando `get_object` levanta `ObjectNotFoundError`, `500` quando levanta outro erro técnico

### Implementation for User Story 2

- [X] T014 [US2] No handler `services/api-gateway/src/api_gateway/handlers/baixar_nota_fiscal.py`, mapear as exceções de domínio e `ObjectNotFoundError` para `HTTPException` com os detalhes de `contracts/nota-fiscal-endpoint.md`; erros técnicos do S3 propagam (500, sem detalhe interno)

**Checkpoint**: US1 e US2 funcionam de forma independente.

---

## Phase 5: User Story 3 - Armazenamento permanece fechado (Priority: P3)

**Goal**: Nenhuma resposta expõe chave, bucket, endpoint ou credencial do S3.

**Independent Test**: Varrer corpo e cabeçalhos de todas as respostas do endpoint e de `GET /pedidos` procurando `invoices/`, nome do bucket e endpoint.

### Tests for User Story 3

- [X] T015 [P] [US3] Teste em `services/api-gateway/tests/test_nota_fiscal.py` que percorre todos os cenários (200/404/409/410) e afirma que corpo (textual) e cabeçalhos não contêm `invoices/`, `pedidos-bucket` nem `localhost:4566`; em `test_consultar_pedido.py`, afirma que `invoice_s3_key` não aparece no JSON

### Implementation for User Story 3

- [X] T016 [US3] Revisar `services/api-gateway/src/api_gateway/handlers/baixar_nota_fiscal.py` para garantir que nenhuma mensagem de erro/log interpola chave, bucket ou exceção do boto3 na resposta; corrigir o que o teste T015 apontar

**Checkpoint**: Todas as stories independentes.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T017 [P] Atualizar os asserts de `invoice_s3_key` por download do PDF (`GET .../nota-fiscal` → `200`, corpo começando com `%PDF`) em `tests/e2e/test_online_happy_path.py` e `tests/e2e/test_editar_pedido.py`
- [X] T018 [P] Atualizar `README.md` (exemplo de resposta com `invoice_available` e passo `curl -o nota.pdf .../nota-fiscal`) e documentar a extensão em `docs/01-dominio-e-contratos.md`
- [X] T019 [P] Atualizar `services/api-gateway/README.md` (se existir) com a nova rota e os códigos de resposta
- [X] T020 Rodar `uv run --all-packages pytest` (com Ministack e workers parados, conforme CLAUDE.md), `uv run ruff check` e `uv run ruff format --check` em `shared/` e `services/api-gateway/`
- [X] T021 Rodar `make up` + `make e2e` e executar os cenários de `specs/010-acesso-pdf-pedido/quickstart.md`
- [X] T022 Code review (constitution VII, skill `code-review`) com foco em vazamento de chave (SC-005), somente leitura (VII.2) e erro técnico vs. de negócio; corrigir apontamentos antes do PR
- [ ] T023 Abrir PR de `feature/010-acesso-pdf-pedido` para `develop`, registrando no corpo a mudança incompatível (`invoice_s3_key` → `invoice_available`)

---

## Dependencies & Execution Order

### Phase Dependencies

- Foundational (T001–T004) bloqueia todas as stories.
- US1 → US2 → US3: US2 e US3 estendem o mesmo handler/arquivo de testes de US1, então são sequenciais na prática (mesmo arquivo `baixar_nota_fiscal.py`).
- Polish depende de US1–US3.

### Within Each Story

- Testes primeiro (devem falhar), depois domínio, handler e registro.
- T008 antes de T009; T009 antes de T010; T011 independente do endpoint (só schema).

### Parallel Opportunities

- T002 em paralelo a T003/T004 (arquivos distintos).
- T005, T006, T007 em paralelo (T006 e T007 compartilham arquivo: escrever em sequência ou separar em `test_nota_fiscal_integration.py` se quiser paralelizar).
- T011 em paralelo a T008–T010.
- T017, T018, T019 em paralelo.

## Parallel Example: User Story 1

```text
# Testes juntos:
T005 test_nota_fiscal_domain.py
T006 test_nota_fiscal.py (unitário)
# Em paralelo à rota:
T008 domain/nota_fiscal.py   |   T011 schemas.py (invoice_available)
```

## Implementation Strategy

### MVP First (US1)

1. Foundational (T001–T004).
2. US1 (T005–T011): baixar PDF de pedido concluído + `invoice_available`.
3. Validar com o cenário 1 do `quickstart.md`.

### Incremental Delivery

1. US1 → MVP demonstrável.
2. US2 → respostas claras para estados sem PDF.
3. US3 → garantia de não vazamento.
4. Polish (e2e, docs, review, PR).

## Notes

- `[P]` = arquivos diferentes e sem dependência pendente; `[US#]` mapeia a story de `spec.md`.
- O endpoint é somente leitura: nunca escreve em `orders` nem publica em fila.
- Mudança incompatível deliberada: `invoice_s3_key` sai da resposta da API (FR-004); registrar no PR.
- Nunca logar `customer_document` em claro; usar `mask_document` de `pedidos_shared`.
