# Feature Specification: API Gateway

**Feature Branch**: `003-api-gateway`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "api-gateway: serviço FastAPI que expõe a API HTTP de entrada do
sistema (§1 do domínio) — recebe requisições de criar/editar/cancelar pedido, valida payload,
gera order_id (UUID v4) e correlation_id, publica MessageEnvelope nas filas
solicitar_pedido_queue/editar_pedido_queue/cancelar_pedido_queue via pedidos_shared, e expõe
endpoint de consulta de status do pedido lendo da tabela orders. Único serviço do sistema que
aceita HTTP de entrada (constitution I.1)."

## Clarifications

### Session 2026-07-19

- Q: US2 faz o Lambda Line Processor chamar o mesmo endpoint uma vez por linha de um arquivo
  batch — a spec precisa definir meta de volume/concorrência para esse cenário? → A: Não — fica
  para o `plan.md`, quando a stack de execução (workers, concorrência) for decidida; SC-001
  (latência por chamada individual) já cobre a experiência de cada requisição.
- Q: A consulta de pedido (US5/FR-008) deve retornar `customer_document` mascarado ou completo,
  dado que a feature não define autenticação/autorização (Assumptions)? → A: Mascarado — usa
  `mask_document` de `pedidos_shared`, a mesma função já exigida para logs, reduzindo a exposição
  do dado sensível já que qualquer chamador com o `order_id` consegue consultar.
- Q: `docs/01-dominio-e-contratos.md` §1 diz que cada linha do arquivo batch processada pelo
  Lambda Line Processor "vira uma chamada ao mesmo API Gateway" — mas a constitution I.1 diz
  "nenhum microserviço chama outro por HTTP". Como resolver esse conflito para o escopo desta
  spec? → A: O domínio vence — o API Gateway expõe o mesmo endpoint de criação de pedido tanto
  para clientes HTTP externos quanto para a chamada interna do Lambda Line Processor no fluxo
  BATCH, exatamente como o diagrama de §1 mostra. Isso é uma exceção explícita a constitution
  I.1 que MUST ser formalizada no `plan.md` desta feature (seção Constitution Check) e
  justificada no PR, conforme a própria constitution prevê para desvios documentados.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cliente solicita um novo pedido (Priority: P1) 🎯 MVP

Como cliente do sistema, preciso enviar uma solicitação de novo pedido e receber uma confirmação
rápida de que foi aceito, para poder acompanhar o processamento sem esperar toda a cadeia de
validação e emissão de nota fiscal terminar.

**Why this priority**: É a porta de entrada de todo o fluxo de negócio — sem ela nenhum pedido
entra no sistema.

**Independent Test**: Enviar uma solicitação de pedido com payload válido e confirmar que a
resposta chega rapidamente com um `order_id` e `correlation_id`, e que uma mensagem correspondente
aparece em `solicitar_pedido_queue`.

**Acceptance Scenarios**:

1. **Given** um payload válido (cliente, documento, 1 a 50 itens com quantidade > 0), **When** o
   cliente solicita um novo pedido, **Then** o sistema aceita a solicitação, gera `order_id` e
   `correlation_id`, publica a mensagem em `solicitar_pedido_queue` e responde com esses
   identificadores sem esperar o processamento completo.
2. **Given** um payload com campo obrigatório ausente, item com quantidade ≤ 0, mais de 50 itens
   ou nenhum item, **When** o cliente solicita um novo pedido, **Then** o sistema rejeita a
   solicitação com um erro claro, sem gerar `order_id` nem publicar nenhuma mensagem.

---

### User Story 2 - Sistema aceita pedidos oriundos do processamento de arquivo batch (Priority: P1)

Como sistema, preciso que o mesmo ponto de entrada usado por clientes HTTP também aceite pedidos
individuais extraídos de um arquivo posicional processado em lote, para que os dois canais de
entrada (online e batch) convirjam para o mesmo pipeline de processamento sem lógica duplicada.

**Why this priority**: Mesma urgência da User Story 1 — sem essa convergência, o fluxo BATCH
completo (`docs/01-dominio-e-contratos.md` §1) fica sem porta de entrada.

