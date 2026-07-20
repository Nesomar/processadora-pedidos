# Feature Specification: Order Processor

**Feature Branch**: `004-order-processor`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "order-processor: serviço worker Python que é o orquestrador central
do sistema (§1 do domínio) — consome solicitar_pedido_queue/editar_pedido_queue/
cancelar_pedido_queue via pedidos_shared, é o único componente que escreve na tabela orders
(constitution, contrato regra 3 de pedidos_shared), aplica is_valid_transition em toda mutação de
status, dispara validação publicando em validar_pedido_queue e consome a resposta em
validar_pedido_response_queue, dispara geração de PDF publicando em pdf_request_queue e consome a
resposta em pdf_response_queue, e conclui o ciclo do pedido. Idempotente via
mark_message_processed em todo consumo de fila (constitution I.3). Nunca bloqueia esperando
resposta — cada transição é disparada por consumo de mensagem (constitution I.2)."

## Clarifications

### Session 2026-07-20

- Q: FR-008/FR-009 e as User Stories 4/5 dizem só "estado que permite edição/cancelamento", sem
  nomear os estados — devo nomear explicitamente, como a spec do api-gateway (003) fez? → A: Sim
  — nomeados abaixo, mesma tabela de transições usada por `is_valid_transition`
  (`docs/01-dominio-e-contratos.md` §2.3), sem duplicar decisão nova.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sistema aceita nova solicitação de pedido e dispara validação (Priority: P1) 🎯 MVP

Como sistema, preciso que toda solicitação de pedido aceita pelo ponto de entrada seja persistida
e encaminhada automaticamente para validação, para que o pedido comece a ser processado sem
nenhuma intervenção manual.

**Why this priority**: É o primeiro elo da cadeia de processamento — sem ele, nenhum pedido
solicitado chega a existir de fato no sistema nem avança para as etapas seguintes.

**Independent Test**: Publicar uma mensagem válida de solicitação de pedido e confirmar que um
registro correspondente passa a existir na tabela de pedidos em estado "em processamento", e que
uma mensagem de pedido de validação é publicada logo em seguida.

**Acceptance Scenarios**:

1. **Given** uma mensagem válida de solicitação de pedido, **When** o sistema a consome pela
   primeira vez, **Then** um registro do pedido é criado, avança para o estado "em processamento"
   e uma solicitação de validação é publicada, contendo o documento do cliente e os itens do
   pedido.
2. **Given** uma mensagem de solicitação de pedido referenciando um `order_id` já existente,
   **When** o sistema a consome novamente (reentrega), **Then** nenhum registro duplicado é criado
   e nenhuma segunda solicitação de validação é publicada.

---

### User Story 2 - Sistema conclui ou rejeita o pedido conforme o resultado da validação (Priority: P1)

Como sistema, preciso reagir automaticamente ao resultado da validação de um pedido — avançando
para a emissão da nota fiscal quando aprovado, ou encerrando com o motivo da rejeição quando
reprovado — para que o cliente saiba o desfecho sem intervenção manual.

**Why this priority**: Sem essa reação automática, todo pedido enviado para validação fica parado
indefinidamente, quebrando o fluxo de ponta a ponta.

**Independent Test**: Publicar uma resposta de validação (aprovada e, em outro teste, reprovada)
para um pedido em validação e confirmar que o estado e os dados do pedido são atualizados
corretamente em cada caso.

**Acceptance Scenarios**:

1. **Given** um pedido aguardando validação, **When** chega uma resposta de validação aprovada,
   **Then** o pedido é atualizado com os itens enriquecidos e os totais calculados, avança para
   "aguardando nota fiscal" e uma solicitação de emissão de nota fiscal é publicada.
2. **Given** um pedido aguardando validação, **When** chega uma resposta de validação reprovada,
   **Then** o pedido é encerrado em estado de rejeitado, com o motivo da rejeição registrado, e
   nenhuma solicitação de nota fiscal é publicada.

---

### User Story 3 - Sistema emite a nota fiscal e conclui o pedido (Priority: P1)

Como sistema, preciso reagir automaticamente ao resultado da emissão da nota fiscal — concluindo o
pedido com sucesso ou marcando falha técnica — para que o ciclo de vida do pedido chegue a um
desfecho final sem intervenção manual.

**Why this priority**: Fecha o fluxo principal de ponta a ponta; sem essa reação, pedidos
validados nunca chegam a um estado final.

**Independent Test**: Publicar uma resposta de emissão de nota fiscal (com sucesso e, em outro
teste, com falha) para um pedido aguardando nota fiscal e confirmar o desfecho correto em cada
caso.

**Acceptance Scenarios**:

1. **Given** um pedido aguardando nota fiscal, **When** chega uma resposta de emissão com sucesso,
   **Then** o pedido é concluído, com a referência da nota fiscal registrada.
