---

description: "Task list for Infraestrutura Local (Ministack)"
---

# Tasks: Infraestrutura Local (Ministack)

**Input**: Design documents from `/specs/002-infraestrutura-local/` (realinhado a
`docs/01-dominio-e-contratos.md`)

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/bootstrap-resources.md, research.md

**Tests**: Incluídas — FR-006 (idempotência) e constitution IX exigem verificação executável.

**Nota de dependência real**: US1 e US3 não são totalmente independentes de US2 — só são
demonstráveis de ponta a ponta depois que US2 cria os recursos de fato. Ver Dependencies.

## Path Conventions

```
.env.example                     # raiz
Makefile                          # raiz
infra/
├── docker-compose.yml
└── bootstrap/
    ├── pyproject.toml
    ├── main.py
    ├── resources/{queues,orders_table,processed_messages_table,bucket}.py
    └── tests/{test_idempotency,test_bucket_notification}.py
```

---

## Phase 1: Setup

- [X] T001 Criar esqueleto de `infra/bootstrap/` (`pyproject.toml`, `main.py` stub, `resources/__init__.py`, `tests/`)
- [X] T002 [P] Criar `infra/docker-compose.yml` com o serviço `ministack` (imagem, portas, healthcheck com endpoint/intervalo corretos pro gate `condition: service_healthy` do `bootstrap`) — ainda sem o serviço `bootstrap`
- [X] T003 [P] Criar `.env.example` na raiz com `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ORDERS_TABLE_NAME`, `PROCESSED_MESSAGES_TABLE_NAME`, `PEDIDOS_BUCKET_NAME` e as 9 `*_QUEUE_URL` (data-model.md)
- [X] T004 [P] Configurar `ruff` em `infra/bootstrap/pyproject.toml`

**Checkpoint**: `docker compose -f infra/docker-compose.yml up -d` sobe só o Ministack e fica saudável

---

## Phase 2: Foundational

