---

description: "Task list for Infraestrutura Local (Ministack)"
---

# Tasks: Infraestrutura Local (Ministack)

**Input**: Design documents from `/specs/002-infraestrutura-local/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/bootstrap-resources.md, research.md

**Tests**: Incluídas — FR-005 (idempotência) e constitution IX ("ao menos um teste de integração
rodando contra o Ministack") exigem verificação executável, não só documentação.

**Organization**: Tarefas agrupadas por user story (spec.md). **Nota de dependência real**: ao
contrário da feature 001, aqui US1 e US3 não são totalmente independentes de US2 — US1
("dispara automaticamente e os recursos já existem") só é demonstrável de ponta a ponta depois que
US2 cria os recursos de fato, e os testes de US3 chamam as mesmas funções que US2 implementa. Isso
é consequência da clarificação que uniu "subir" e "popular" num único comando (ver spec.md →
Clarifications). Ver seção Dependencies abaixo.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

```
.env.example                     # raiz do repo
infra/
├── docker-compose.yml
└── bootstrap/
    ├── pyproject.toml
    ├── main.py
    ├── resources/{queues,table,bucket}.py
    └── tests/{test_queues,test_table,test_bucket,test_idempotency}.py
```

---

## Phase 1: Setup

- [ ] T001 Criar esqueleto de `infra/bootstrap/` (`pyproject.toml`, `main.py` stub, `resources/__init__.py`, `tests/`) conforme plan.md → Project Structure
- [ ] T002 [P] Criar `infra/docker-compose.yml` com o serviço `ministack` (imagem, portas, healthcheck com endpoint e intervalo corretos pra gate `condition: service_healthy` do serviço `bootstrap`) — ainda sem o serviço `bootstrap`
- [ ] T003 [P] Criar `.env.example` na raiz do repo com `MINISTACK_ENDPOINT_URL`, `AWS_REGION`, `ORDERS_TABLE_NAME`, `ORDERS_BUCKET_NAME`, `PEDIDO_SOLICITADO_QUEUE_URL` (data-model.md)
- [ ] T004 [P] Configurar `ruff` em `infra/bootstrap/pyproject.toml`

**Checkpoint**: `docker compose -f infra/docker-compose.yml up -d` sobe só o Ministack e fica saudável

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: bloqueia todas as user stories

- [ ] T005 Adicionar o serviço `bootstrap` a `infra/docker-compose.yml` (`depends_on: ministack: condition: service_healthy`), ainda sem lógica de negócio (depende de T001, T002)
- [ ] T006 Implementar helper de retry de conexão (poucas tentativas, backoff simples) em `infra/bootstrap/main.py`, conforme research.md #4

**Checkpoint**: `docker compose up` sobe o Ministack e dispara o serviço `bootstrap` (que ainda não faz nada)

---

## Phase 3: User Story 2 - Recursos de infraestrutura já existem (Priority: P1)

**Goal**: filas (com DLQ), tabela e bucket criados de fato contra o Ministack.

**Independent Test**: rodar `main.py` diretamente contra um Ministack já subido (sem depender do
gatilho automático de US1) e consultar SQS/DynamoDB/S3 pra confirmar que os recursos existem com a
configuração esperada.

### Tests for User Story 2 ⚠️

- [ ] T007 [P] [US2] Teste de `create_or_verify_queue` (cria fila + DLQ com `maxReceiveCount=3`) em `infra/bootstrap/tests/test_queues.py`
- [ ] T008 [P] [US2] Teste de `create_or_verify_table` (cria tabela `orders` com chave `order_id`) em `infra/bootstrap/tests/test_table.py`
- [ ] T009 [P] [US2] Teste de `create_or_verify_bucket` (cria bucket `orders-pdf`) em `infra/bootstrap/tests/test_bucket.py`

### Implementation for User Story 2

- [ ] T010 [P] [US2] Implementar `create_or_verify_queue(name, dlq_name) -> str` (fila + DLQ + redrive policy `maxReceiveCount=3`, captura exceção "já existe" — research.md #3) em `infra/bootstrap/resources/queues.py`
- [ ] T011 [P] [US2] Implementar `create_or_verify_table(name) -> None` (tabela com chave `order_id`) em `infra/bootstrap/resources/table.py`
- [ ] T012 [P] [US2] Implementar `create_or_verify_bucket(name) -> None` em `infra/bootstrap/resources/bucket.py`
- [ ] T013 [US2] Em `infra/bootstrap/main.py`, ler nomes de recurso das variáveis de ambiente (`.env.example`) e chamar `create_or_verify_queue("pedido-solicitado", "pedido-solicitado-dlq")`, `create_or_verify_table(ORDERS_TABLE_NAME)`, `create_or_verify_bucket(ORDERS_BUCKET_NAME)` usando o retry de T006 (depende de T006, T010, T011, T012)

**Checkpoint**: `uv run --package infra-bootstrap python infra/bootstrap/main.py` cria os 3 tipos de recurso contra um Ministack já rodando

---

## Phase 4: User Story 1 - Subir o ambiente local com um comando (Priority: P1)

**Goal**: `docker compose up` sozinho deixa Ministack + recursos prontos, sem segundo comando.

**Independent Test**: numa máquina limpa, rodar só `docker compose up -d` e confirmar que o
Ministack fica saudável e o serviço `bootstrap` roda e sai com código 0 automaticamente.

**Depende de**: Phase 3 completa — antes disso o serviço `bootstrap` do compose não faz nada de
útil (ver nota de dependência real no topo do arquivo).

### Implementation for User Story 1

- [ ] T015 [US1] Configurar build/comando do serviço `bootstrap` em `infra/docker-compose.yml` (imagem Python 3.12 + `uv`, roda `main.py`, sai com código 0) (depende de T005, T013) — healthcheck do `ministack` já cravado em T002

**Checkpoint**: `docker compose up -d` sozinho deixa o ambiente pronto — User Stories 1 e 2 validadas juntas de ponta a ponta

---

## Phase 5: User Story 3 - Rodar o bootstrap de novo não quebra nem duplica (Priority: P2)

**Goal**: idempotência verificada, incluindo o caso de recurso com configuração divergente.

**Independent Test**: rodar `main.py` duas vezes seguidas contra o mesmo Ministack; segunda
execução não falha nem duplica.

**Depende de**: Phase 3 (usa as mesmas funções `create_or_verify_*`).

### Tests for User Story 3 ⚠️

- [ ] T016 [P] [US3] Teste de idempotência: chamar `create_or_verify_queue`/`_table`/`_bucket` duas vezes seguidas contra Ministack, confirmar sem exceção e sem duplicata em `infra/bootstrap/tests/test_idempotency.py`

### Implementation for User Story 3

- [ ] T017 [US3] Completar `create_or_verify_queue` (e os demais, se aplicável) para logar aviso estruturado — não falhar — quando o recurso existir com configuração divergente da esperada (edge case da spec; constitution I.5 "falha é dado") (depende de T010)

**Checkpoint**: todas as 3 user stories validadas

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T018 [P] Escrever `infra/README.md` documentando as variáveis de `.env.example` e o comando `docker compose up` (constitution IX / FR-008)
- [ ] T019 Rodar `ruff check` e `ruff format --check` em `infra/bootstrap/` sem apontamentos
- [ ] T020 Rodar os cenários de `quickstart.md` ponta a ponta, incluindo o teste de integração de `pedidos_shared` (feature 001) contra este ambiente (valida SC-004)
- [ ] T021 [P] Executar o code review da constitution seção VII antes de abrir o PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende do Setup — bloqueia todas as stories
- **US2 (Phase 3)**: depende só do Foundational — é a que efetivamente implementa a lógica de recurso
- **US1 (Phase 4)**: depende de US2 completa (ver nota de dependência real) — não é paralela a US2
- **US3 (Phase 5)**: depende de US2 completa (reusa as mesmas funções) — pode rodar em paralelo com US1, já que ambas só dependem de US2, não uma da outra
- **Polish (Phase 6)**: depende de US1, US2 e US3 completas

### Parallel Opportunities

- T002/T003/T004 (Setup) em paralelo
- T007/T008/T009 (testes de US2) em paralelo; T010/T011/T012 (implementação de US2) em paralelo
- Depois que US2 fecha: US1 (T015) e US3 (T016/T017) podem ser trabalhadas em paralelo por desenvolvedores diferentes

---

## Parallel Example: User Story 2

```bash
# Testes em paralelo:
Task: "Teste de create_or_verify_queue em infra/bootstrap/tests/test_queues.py"
Task: "Teste de create_or_verify_table em infra/bootstrap/tests/test_table.py"
Task: "Teste de create_or_verify_bucket em infra/bootstrap/tests/test_bucket.py"