**Independent Test**: Simular uma chamada com os dados de uma linha de pedido extraída de um
arquivo batch (`channel = "BATCH"`, `source_file` e `source_line` preenchidos) e confirmar que o
sistema aceita e publica exatamente como aceitaria uma solicitação idêntica vinda de um cliente
HTTP direto.

**Acceptance Scenarios**:

1. **Given** uma linha de pedido válida extraída de um arquivo batch, com `source_file` e
   `source_line` preenchidos, **When** o Lambda Line Processor faz a chamada correspondente,
   **Then** o sistema aceita, gera `order_id`/`correlation_id` e publica em
   `solicitar_pedido_queue` com `channel = "BATCH"` e os campos de origem preenchidos.
2. **Given** os mesmos dados de negócio, **When** vêm de um cliente HTTP direto (`channel =
   "HTTP"`) ou de uma linha de arquivo batch (`channel = "BATCH"`), **Then** o sistema aplica as
   mesmas regras de validação e o mesmo formato de mensagem publicada, diferindo apenas em
   `channel`, `source_file` e `source_line`.

---

### User Story 3 - Cliente edita um pedido existente (Priority: P2)

Como cliente, preciso poder corrigir um pedido já enviado (itens, quantidades) enquanto ele ainda
não foi concluído, cancelado ou rejeitado definitivamente, para não precisar abrir um pedido novo
por um erro de digitação ou mudança de ideia.

**Why this priority**: Importante para a experiência do cliente, mas o sistema já entrega valor
completo (criar e consultar pedidos) sem essa capacidade.

**Independent Test**: Criar um pedido, depois enviar uma edição e confirmar que uma mensagem
aparece em `editar_pedido_queue` com o `order_id` original.

**Acceptance Scenarios**:

1. **Given** um pedido em estado `RECEIVED`, `VALIDATED` ou `REJECTED`, **When** o cliente envia
   uma edição, **Then** o sistema aceita, publica em `editar_pedido_queue` e responde com o mesmo
   `order_id`.
2. **Given** um pedido em estado terminal `COMPLETED`, `CANCELLED` ou `FAILED`, **When** o cliente
   tenta editá-lo, **Then** o sistema rejeita com um erro de conflito, sem publicar nenhuma
   mensagem.
3. **Given** um `order_id` que não existe, **When** o cliente tenta editá-lo, **Then** o sistema
   responde com um erro de "não encontrado".

---

### User Story 4 - Cliente cancela um pedido existente (Priority: P2)

Como cliente, preciso poder cancelar um pedido que ainda está em processamento, para desistir da
compra antes da nota fiscal ser emitida.

**Why this priority**: Mesma faixa de importância da edição — melhora a experiência, não bloqueia
o fluxo principal.

**Independent Test**: Criar um pedido, enviar um cancelamento e confirmar que uma mensagem aparece
em `cancelar_pedido_queue` com o `order_id` e o motivo informado.

**Acceptance Scenarios**:

1. **Given** um pedido em estado `RECEIVED`, `PROCESSING`, `VALIDATING` ou `VALIDATED`, **When**
   o cliente cancela o pedido informando um motivo, **Then** o sistema aceita e publica em
   `cancelar_pedido_queue` com o `order_id` e o motivo.
2. **Given** um pedido em estado terminal (`COMPLETED`, `CANCELLED`, `REJECTED` ou `FAILED`),
   **When** o cliente tenta cancelá-lo, **Then** o sistema rejeita com um erro de conflito.
3. **Given** um `order_id` que não existe, **When** o cliente tenta cancelá-lo, **Then** o sistema
   responde com um erro de "não encontrado".

---

### User Story 5 - Cliente consulta um pedido específico (Priority: P3)

Como cliente, preciso consultar os detalhes e o status atual de um pedido que já enviei, para
acompanhar o andamento sem precisar contatar suporte.

**Why this priority**: Conveniência de acompanhamento — não bloqueia a criação nem o processamento
dos pedidos.