- [X] T005 Adicionar o serviço `bootstrap` a `infra/docker-compose.yml` (`depends_on: ministack: condition: service_healthy`), ainda sem lógica de negócio (depende de T001, T002)
- [X] T006 Implementar helper de retry de conexão em `infra/bootstrap/main.py` (research.md #4)

**Checkpoint**: `docker compose up` sobe o Ministack e dispara o `bootstrap` (ainda vazio)

---

## Phase 3: User Story 2 - Recursos completos do domínio existem (Priority: P1)

**Independent Test**: rodar `main.py` diretamente contra Ministack já subido; consultar
SQS/DynamoDB/S3 e confirmar os 9+2+1 recursos com a configuração exata do domínio.

### Tests

- [X] T007 [P] [US2] Teste de `create_or_verify_queue` (fila + DLQ + `maxReceiveCount=3`) parametrizado pelas 9 filas de data-model.md em `infra/bootstrap/tests/test_queues.py`
- [X] T008 [P] [US2] Teste de `create_or_verify_orders_table` (`PK`/`SK` + `GSI1` + `GSI2`) em `infra/bootstrap/tests/test_orders_table.py`
- [X] T009 [P] [US2] Teste de `create_or_verify_processed_messages_table` (PK + TTL habilitado) em `infra/bootstrap/tests/test_processed_messages_table.py`
- [X] T010 [P] [US2] Teste de `create_or_verify_bucket` + notificação de evento (`uploads/*.txt` → `s3_notifications_queue`) em `infra/bootstrap/tests/test_bucket_notification.py`

### Implementation

- [X] T011 [P] [US2] Implementar `create_or_verify_queue(name, dlq_name) -> str` (research.md #3) em `infra/bootstrap/resources/queues.py`
- [X] T012 [P] [US2] Implementar `create_or_verify_orders_table() -> None` (`PK`/`SK` + `GSI1` + `GSI2`, research.md #6) em `infra/bootstrap/resources/orders_table.py`
- [X] T013 [P] [US2] Implementar `create_or_verify_processed_messages_table() -> None` (PK + `TimeToLiveSpecification`) em `infra/bootstrap/resources/processed_messages_table.py`
- [X] T014 [P] [US2] Implementar `create_or_verify_bucket() -> None` + configuração de notificação de evento (compara config existente vs esperada antes de escrever — research.md #5) em `infra/bootstrap/resources/bucket.py`
- [X] T015 [US2] Em `infra/bootstrap/main.py`, ler nomes/URLs de `.env.example` e chamar `create_or_verify_queue` pras 9 filas, `create_or_verify_orders_table`, `create_or_verify_processed_messages_table`, `create_or_verify_bucket`, usando o retry de T006 (depende de T006, T011–T014)

**Checkpoint**: `uv run --package infra-bootstrap python infra/bootstrap/main.py` cria todos os recursos do domínio contra um Ministack já rodando

---

## Phase 4: User Story 1 - Subir o ambiente local com um comando (Priority: P1)

**Depende de**: Phase 3 completa (ver nota de dependência real).

### Implementation

- [X] T016 [US1] Configurar build/comando do serviço `bootstrap` em `infra/docker-compose.yml` (imagem Python 3.12 + `uv`, roda `main.py`, sai com código 0) (depende de T005, T015)

**Checkpoint**: `docker compose up -d` sozinho deixa o ambiente completo pronto

---

## Phase 5: User Story 3 - Rodar o bootstrap de novo não quebra nem duplica (Priority: P2)

**Depende de**: Phase 3 (usa as mesmas funções `create_or_verify_*`).

### Tests

- [X] T017 [P] [US3] Teste de idempotência: chamar todas as `create_or_verify_*` duas vezes seguidas contra Ministack, confirmar sem exceção e sem duplicata (filas, tabelas, bucket) em `infra/bootstrap/tests/test_idempotency.py`
- [X] T018 [P] [US3] Teste de idempotência da notificação de evento do bucket (configurar 2x não duplica nem quebra a config existente) em `infra/bootstrap/tests/test_bucket_notification.py` (estende T010)

### Implementation

- [X] T019 [US3] Completar `create_or_verify_queue`/`create_or_verify_bucket` pra logar aviso — não falhar — quando o recurso existir com configuração divergente da esperada (constitution I.5) (depende de T011, T014)

**Checkpoint**: US1–US3 validadas

---

## Phase 6: User Story 4 - Atalhos de Makefile (Priority: P3)

**Independent Test**: rodar cada alvo numa máquina limpa, confirmar mesmo efeito do comando completo.

### Implementation

- [X] T020 [P] [US4] Criar `Makefile` na raiz com os alvos `up`, `down`, `bootstrap`, `test`, `e2e` conforme §8 (depende de T016)
- [X] T021 [US4] Implementar `make seed-file` — gera arquivo posicional de exemplo válido (header + 1 pedido + trailer, layout de `docs/01-dominio-e-contratos.md` §6) e faz upload em `uploads/` no bucket (depende de T014, T020)

**Checkpoint**: todas as 4 user stories validadas

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T022 [P] Escrever `infra/README.md` documentando as variáveis de `.env.example`, o comando `docker compose up` e os alvos do `Makefile` (constitution IX / FR-009)
- [X] T023 Rodar `ruff check`/`ruff format --check` em `infra/bootstrap/`
- [X] T024 Rodar os cenários de `quickstart.md` ponta a ponta, incluindo o teste de integração de `pedidos_shared` (SC-004) e o upload → notificação (SC-005) — SC-005 validado manualmente (seed-file → s3_notifications_queue); SC-004 validado após merge de develop nesta branch: shared/pedidos_shared/tests/clients/test_sqs.py passou contra Ministack real
- [X] T025 [P] Executar o code review da constitution seção VII antes de abrir o PR

---

## Dependencies & Execution Order

- **Setup/Foundational**: bloqueiam tudo
- **US2 (Phase 3)**: depende só do Foundational — núcleo real da feature
- **US1 (Phase 4)**: depende de US2 completa
- **US3 (Phase 5)**: depende de US2 completa; pode rodar em paralelo com US1
- **US4 (Phase 6)**: depende de US1 (`make up`) e US2 (`make seed-file` usa `create_or_verify_bucket`)
- **Polish**: depende de US1–US4 completas

### Parallel Opportunities

- T002/T003/T004 (Setup) em paralelo
- T007–T010 (testes US2) em paralelo; T011–T014 (implementação US2) em paralelo
- Depois que US2 fecha: US1 e US3 em paralelo; depois que US1 fecha, US4 pode começar

---

## Implementation Strategy

### MVP First

1. Setup + Foundational
2. US2 — núcleo real; sem ela nada mais tem o que validar
3. **PARAR e VALIDAR**: `main.py` manual contra Ministack, conferir os 9+2+1 recursos
4. US1 — fecha a experiência de um comando só
5. US3 — fecha a garantia de idempotência/drift
6. US4 — conveniência, não bloqueia nada

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente
- US1 e US3 dependem de US2 apesar do label — documentado explicitamente
- Rodar `ruff check`/`ruff format --check` a cada story fechada
