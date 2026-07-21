# Feature Specification: Lambda Line Processor

**Feature Branch**: `008-lambda-line-processor`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "Servico serverless (Lambda) que consome pedido_lines_queue (payload sem MessageEnvelope, formato: source_file, line_number, operation, raw_line, order_id, parsed — docs/01-dominio-e-contratos.md §5) e, para cada mensagem, chama o endpoint HTTP correspondente do API Gateway já existente: POST /pedidos (SOLICITAR, corpo = parsed), PUT /pedidos/{order_id} (EDITAR, corpo = parsed) ou POST /pedidos/{order_id}/cancelamento (CANCELAR, corpo = parsed). Resposta 2xx do API Gateway confirma a mensagem. Resposta 4xx (400/404/409) é rejeição de negócio permanente (pedido inválido, não encontrado, ou em estado que não permite a operação) — confirma a mensagem sem repetir. Falha técnica (timeout, erro de conexão, 5xx do API Gateway) não confirma a mensagem, permitindo redrive nativo do SQS. Não escreve na tabela orders nem em nenhuma fila — é o último elo da entrada em lote, fecha o pipeline iniciado pelo File Consumer (007-file-consumer)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Encaminhar linha de pedido válida para o API Gateway (Priority: P1) MVP

Depois que uma linha de um arquivo em lote foi extraída e traduzida para o formato de comando
(solicitação, edição ou cancelamento de pedido), o sistema precisa efetivamente realizar essa
chamada ao mesmo ponto de entrada HTTP usado por clientes online, para que o pedido siga o mesmo
fluxo de processamento.

**Why this priority**: Sem esse encaminhamento, nenhum pedido enviado por arquivo chega de fato a
existir no sistema — é o elo final que fecha a entrada em lote, motivo de existir deste serviço.

**Independent Test**: Publicar uma mensagem em `pedido_lines_queue` com `operation="SOLICITAR"` e
`parsed` completo; verificar que uma chamada `POST /pedidos` é feita com o corpo de `parsed` e que,
recebendo `2xx`, a mensagem original não é reentregue.

**Acceptance Scenarios**:

1. **Given** uma mensagem com `operation="SOLICITAR"`, **When** processada, **Then** o sistema
   chama `POST /pedidos` com o corpo igual a `parsed`; uma resposta `2xx` confirma a mensagem.
2. **Given** uma mensagem com `operation="EDITAR"` e `order_id` preenchido, **When** processada,
   **Then** o sistema chama `PUT /pedidos/{order_id}` com o corpo igual a `parsed`; uma resposta
   `2xx` confirma a mensagem.
3. **Given** uma mensagem com `operation="CANCELAR"` e `order_id` preenchido, **When** processada,
   **Then** o sistema chama `POST /pedidos/{order_id}/cancelamento` com o corpo igual a `parsed`;
   uma resposta `2xx` confirma a mensagem.

---

### User Story 2 - Descartar linha com rejeição de negócio permanente (Priority: P1)

Quando o API Gateway recusa a chamada por um motivo que não muda com uma nova tentativa (dados
inválidos, pedido inexistente, ou pedido em um estado que não permite a operação pedida), o
sistema precisa aceitar essa recusa como definitiva e seguir em frente, em vez de insistir
indefinidamente na mesma linha.

**Why this priority**: Sem esse tratamento, uma única linha malformada ou desatualizada
travaria o processamento daquele item para sempre (redrive infinito até a fila de erro), exigindo
intervenção manual desnecessária.

**Independent Test**: Publicar uma mensagem cuja chamada ao API Gateway responda `404` (pedido
inexistente) ou `409` (estado inválido); verificar que a mensagem original não é reentregue e que
o motivo da recusa fica registrado.

**Acceptance Scenarios**:

1. **Given** uma mensagem `EDITAR`/`CANCELAR` referenciando um `order_id` inexistente, **When**
   processada e o API Gateway responde `404`, **Then** a mensagem é confirmada (não reentregue) e
   o motivo é registrado.