**Independent Test**: Criar um pedido, aguardar o processamento avançar e consultar o mesmo
`order_id`, confirmando que os dados retornados batem com o estado real do pedido na tabela
`orders`.

**Acceptance Scenarios**:

1. **Given** um pedido existente na tabela `orders`, **When** o cliente consulta pelo `order_id`,
   **Then** o sistema retorna os dados do pedido (incluindo `status` e `status_reason` quando
   aplicável) com `customer_document` mascarado — só os últimos 4 dígitos visíveis.
2. **Given** um `order_id` que não existe (ou ainda não foi persistido pelo Order Processor),
   **When** o cliente consulta, **Then** o sistema responde com um erro de "não encontrado".

---

### User Story 6 - Cliente lista os próprios pedidos (Priority: P3)

Como cliente, preciso listar todos os meus pedidos, do mais recente para o mais antigo, para ter
uma visão geral do meu histórico sem precisar saber cada `order_id` de cabeça.

**Why this priority**: Conveniência adicional sobre a consulta individual (User Story 5) — usa o
mesmo dado, só agrupado por cliente.

**Independent Test**: Criar dois ou mais pedidos para o mesmo `customer_id` e confirmar que a
listagem retorna todos, ordenados do mais recente para o mais antigo.

**Acceptance Scenarios**:

1. **Given** um `customer_id` com um ou mais pedidos, **When** o cliente lista seus pedidos,
   **Then** o sistema retorna todos eles ordenados do mais recente para o mais antigo, cada um com
   `customer_document` mascarado (mesma regra da User Story 5).
2. **Given** um `customer_id` sem nenhum pedido, **When** o cliente lista seus pedidos, **Then**
   o sistema retorna uma lista vazia (não um erro).

---

### Edge Cases

- Payload de criação com `customer_id` maior que 20 caracteres ou não alfanumérico → rejeitado.
- Payload de criação com `customer_document` contendo caracteres não numéricos → rejeitado.
- Consulta de pedido logo após a criação, antes do Order Processor consumir a mensagem e persistir
  o registro em `orders` → "não encontrado" temporariamente (consistência eventual); não é erro do
  sistema.
- Falha técnica ao publicar a mensagem na fila (ex.: fila indisponível) → a solicitação HTTP falha
  com erro técnico; nenhum `order_id` é retornado como aceito; o cliente decide se tenta de novo.
- Edição de um pedido `REJECTED` é permitida (reabre o ciclo) — diferente dos demais estados
  terminais, que rejeitam qualquer edição ou cancelamento.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST expor um ponto de entrada para solicitação de novo pedido que aceita
  tanto clientes externos quanto a chamada interna do processamento de arquivo batch
  (`docs/01-dominio-e-contratos.md` §1) — mesma validação e mesmo formato de mensagem publicada
  para os dois canais, diferindo apenas em `channel`, `source_file` e `source_line`.
- **FR-002**: O sistema MUST validar o payload de criação/edição de pedido: `customer_id` (até 20
  caracteres, alfanumérico), `customer_name`, `customer_document` (somente dígitos), `items` (1 a
  50 itens, cada um com `product_id` e `quantity > 0`) — rejeitando com erro claro qualquer campo
  ausente ou fora dessas regras.
- **FR-003**: O sistema MUST gerar `order_id` (UUID v4) e `correlation_id` (UUID v4) para cada
  novo pedido aceito.
- **FR-004**: O sistema MUST publicar o pedido aceito na fila correspondente à operação
  (`solicitar_pedido_queue` para criação, `editar_pedido_queue` para edição,
  `cancelar_pedido_queue` para cancelamento), envelopado conforme o contrato de mensagem
  compartilhado — o sistema nunca escreve diretamente na tabela `orders`.
- **FR-005**: O sistema MUST responder à solicitação assim que a mensagem for publicada com
  sucesso, sem esperar o processamento completo do pedido pelas demais partes do sistema.
- **FR-006**: O sistema MUST aceitar edição apenas de pedidos em `RECEIVED`, `VALIDATED` ou
  `REJECTED`, e cancelamento apenas de pedidos em `RECEIVED`, `PROCESSING`, `VALIDATING` ou
  `VALIDATED` — rejeitando com erro de conflito qualquer tentativa sobre os demais estados
  terminais.