# Implementação em paralelo:
Task: "Implementar create_or_verify_queue em infra/bootstrap/resources/queues.py"
Task: "Implementar create_or_verify_table em infra/bootstrap/resources/table.py"
Task: "Implementar create_or_verify_bucket em infra/bootstrap/resources/bucket.py"
```

---

## Implementation Strategy

### MVP First

1. Setup (Phase 1) + Foundational (Phase 2)
2. US2 (Phase 3) — é o núcleo real da feature; sem ela, US1 e US3 não têm o que validar
3. **PARAR e VALIDAR**: `uv run --package infra-bootstrap python infra/bootstrap/main.py` contra Ministack manual, conferir recursos
4. US1 (Phase 4) — fecha a experiência de um comando só
5. US3 (Phase 5) — fecha a garantia de idempotência/drift

### Incremental Delivery

1. Setup + Foundational → compose sobe Ministack, bootstrap existe mas é vazio
2. US2 → recursos criáveis via `main.py` manual
3. US1 → `docker compose up` já basta (fecha SC-001)
4. US3 → reexecução segura garantida e testada (fecha SC-002)

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente
- US1 e US3 dependem de US2 apesar do label de story — documentado explicitamente pra não gerar
  falsa expectativa de paralelismo total entre as 3 stories
- Verificar que os testes falham antes de implementar
- Rodar `ruff check`/`ruff format --check` a cada story fechada