2. **Given** uma mensagem cuja chamada ao API Gateway responde `409` (pedido em estado que não
   permite a operação), **When** processada, **Then** a mensagem é confirmada e o motivo é
   registrado.
3. **Given** uma mensagem cujo `parsed` é rejeitado pelo API Gateway com `400` (dado inválido),
   **When** processada, **Then** a mensagem é confirmada e o motivo é registrado.

---

### User Story 3 - Preservar disponibilidade diante de falha técnica do API Gateway (Priority: P2)

Se o API Gateway estiver temporariamente indisponível ou não responder a tempo, o sistema não deve
tratar isso como uma recusa definitiva — deve preservar a mensagem para tentar de novo mais tarde,
como já acontece nos demais workers do sistema.

**Why this priority**: Tratar uma instabilidade passageira do API Gateway como "recusa permanente"
descartaria pedidos legítimos que nunca chegaram a ser realmente processados.

**Independent Test**: Simular indisponibilidade ou timeout do API Gateway ao processar uma
mensagem; verificar que a mensagem original não é confirmada nem descartada, permanecendo
disponível para nova tentativa.

**Acceptance Scenarios**:

1. **Given** o API Gateway está indisponível, retorna erro `5xx`, ou não responde dentro do tempo
   esperado, **When** o sistema tenta processar a mensagem, **Then** a mensagem original não é
   confirmada, permanece disponível para nova tentativa, e o erro é registrado em log.

---

### User Story 4 - Reprocessar a mesma linha sem duplicar a chamada (Priority: P3)

Como qualquer fila pode entregar a mesma mensagem mais de uma vez, chamar o API Gateway duas vezes
para a mesma linha poderia criar um pedido duplicado (no caso de `SOLICITAR`) ou repetir uma edição
já aplicada.

**Why this priority**: Reforça a garantia de idempotência já adotada pelos outros workers do
sistema; prioridade menor porque a duplicidade de entrega é rara, mas precisa ser coberta antes de
produção.

**Independent Test**: Processar ou entregar a mesma mensagem duas vezes; verificar que o API
Gateway é chamado apenas uma vez para aquela linha.

**Acceptance Scenarios**:

1. **Given** uma mensagem já processada com sucesso, **When** ela chega novamente ao sistema,
   **Then** nenhuma nova chamada ao API Gateway é feita, e a duplicidade é registrada em log de
   nível informativo.

---

### Edge Cases

- Mensagem com `operation` diferente de `SOLICITAR`/`EDITAR`/`CANCELAR`: tratada como rejeição de
  negócio permanente (US2) — não há chamada correspondente a fazer, e tentar de novo não muda isso.
- Mensagem `EDITAR`/`CANCELAR` sem `order_id` preenchido: tratada como rejeição de negócio
  permanente (US2) — dado necessário para montar a chamada está ausente.
- API Gateway responde `2xx` mas com corpo inesperado/vazio: considerado sucesso pelo código de
  status; o conteúdo da resposta não é usado por este serviço.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE consumir mensagens de `pedido_lines_queue` contendo `operation`,
  `order_id`, e `parsed`.
- **FR-002**: Para `operation="SOLICITAR"`, o sistema DEVE chamar o endpoint de criação de pedido
  do API Gateway com o corpo igual a `parsed`.
- **FR-003**: Para `operation="EDITAR"`, o sistema DEVE chamar o endpoint de edição de pedido do
  API Gateway, identificado por `order_id`, com o corpo igual a `parsed`.
- **FR-004**: Para `operation="CANCELAR"`, o sistema DEVE chamar o endpoint de cancelamento de
  pedido do API Gateway, identificado por `order_id`, com o corpo igual a `parsed`.
- **FR-005**: O sistema DEVE confirmar a mensagem original quando a chamada ao API Gateway
  responder com sucesso (`2xx`).
- **FR-006**: O sistema DEVE confirmar a mensagem original, registrando o motivo, quando a chamada
  ao API Gateway responder com uma recusa de negócio permanente (`400`, `404` ou `409`) —  sem
  tentar novamente, já que os mesmos dados nunca produziriam um resultado diferente.
