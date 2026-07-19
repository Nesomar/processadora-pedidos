---

description: "Task list for Fundação Compartilhada (pedidos_shared)"
---

# Tasks: Fundação Compartilhada (pedidos_shared)

**Input**: Design documents from `/specs/001-fundacao-compartilhada/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/pedidos_shared-api.md, research.md

**Tests**: Incluídas — FR-010 exige explicitamente testes unitários dos modelos, transições e
parser; FR-012 e a integração SQS de US2 também têm caminho de erro coberto.

**Organization**: Tarefas agrupadas por user story (spec.md) pra permitir implementação e teste
independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: US1–US4, mapeando pra spec.md
- Caminhos de arquivo exatos em cada descrição

## Path Conventions

Biblioteca única em `shared/pedidos_shared/` (ver plan.md → Project Structure):

```
shared/pedidos_shared/
├── pyproject.toml
├── src/pedidos_shared/{models,status,settings,masking,logging,parsing}.py + clients/{sqs,dynamodb,s3}.py
└── tests/{test_models,test_status,test_settings,test_masking,test_logging,test_parsing}.py + tests/clients/test_sqs.py
```

---

## Phase 1: Setup

**Purpose**: Inicialização do pacote e do workspace `uv`

- [ ] T001 Criar esqueleto do projeto em `shared/pedidos_shared/` (`pyproject.toml`, `src/pedidos_shared/`, `tests/`, `tests/clients/`) conforme plan.md → Project Structure
- [ ] T002 [P] Configurar workspace `uv` na raiz do repo: adicionar `[tool.uv.workspace]` com `members = ["services/*", "shared/pedidos_shared"]` em `pyproject.toml` (raiz) — research.md #2
- [ ] T003 [P] Configurar `ruff` (lint + format) em `shared/pedidos_shared/pyproject.toml` conforme constitution IV

**Checkpoint**: `uv sync --package pedidos-shared` roda sem erro (pacote vazio, mas instalável)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Único artefato que toda user story precisa para poder importar do pacote

**⚠️ CRITICAL**: Nenhuma user story pode ser implementada antes desta fase

- [ ] T004 Criar `shared/pedidos_shared/src/pedidos_shared/__init__.py` vazio (será populado com exports conforme cada user story fecha)

**Checkpoint**: `import pedidos_shared` funciona a partir de qualquer serviço do workspace

---

## Phase 3: User Story 1 - Contrato de mensagem e status únicos (Priority: P1) 🎯 MVP

**Goal**: Modelos Pydantic de mensagem e enum `StatusPedido` com transições válidas, únicos e
importáveis por qualquer serviço.

**Independent Test**: Importar o pacote num serviço de teste isolado, instanciar cada modelo,
serializar para JSON e confirmar que payload inválido / status fora do enum é rejeitado na
validação Pydantic.

### Tests for User Story 1 ⚠️

- [ ] T005 [P] [US1] Teste unitário de `StatusPedido` e `is_valid_transition` (todas as transições válidas do grafo em data-model.md + todas as inválidas rejeitadas) em `shared/pedidos_shared/tests/test_status.py`
- [ ] T006 [P] [US1] Teste unitário de `Pedido`, `ItemPedido` e dos 6 contratos de mensagem (payload válido aceito, campo obrigatório ausente rejeitado, `correlation_id` obrigatório) em `shared/pedidos_shared/tests/test_models.py`

### Implementation for User Story 1

- [ ] T007 [P] [US1] Implementar `StatusPedido` (enum) e `is_valid_transition(current, next) -> bool` conforme grafo em data-model.md em `shared/pedidos_shared/src/pedidos_shared/status.py`
- [ ] T008 [P] [US1] Implementar `Pedido` e `ItemPedido` (Pydantic v2) conforme data-model.md em `shared/pedidos_shared/src/pedidos_shared/models.py`
- [ ] T009 [US1] Implementar os 6 contratos de mensagem (`PedidoSolicitado`, `PedidoParaValidar`, `PedidoValidado`, `PedidoRejeitado`, `PedidoParaGerarPdf`, `PdfGerado`), todos com `correlation_id: str` obrigatório, em `shared/pedidos_shared/src/pedidos_shared/models.py` (depende de T008)
- [ ] T010 [US1] Exportar `StatusPedido`, `is_valid_transition`, `Pedido`, `ItemPedido` e os 6 contratos de mensagem em `shared/pedidos_shared/src/pedidos_shared/__init__.py` (depende de T007, T009)

**Checkpoint**: User Story 1 completa e testável de forma independente — MVP pronto

---

## Phase 4: User Story 2 - Configuração e clientes sem valores hardcoded (Priority: P2)

**Goal**: `Settings` lido de env vars + clientes SQS/DynamoDB/S3 usando `endpoint_url` do
Ministack, sem nenhum valor de infraestrutura hardcoded.

**Independent Test**: Com env vars apontando pro Ministack local, instanciar `SqsClient`, enviar e
receber uma mensagem de teste, sem nenhuma URL fixa no código.

### Tests for User Story 2 ⚠️

- [ ] T011 [P] [US2] Teste unitário de `Settings` (carrega valores válidos; `pydantic.ValidationError` claro quando uma env var obrigatória está ausente) em `shared/pedidos_shared/tests/test_settings.py`
- [ ] T012 [P] [US2] Teste de integração de `SqsClient` (send + receive contra Ministack local) em `shared/pedidos_shared/tests/clients/test_sqs.py`

### Implementation for User Story 2

- [ ] T013 [P] [US2] Implementar `Settings` (Pydantic, campos de data-model.md: `ministack_endpoint_url`, `orders_table_name`, `orders_bucket_name`, `*_queue_url`, `aws_region`) em `shared/pedidos_shared/src/pedidos_shared/settings.py`
- [ ] T014 [US2] Implementar `SqsClient(settings: Settings)` (wrapper síncrono sobre `boto3.client("sqs", endpoint_url=...)`) em `shared/pedidos_shared/src/pedidos_shared/clients/sqs.py` (depende de T013)
- [ ] T015 [US2] Implementar `DynamoDbClient(settings: Settings)` em `shared/pedidos_shared/src/pedidos_shared/clients/dynamodb.py` (depende de T013)
- [ ] T016 [US2] Implementar `S3Client(settings: Settings)` em `shared/pedidos_shared/src/pedidos_shared/clients/s3.py` (depende de T013)
- [ ] T017 [US2] Exportar `Settings`, `SqsClient`, `DynamoDbClient`, `S3Client` em `shared/pedidos_shared/src/pedidos_shared/__init__.py` (depende de T013–T016)

**Checkpoint**: User Stories 1 e 2 funcionam de forma independente

---

## Phase 5: User Story 3 - Logging estruturado rastreável (Priority: P3)

**Goal**: Logger JSON com `orderId`/`correlationId`, e mascaramento de documento do cliente
(FR-012) usado pelo logger sempre que o documento aparecer em log.

**Independent Test**: Chamar o logger com `orderId`/`correlationId` no contexto, capturar stdout,
validar JSON bem formado; chamar `mask_document` e validar que só os últimos 4 caracteres ficam
visíveis.

### Tests for User Story 3 ⚠️

- [ ] T018 [P] [US3] Teste unitário de `mask_document` (documento >4 chars mostra só os últimos 4; documento ≤4 chars totalmente mascarado) em `shared/pedidos_shared/tests/test_masking.py`
- [ ] T019 [P] [US3] Teste unitário do logger (log com `orderId`/`correlationId` → JSON válido com ambos os campos; log sem `orderId` → JSON válido sem exceção) em `shared/pedidos_shared/tests/test_logging.py`

### Implementation for User Story 3

- [ ] T020 [P] [US3] Implementar `mask_document(document: str) -> str` conforme regra em data-model.md em `shared/pedidos_shared/src/pedidos_shared/masking.py`
- [ ] T021 [P] [US3] Implementar `JsonFormatter` e `get_logger(name: str) -> logging.Logger` (stdlib `logging`, ver research.md #1) em `shared/pedidos_shared/src/pedidos_shared/logging.py`
- [ ] T022 [US3] Exportar `get_logger`, `mask_document` em `shared/pedidos_shared/src/pedidos_shared/__init__.py` e documentar no docstring do módulo que qualquer log de `Pedido.customer_document` MUST passar por `mask_document` (FR-012) (depende de T020, T021)

**Checkpoint**: User Stories 1–3 funcionam de forma independente

---

## Phase 6: User Story 4 - Parser de arquivo posicional reutilizável (Priority: P4)

**Goal**: Motor de parsing de largura fixa genérico, reutilizável pelo file-consumer (layout
fornecido pelo chamador, não fixado no pacote — ver research.md #6).

**Independent Test**: Parsear uma linha bem formada e validar campos extraídos; parsear uma linha
mais curta que o layout e validar erro de domínio específico, sem exceção genérica.

### Tests for User Story 4 ⚠️

- [ ] T023 [P] [US4] Teste unitário de `parse_fixed_width` (linha bem formada extrai campos corretos; linha mais curta que o layout levanta `LinhaCurtaError`) em `shared/pedidos_shared/tests/test_parsing.py`

### Implementation for User Story 4

- [ ] T024 [P] [US4] Implementar `FieldSpec`, `parse_fixed_width(line, layout)` e `LinhaCurtaError` conforme data-model.md em `shared/pedidos_shared/src/pedidos_shared/parsing.py`
- [ ] T025 [US4] Exportar `FieldSpec`, `parse_fixed_width`, `LinhaCurtaError` em `shared/pedidos_shared/src/pedidos_shared/__init__.py` (depende de T024)

**Checkpoint**: Todas as 4 user stories funcionam de forma independente

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Definição de pronto (constitution IX)

- [ ] T026 [P] Escrever `shared/pedidos_shared/README.md` documentando as variáveis de ambiente de `Settings` e os contratos de mensagem expostos (constitution IX)
- [ ] T027 Rodar `ruff check` e `ruff format --check` em `shared/pedidos_shared/` sem apontamentos
- [ ] T028 Rodar os cenários de `quickstart.md` ponta a ponta contra o Ministack local
- [ ] T029 [P] Executar o code review da constitution seção VII (skill `code-review` ou `/review`) antes de abrir o PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende do Setup — bloqueia todas as user stories
- **User Stories (Phase 3–6)**: todas dependem só do Foundational; são independentes entre si (US1–US4 podem rodar em paralelo se houver capacidade)
- **Polish (Phase 7)**: depende de todas as user stories desejadas estarem completas

### User Story Dependencies

- **US1 (P1)**: sem dependência de outra story
- **US2 (P2)**: sem dependência de outra story (usa `Settings` própria, não depende de US1)
- **US3 (P3)**: sem dependência de outra story (masking/logging são módulos isolados; a menção a `Pedido.customer_document` em T022 é documentação, não import)
- **US4 (P4)**: sem dependência de outra story

### Within Each Story

- Testes antes da implementação
- Modelos/enum antes de exports (`__init__.py` sempre por último em cada story)

### Parallel Opportunities

- Todo T com `[P]` roda em paralelo dentro da sua fase
- Uma vez completo o Foundational (T004), US1, US2, US3 e US4 podem ser trabalhadas em paralelo por desenvolvedores diferentes

---

## Parallel Example: User Story 1

```bash
# Testes de US1 em paralelo:
Task: "Teste unitário de StatusPedido e is_valid_transition em shared/pedidos_shared/tests/test_status.py"
Task: "Teste unitário de Pedido e contratos de mensagem em shared/pedidos_shared/tests/test_models.py"

# Implementação em paralelo (T007, T008 são arquivos/símbolos independentes):
Task: "Implementar StatusPedido e is_valid_transition em shared/pedidos_shared/src/pedidos_shared/status.py"
Task: "Implementar Pedido e ItemPedido em shared/pedidos_shared/src/pedidos_shared/models.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 apenas)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational
3. Completar Phase 3: User Story 1
4. **PARAR e VALIDAR**: rodar `pytest shared/pedidos_shared/tests/test_status.py shared/pedidos_shared/tests/test_models.py`
5. Demonstrar contrato único funcionando entre dois serviços de exemplo

### Incremental Delivery

1. Setup + Foundational → base pronta
2. US1 → testar independente → contrato/enum disponíveis pros demais serviços
3. US2 → testar independente → clientes de infraestrutura disponíveis
4. US3 → testar independente → observabilidade disponível
5. US4 → testar independente → parser disponível pro file-consumer

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente
- [Story] mapeia a tarefa pra user story correspondente em spec.md
- Verificar que os testes falham antes de implementar
- Rodar `ruff check`/`ruff format --check` a cada story fechada, não só no Polish
- Evitar: tarefa vaga, conflito de mesmo arquivo entre tarefas paralelas, dependência cruzada entre stories que quebre independência