2. **Given** um pedido aguardando nota fiscal, **When** chega uma resposta de emissão com falha,
   **Then** o pedido é marcado como falho, com o motivo técnico registrado.

---

### User Story 4 - Pedido editado reinicia o ciclo de processamento (Priority: P2)

Como sistema, preciso que uma edição de pedido aceita pelo ponto de entrada atualize os dados do
pedido e reinicie o ciclo de validação, desde que o pedido ainda esteja em um estado que permita
edição (`RECEIVED`, `VALIDATED` ou `REJECTED` — mesma tabela de transições usada por
`is_valid_transition`, `docs/01-dominio-e-contratos.md` §2.3).

**Why this priority**: Importante para dar suporte à correção de pedidos, mas o fluxo principal de
criação e conclusão já funciona sem essa capacidade.

**Independent Test**: Publicar uma mensagem de edição para um pedido em estado editável e para um
pedido em estado não editável, e confirmar o comportamento correto em cada caso.

**Acceptance Scenarios**:

1. **Given** um pedido em `RECEIVED`, `VALIDATED` ou `REJECTED`, **When** chega uma mensagem de
   edição, **Then** os dados do pedido são atualizados, o pedido reinicia o ciclo de
   processamento (mesmo comportamento da User Story 1) e uma nova solicitação de validação é
   publicada.
2. **Given** um pedido em qualquer outro estado (`PROCESSING`, `VALIDATING`, `INVOICING`,
   `COMPLETED`, `CANCELLED` ou `FAILED`), **When** chega uma mensagem de edição, **Then** a
   edição é rejeitada como erro de negócio e o pedido permanece inalterado.

---

### User Story 5 - Pedido cancelado é encerrado (Priority: P2)

Como sistema, preciso que uma solicitação de cancelamento aceita pelo ponto de entrada encerre o
pedido, desde que ele ainda esteja em um estado que permita cancelamento (`RECEIVED`,
`PROCESSING`, `VALIDATING` ou `VALIDATED` — mesma tabela de transições de §2.3).

**Why this priority**: Mesma faixa de importância da edição — completa a experiência do cliente
sem bloquear o fluxo principal.

**Independent Test**: Publicar uma mensagem de cancelamento para um pedido em estado cancelável e
para um pedido em estado não cancelável, e confirmar o comportamento correto em cada caso.

**Acceptance Scenarios**:

1. **Given** um pedido em `RECEIVED`, `PROCESSING`, `VALIDATING` ou `VALIDATED`, **When** chega
   uma mensagem de cancelamento, **Then** o pedido é encerrado em estado cancelado, com o motivo
   informado registrado.
2. **Given** um pedido em qualquer outro estado (`INVOICING`, `COMPLETED`, `CANCELLED`, `REJECTED`
   ou `FAILED`), **When** chega uma mensagem de cancelamento, **Then** o cancelamento é rejeitado
   como erro de negócio e o pedido permanece inalterado.

---

### User Story 6 - Reprocessar a mesma mensagem não duplica nem corrompe o pedido (Priority: P3)

Como sistema, preciso que reentregas da mesma mensagem (comum em filas assíncronas) nunca
dupliquem um registro, publiquem uma solicitação duplicada ou apliquem uma transição de estado
mais de uma vez.

**Why this priority**: Reforça a garantia de idempotência já usada pelas demais user stories —
tratada à parte para deixar essa garantia explicitamente testável.

**Independent Test**: Publicar a mesma mensagem (mesmo identificador de mensagem) duas vezes
seguidas e confirmar que o efeito observável (registro criado, mensagens publicadas, transição de
estado) acontece exatamente uma vez.

**Acceptance Scenarios**:

1. **Given** uma mensagem já processada com sucesso, **When** a mesma mensagem é entregue de novo,
   **Then** o sistema identifica a duplicidade e descarta o reprocessamento sem gerar nenhum efeito
   adicional.

---

### Edge Cases

- Resposta de validação ou de emissão de nota fiscal chega referenciando um `order_id` que não
  existe, ou que já está em um estado final incompatível → tratado como erro técnico, registrado
  em log, sem aplicar nenhuma mudança.
- Duas atualizações concorrentes do mesmo pedido (ex.: edição e resposta de validação chegando
  quase ao mesmo tempo) → a segunda escrita detecta o conflito, recarrega o estado atual do pedido
  e reavalia a transição antes de tentar de novo.
- Mensagem com formato inesperado (campos obrigatórios ausentes) → tratado como erro técnico,
  registrado em log, mensagem não é confirmada (permanece disponível para nova tentativa).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST, ao consumir uma solicitação de novo pedido, criar o registro do
  pedido e colocá-lo em processamento, publicando em seguida uma solicitação de validação com o
  documento do cliente e os itens do pedido.