- **FR-007**: O sistema DEVE confirmar a mensagem original, registrando o motivo, quando a
  mensagem tiver `operation` desconhecida ou `order_id` ausente para `EDITAR`/`CANCELAR` — mesmo
  tratamento de rejeição permanente (Edge Cases).
- **FR-008**: O sistema NÃO DEVE confirmar a mensagem original quando a chamada ao API Gateway
  falhar por motivo técnico (indisponibilidade, timeout, erro de conexão, `5xx`) — a mensagem deve
  permanecer disponível para nova tentativa via redrive da fila.
- **FR-009**: O sistema DEVE preservar a idempotência: reprocessar a mesma mensagem não deve
  gerar uma nova chamada ao API Gateway.
- **FR-010**: O sistema NUNCA DEVE escrever diretamente na tabela `orders` nem publicar em
  nenhuma fila — a única saída deste serviço é a chamada HTTP ao API Gateway.
- **FR-011**: O sistema DEVE expor um endpoint de verificação de saúde (`health check`), seguindo
  o mesmo padrão dos demais workers do sistema.
- **FR-012**: O sistema DEVE evitar registrar em log o `customer_document` sem mascaramento.

### Key Entities

- **Linha de pedido**: dados recebidos via `pedido_lines_queue` — arquivo/linha de origem,
  operação (`SOLICITAR`/`EDITAR`/`CANCELAR`), identificador do pedido (quando aplicável) e o corpo
  já pronto para a chamada HTTP correspondente.
- **Resultado da chamada**: o código de status HTTP retornado pelo API Gateway, usado para decidir
  entre confirmar a mensagem (sucesso ou recusa permanente) ou preservá-la para nova tentativa
  (falha técnica).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das linhas de pedido válidas resultam em uma chamada ao endpoint correto do
  API Gateway em até alguns segundos após a publicação da mensagem.
- **SC-002**: 100% das linhas rejeitadas por motivo de negócio permanente (`400`/`404`/`409`) são
  confirmadas sem gerar nova tentativa, com o motivo registrado.
- **SC-003**: Nenhuma chamada duplicada ao API Gateway ocorre quando a mesma mensagem é entregue
  mais de uma vez.
- **SC-004**: Nenhuma decisão (sucesso ou recusa) é tomada quando o API Gateway está
  temporariamente indisponível — 100% desses casos preservam a mensagem original para nova
  tentativa.

## Assumptions

- O File Consumer (`007-file-consumer`) é o único publicador de `pedido_lines_queue`; este
  serviço é o único consumidor. `pedido_lines_queue` não usa o `MessageEnvelope` comum — mesma
  decisão de `007-file-consumer`.
- Idempotência é obtida pelo `MessageId` nativo do SQS (não há `message_id` de domínio no payload
  desta fila) — mesmo padrão adotado em `007-file-consumer`.
- O corpo (`parsed`) já está no formato exigido pelos endpoints do API Gateway
  (`POST /pedidos`, `PUT /pedidos/{order_id}`, `POST /pedidos/{order_id}/cancelamento`) — este
  serviço não valida nem transforma esse conteúdo, apenas o encaminha.
- `400`, `404` e `409` são os únicos códigos de recusa de negócio permanente hoje produzidos pelo
  API Gateway para esses três endpoints; qualquer outro código de erro (`401`, `403`, `422`, etc.)
  não é esperado neste fluxo e, se ocorrer, é tratado como falha técnica (redrive), já que não há
  uma regra de negócio conhecida associada a ele.
- Este serviço roda localmente como um processo persistente com loop de consumo próprio e
  `GET /health`, no mesmo padrão dos demais workers — a constitution IV exige o health check
  "mesmo nos workers", sem abrir exceção para um serviço "serverless"; a natureza "Lambda"
  descreve aqui o papel arquitetural (função de tradução sem estado, sem tabela própria, sem
  regra de negócio própria), não uma forma de execução local diferente das demais.