- **FR-007**: O sistema MUST exigir um motivo (`reason`) em toda solicitação de cancelamento.
- **FR-008**: O sistema MUST expor consulta de um pedido específico por `order_id`, lendo os dados
  atuais da tabela `orders`, retornando `customer_document` mascarado (só os últimos 4 dígitos
  visíveis, via `mask_document` de `pedidos_shared`) — nunca o documento completo.
- **FR-009**: O sistema MUST expor listagem de pedidos por `customer_id`, ordenados do mais
  recente para o mais antigo.
- **FR-010**: O sistema MUST responder com um erro de "não encontrado" ao consultar, editar ou
  cancelar um `order_id` que não existe na tabela `orders`.

### Key Entities

- **Pedido (`Order`)**: entidade central do domínio, definida em `pedidos_shared` (feature
  `001-fundacao-compartilhada`) — esta feature apenas lê (consulta/listagem) e publica mensagens
  que o referenciam; nunca redefine nem escreve o registro diretamente.
- **Item do pedido (`OrderItem`)**: item individual dentro de um pedido, também definido em
  `pedidos_shared`.
- **Mensagem publicada (`MessageEnvelope`)**: envelope padrão de mensagem enfileirada, definido em
  `pedidos_shared` — esta feature monta o `payload` específico de cada operação (criar/editar/
  cancelar) conforme `docs/01-dominio-e-contratos.md` §5.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um cliente recebe a confirmação de aceite de um novo pedido (com `order_id`) em
  menos de 1 segundo, sem esperar o processamento completo do pedido.
- **SC-002**: 100% das solicitações com payload inválido são rejeitadas com uma mensagem de erro
  clara, sem gerar `order_id` nem publicar nenhuma mensagem.
- **SC-003**: Um cliente consegue consultar o status atual de qualquer pedido já persistido em uma
  única chamada.
- **SC-004**: Um cliente consegue listar todos os seus pedidos, mais recentes primeiro, em uma
  única chamada.
- **SC-005**: 100% das tentativas de editar ou cancelar um pedido em estado terminal (exceto
  reabrir um pedido `REJECTED`) são rejeitadas com erro de conflito, sem alterar o estado do
  pedido.
- **SC-006**: O mesmo ponto de entrada processa corretamente tanto pedidos vindos de clientes HTTP
  quanto pedidos extraídos de arquivo batch, sem exigir regras de validação diferentes entre os
  dois canais.

## Assumptions

- Autenticação e autorização de clientes não são especificadas em
  `docs/01-dominio-e-contratos.md` e ficam fora do escopo desta feature.
- O sistema nunca escreve diretamente na tabela `orders` — apenas o Order Processor persiste o
  pedido, ao consumir a mensagem publicada. Consultar um pedido imediatamente após criá-lo pode
  retornar "não encontrado" por uma janela breve, até o Order Processor processar a mensagem
  (consistência eventual, consistente com constitution I.2 — nenhum componente bloqueia esperando
  resposta de outro).
- Reenviar uma solicitação após falha técnica na publicação gera um novo `order_id` — não há
  deduplicação de solicitação HTTP nesta feature (a idempotência do sistema atua no consumo da
  mensagem, não na entrada HTTP).
- A listagem por `customer_id` (User Story 6) não define paginação nesta feature; se o volume de
  pedidos por cliente exigir, paginação é uma melhoria futura.
- O ponto de entrada compartilhado entre clientes HTTP e o processamento de arquivo batch (User
  Story 2) é uma exceção explícita à leitura restritiva de constitution I.1, decidida na sessão de
  clarificação acima — a exceção MUST ser formalizada no `plan.md` desta feature e justificada no
  PR.
- Meta de volume/concorrência para o cenário de múltiplas chamadas em sequência vindas do
  processamento de arquivo batch (User Story 2) não é definida nesta spec — fica para o `plan.md`,
  quando a stack de execução for decidida; SC-001 já cobre a latência de cada chamada individual.