- **FR-002**: O sistema MUST ser o único componente que grava o registro do pedido — nenhuma outra
  parte do sistema escreve diretamente nesse registro.
- **FR-003**: O sistema MUST aplicar a máquina de estados oficial do domínio em toda mudança de
  status do pedido — nenhuma transição fora da tabela de estados é permitida.
- **FR-004**: O sistema MUST, ao consumir uma resposta de validação aprovada, atualizar o pedido
  com os itens enriquecidos e os totais calculados, colocá-lo em espera de nota fiscal, e publicar
  uma solicitação de emissão de nota fiscal.
- **FR-005**: O sistema MUST, ao consumir uma resposta de validação reprovada, encerrar o pedido
  como rejeitado, registrando o motivo da rejeição, sem publicar solicitação de nota fiscal.
- **FR-006**: O sistema MUST, ao consumir uma resposta de emissão de nota fiscal bem-sucedida,
  concluir o pedido e registrar a referência da nota fiscal emitida.
- **FR-007**: O sistema MUST, ao consumir uma resposta de emissão de nota fiscal malsucedida,
  marcar o pedido como falho e registrar o motivo técnico.
- **FR-008**: O sistema MUST, ao consumir uma edição de pedido, aceitá-la apenas se o pedido
  estiver em `RECEIVED`, `VALIDATED` ou `REJECTED` — reiniciando o ciclo de processamento (como
  na User Story 1) quando aceita, ou rejeitando como erro de negócio quando o pedido estiver em
  qualquer outro estado.
- **FR-009**: O sistema MUST, ao consumir um cancelamento de pedido, aceitá-lo apenas se o pedido
  estiver em `RECEIVED`, `PROCESSING`, `VALIDATING` ou `VALIDATED` — encerrando o pedido como
  cancelado com o motivo informado quando aceito, ou rejeitando como erro de negócio quando o
  pedido estiver em qualquer outro estado.
- **FR-010**: O sistema MUST ser idempotente em todo consumo de mensagem de qualquer fila que
  processe — reentregar a mesma mensagem não MUST produzir nenhum efeito adicional além do já
  aplicado na primeira vez.
- **FR-011**: O sistema MUST detectar e tratar atualizações concorrentes do mesmo pedido, sem
  perder nem sobrescrever incorretamente uma mudança de estado já aplicada.
- **FR-012**: O sistema MUST tratar mensagens referenciando um pedido inexistente ou em estado
  incompatível como erro técnico, registrado em log, sem aplicar mudanças.

### Key Entities

- **Pedido (`Order`)**: entidade central do domínio, definida em `pedidos_shared` (feature
  `001-fundacao-compartilhada`) — esta feature é a única que escreve nesse registro; as demais
  features apenas leem ou publicam mensagens que o referenciam.
- **Item do pedido (`OrderItem`)**: item individual dentro de um pedido, também definido em
  `pedidos_shared`; enriquecido com preço, desconto e total de linha após a validação.
- **Mensagem publicada/consumida (`MessageEnvelope`)**: envelope padrão de mensagem, definido em
  `pedidos_shared` — esta feature consome de 5 filas e publica em 2, sempre nesse formato.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das solicitações de novo pedido resultam em um registro em processamento e uma
  solicitação de validação publicada, sem intervenção manual.
- **SC-002**: 100% dos pedidos aprovados na validação avançam automaticamente até o estado de
  espera de nota fiscal, sem intervenção manual.
- **SC-003**: 100% dos pedidos com nota fiscal emitida com sucesso terminam concluídos, com a
  referência da nota fiscal registrada.
- **SC-004**: Reprocessar a mesma mensagem não duplica nem corrompe o estado do pedido em nenhum
  dos cenários testados.
- **SC-005**: Nenhuma transição de estado aplicada pelo sistema viola a máquina de estados oficial
  do domínio.
- **SC-006**: 100% das tentativas de editar ou cancelar um pedido em estado incompatível são
  rejeitadas sem alterar o registro do pedido.

## Assumptions

- Este serviço não expõe nenhuma porta HTTP — é um worker que consome filas continuamente
  (constitution I.1, I.2).
- A comunicação com os serviços de validação e de emissão de nota fiscal é inteiramente
  assíncrona via fila — este serviço nunca os chama diretamente nem espera resposta síncrona.
- O formato exato de cada mensagem consumida ou publicada já está definido em
  `docs/01-dominio-e-contratos.md` §5 (contratos de `pedidos_shared`) — esta feature não inventa
  nenhum campo novo.
- Detalhes de execução do consumo de fila (long-polling, tamanho de lote, timeout de
  visibilidade) ficam para o `plan.md` desta feature.
