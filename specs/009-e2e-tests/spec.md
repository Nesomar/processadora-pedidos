# Feature Specification: Suite de Testes End-to-End

**Feature Branch**: `009-e2e-tests`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "Suite de testes end-to-end (tests/e2e/, já mencionada na constitution III e no Makefile 'make e2e', ainda não criada) que valida o pipeline inteiro do sistema rodando de verdade via docker-compose (Ministack + todos os 6 serviços), sem mockar nada. Cobre: (1) fluxo online feliz — POST /pedidos com pedido válido chega a COMPLETED com nota fiscal emitida; (2) edição de pedido (EDITAR) muda os dados e o pedido segue o ciclo; (3) cancelamento (CANCELAR) leva o pedido a CANCELLED; (4) fluxo batch feliz — upload de arquivo posicional válido no S3 chega a um pedido criado e processado, fechando o pipeline File Consumer → Lambda Line Processor → API Gateway → Order Processor; (5) rejeição de negócio — pedido com documento inválido ou item sem estoque chega a REJECTED com motivo. São testes de sistema (contra o ambiente todo rodando), distintos dos testes de integração por serviço que já existem em cada services/*/tests/."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Confirmar que um pedido online válido chega a completo (Priority: P1) MVP

Como responsável por manter o sistema, preciso de uma prova automatizada, executável a qualquer
momento, de que um pedido enviado pelo cliente HTTP com dados válidos percorre o pipeline inteiro
(validação, cálculo de totais, emissão de nota fiscal) e chega ao estado final de sucesso — sem
depender de checagem manual via `curl` a cada mudança no sistema.

**Why this priority**: É o caminho principal do sistema inteiro. Se esse fluxo quebrar sem que
ninguém perceba, nenhum pedido online é processado — é a prova de vida mais importante que a
suíte pode dar.

**Independent Test**: Rodar a suíte com o ambiente completo no ar; o cenário envia um pedido válido
via HTTP e falha se o pedido não chegar a `COMPLETED` com nota fiscal registrada dentro do tempo
esperado.

**Acceptance Scenarios**:

1. **Given** o ambiente completo rodando (Ministack + todos os serviços), **When** um pedido válido
   é enviado via `POST /pedidos`, **Then** consultar esse pedido eventualmente mostra
   `status=COMPLETED` e uma chave de nota fiscal preenchida.
2. **Given** um pedido chegou a `COMPLETED`, **When** o cenário consulta o pedido, **Then** os
   totais (subtotal, desconto, total) e os itens enriquecidos estão preenchidos com os dados reais
   do catálogo externo.

---

### User Story 2 - Confirmar que um pedido inválido é reprovado com motivo (Priority: P1)

Preciso da mesma garantia automatizada para o caminho de reprovação: um pedido com documento
inválido ou item sem estoque suficiente deve ser recusado de forma clara, com o motivo registrado,
em vez de ficar em um estado incerto.

**Why this priority**: Reprovar pedidos de forma correta é tão crítico quanto aprová-los — um erro
aqui deixaria pedidos inválidos passarem, ou pedidos válidos travados por engano.

**Independent Test**: Rodar a suíte com o ambiente completo no ar; o cenário envia um pedido com
documento inválido (ou item sem estoque) e falha se o pedido não chegar a `REJECTED` com motivo
registrado.

**Acceptance Scenarios**:

1. **Given** o ambiente completo rodando, **When** um pedido com `customer_document` inválido é
   enviado via `POST /pedidos`, **Then** consultar esse pedido eventualmente mostra
   `status=REJECTED` com um motivo não vazio.

---

### User Story 3 - Confirmar que o pipeline de arquivo em lote cria o pedido (Priority: P1)

Preciso da mesma garantia automatizada para a outra porta de entrada do sistema: um arquivo
posicional válido enviado ao armazenamento deve resultar em um pedido criado e processado, provando
que a cadeia inteira (File Consumer → Lambda Line Processor → API Gateway → Order Processor)
funciona de ponta a ponta.

**Why this priority**: É a única forma de provar, de forma automatizada, que a entrada em lote
continua funcionando depois de qualquer mudança futura em qualquer um dos quatro serviços dessa
cadeia — hoje essa prova só existe como validação manual repetida a cada feature.

**Independent Test**: Rodar a suíte com o ambiente completo no ar; o cenário envia um arquivo
posicional válido para o armazenamento e falha se o pedido correspondente não for criado dentro do
tempo esperado.

**Acceptance Scenarios**:

1. **Given** o ambiente completo rodando, **When** um arquivo posicional válido com um pedido é
   enviado ao armazenamento, **Then** eventualmente existe um pedido consultável com
   `channel=BATCH`, o nome do arquivo e o número da linha de origem corretos.

---

### User Story 4 - Confirmar que editar um pedido reflete os novos dados (Priority: P2)

Preciso da mesma garantia automatizada para a edição: alterar um pedido existente deve atualizar
os dados e reiniciar o ciclo de validação, não apenas aceitar a requisição sem efeito real.

**Why this priority**: Edição é um caminho secundário em relação ao fluxo principal de criação —
importante, mas com menor impacto se quebrar isoladamente (o pedido original continua existindo).

**Independent Test**: Rodar a suíte com o ambiente completo no ar; o cenário cria um pedido, edita
um dado (ex.: quantidade de um item) e falha se o pedido consultado não refletir o novo dado depois
de reprocessado.

**Acceptance Scenarios**:

1. **Given** um pedido existente, **When** ele é editado via `PUT /pedidos/{order_id}` com itens
   diferentes, **Then** consultar o pedido eventualmente mostra os itens atualizados e um novo
   ciclo de validação concluído.

---

### User Story 5 - Confirmar que cancelar um pedido o leva a cancelado (Priority: P2)

Preciso da mesma garantia automatizada para o cancelamento: cancelar um pedido existente deve
levá-lo ao estado final correspondente, encerrando o ciclo.

**Why this priority**: Assim como a edição, é um caminho secundário — importante para completar a
cobertura do ciclo de vida do pedido, mas de impacto isolado menor que o caminho principal.

**Independent Test**: Rodar a suíte com o ambiente completo no ar; o cenário cria um pedido,
cancela-o e falha se o pedido consultado não chegar a `CANCELLED`.

**Acceptance Scenarios**:

1. **Given** um pedido existente e ainda não finalizado, **When** ele é cancelado via
   `POST /pedidos/{order_id}/cancelamento`, **Then** consultar o pedido eventualmente mostra
   `status=CANCELLED`.

---

### Edge Cases

- Ambiente não está no ar (Ministack ou algum dos 6 serviços indisponível): a suíte falha
  rapidamente com uma mensagem clara indicando qual componente está inacessível, em vez de esperar
  o tempo limite completo de cada cenário.
- Um cenário demora mais que o tempo limite esperado para chegar ao estado final: a suíte falha
  aquele cenário especificamente, sem travar a execução dos demais cenários independentes.
- Execuções repetidas da suíte contra o mesmo ambiente não devem colidir entre si nem com dados de
  execuções anteriores (cada cenário usa seus próprios identificadores únicos).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A suíte DEVE rodar contra o ambiente completo real (Ministack e os 6 serviços via
  `docker-compose`), sem substituir nenhum componente por um dublê — incluindo a chamada real ao
  catálogo externo de produtos.
- **FR-002**: A suíte DEVE cobrir o fluxo online de aprovação completa (US1), o fluxo online de
  reprovação de negócio (US2), o fluxo de entrada em lote (US3), a edição de pedido (US4) e o
  cancelamento de pedido (US5).
- **FR-003**: Cada cenário DEVE aguardar o processamento assíncrono (poll com intervalo curto até
  um tempo limite) em vez de assumir que o resultado já está disponível imediatamente após a
  requisição inicial.
- **FR-004**: Cada cenário DEVE usar identificadores únicos (ex.: UUID por execução) para não
  colidir com dados de execuções anteriores ou concorrentes contra o mesmo ambiente.
- **FR-005**: A suíte DEVE ser executável via `make e2e` (alvo já existente no `Makefile`, hoje sem
  efeito por não existir `tests/e2e/`).
- **FR-006**: Um cenário que atinge o tempo limite sem chegar ao estado esperado DEVE falhar com
  uma mensagem que identifique o pedido (ou arquivo) e o último estado observado — não apenas um
  timeout genérico.
- **FR-007**: A suíte NÃO DEVE escrever diretamente em nenhuma tabela ou fila do sistema — toda
  interação acontece pelos mesmos pontos de entrada que um usuário real usaria (API HTTP do API
  Gateway, upload de arquivo no armazenamento).

### Key Entities

- **Cenário de sistema**: um teste que exercita o pipeline completo a partir de um ponto de entrada
  real (HTTP ou upload de arquivo) até observar o resultado esperado (estado final do pedido,
  dados refletidos).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Rodando `make e2e` contra o ambiente completo íntegro, 100% dos 5 cenários (US1-US5)
  passam de forma consistente.
- **SC-002**: Cada cenário conclui (sucesso ou falha) em menos de 60 segundos, refletindo o tempo
  real de processamento assíncrono do pipeline.
- **SC-003**: Rodar a suíte duas vezes seguidas contra o mesmo ambiente não produz falhas por
  colisão de dados entre execuções.
- **SC-004**: Quando um componente do ambiente está fora do ar, a suíte falha em segundos (não em
  minutos), com uma mensagem indicando qual componente está inacessível.

## Assumptions

- O ambiente completo (`docker-compose up -d` / `make up`) já está no ar antes de rodar
  `make e2e` — a suíte não sobe nem derruba o ambiente sozinha, mesma separação de
  responsabilidades já refletida no `Makefile` atual (`up`/`down` são alvos distintos de `e2e`).
- A suíte consulta o estado do pedido pelos endpoints HTTP já existentes do API Gateway
  (`GET /pedidos/{order_id}`, `GET /pedidos?customerId=...`) — não lê o DynamoDB nem nenhuma fila
  diretamente, preservando o mesmo caminho que um cliente real usaria (FR-007).
- "Item sem estoque" ou "documento inválido" (US2) usa os mesmos dados de exemplo já usados nas
  validações manuais das features anteriores (ex.: catálogo real do `dummyjson.com`, mesmo CPF de
  exemplo já usado em `005-order-validator`/`007-file-consumer`).
- O tempo limite de espera por cenário (FR-003, SC-002) é uma escolha de implementação — não é
  reaberto nesta spec além do teto de 60s definido em SC-002.
