# Feature Specification: Observabilidade e Reprocessamento de DLQ

**Feature Branch**: `feature/011-observabilidade-dlq`

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "Observabilidade / DLQ — visibilidade das mensagens que falham tecnicamente e vão para a DLQ, e forma de reprocessá-las"

## Clarifications

### Session 2026-10-03

- Q: Segurança do reprocessamento sem autenticação → A: Aberto, sem proteção (igual à 010); autenticação fica para feature futura
- Q: Granularidade do reprocessamento → A: DLQ inteira, ou uma mensagem específica pelo identificador
- Q: Visibilidade do pedido parado → A: Nada muda no pedido nem na listagem; o operador cruza o `order_id` da DLQ com `GET /pedidos/{id}`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Saber se há mensagens paradas em DLQ (Priority: P1)

O operador do sistema consulta, em um único lugar, quantas mensagens estão acumuladas na DLQ de
cada fila do pipeline. Hoje toda fila tem DLQ, mas ninguém olha para elas: uma falha técnica
repetida (3 tentativas) manda a mensagem para a DLQ e o pedido correspondente fica parado num
estado não terminal, sem que nada avise.

**Why this priority**: Sem visibilidade não há como saber que o sistema está perdendo trabalho.
É a base de qualquer tratamento de falha técnica e entrega valor sozinha.

**Independent Test**: Provocar uma falha técnica persistente em um consumidor até a mensagem ir
para a DLQ, consultar o resumo e verificar que a fila afetada mostra contagem maior que zero e as
demais mostram zero.

**Acceptance Scenarios**:

1. **Given** todas as DLQs vazias, **When** o operador consulta o resumo, **Then** vê cada fila do pipeline com contagem `0`.
2. **Given** uma mensagem da `validar_pedido_queue` esgotou as tentativas e foi para a DLQ, **When** o operador consulta o resumo, **Then** a DLQ dessa fila mostra `1` e as outras `0`.
3. **Given** o ambiente local recém-subido, **When** o operador consulta o resumo, **Then** a consulta responde sem exigir configuração adicional.

---

### User Story 2 - Inspecionar uma mensagem em DLQ (Priority: P2)

O operador lista as mensagens de uma DLQ e vê, para cada uma, a qual pedido ela pertence
(`order_id`, `correlation_id`), quando ocorreu e o conteúdo, para entender o que falhou e qual
pedido ficou parado. Documentos pessoais aparecem mascarados.

**Why this priority**: Saber que existe uma mensagem parada (P1) não basta; é preciso ligá-la ao
pedido afetado para decidir o que fazer.

**Independent Test**: Com uma mensagem na DLQ, listar a DLQ e confirmar que a entrada traz o
`order_id` e o `correlation_id` corretos, sem documento em claro, e que a mensagem continua na DLQ
após a listagem.

**Acceptance Scenarios**:

1. **Given** uma mensagem em DLQ, **When** o operador lista aquela DLQ, **Then** vê o `order_id`, o `correlation_id` e o conteúdo da mensagem, com `customer_document` mascarado.
2. **Given** a mesma DLQ, **When** o operador lista duas vezes seguidas, **Then** a mensagem continua presente e a contagem não muda (listar não consome).
3. **Given** um nome de DLQ que não existe, **When** o operador a consulta, **Then** recebe resposta clara de que a fila não existe.

---

### User Story 3 - Reprocessar mensagens da DLQ (Priority: P3)

Depois de corrigir a causa da falha técnica, o operador devolve as mensagens da DLQ à fila de
origem para que o pipeline as processe de novo e o pedido parado volte a andar.

**Why this priority**: Fecha o ciclo (ver → entender → recuperar). Depende de P1 e P2 e só faz
sentido depois que a visibilidade existe.

**Independent Test**: Com uma mensagem na DLQ cuja causa foi corrigida, acionar o reprocessamento
e verificar que a DLQ esvazia e o pedido correspondente chega a um estado terminal.

**Acceptance Scenarios**:

1. **Given** uma mensagem na DLQ e a causa da falha corrigida, **When** o operador aciona o reprocessamento daquela DLQ, **Then** a mensagem volta à fila de origem, a DLQ fica vazia e o pedido avança normalmente.
2. **Given** a mensagem já foi processada com sucesso antes de ir para a DLQ, **When** é reprocessada, **Then** o consumidor a reconhece como já tratada e não duplica transição, pedido nem PDF.
3. **Given** uma DLQ vazia, **When** o operador aciona o reprocessamento, **Then** nada é movido e a resposta informa `0` mensagens reprocessadas.
4. **Given** uma DLQ com várias mensagens, das quais uma é "venenosa" (sempre falha), **When** o operador reprocessa apenas as demais pelo identificador de cada uma, **Then** só essas voltam à fila de origem e a venenosa permanece na DLQ.
5. **Given** um identificador que não está na DLQ, **When** o operador pede para reprocessá-lo, **Then** recebe resposta de "não encontrada" e nada é movido.
6. **Given** a causa ainda não foi corrigida, **When** a mensagem reprocessada falha de novo, **Then** ela volta para a DLQ após as tentativas normais, sem perda.

---

### Edge Cases

- Mensagem em DLQ cujo pedido não existe mais ou nunca chegou a ser criado (ex.: linha de arquivo batch): a listagem mostra a mensagem mesmo assim, sem exigir que o pedido exista.
- DLQ de `s3_notifications_queue` e `pedido_lines_queue`, que não seguem o envelope comum: devem aparecer no resumo e na listagem, mostrando o que for identificável (nome do arquivo/linha em vez de `order_id`).
- DLQ com muitas mensagens: a listagem devolve no máximo um lote limitado e informa que há mais.
- Reprocessamento parcial interrompido no meio: nenhuma mensagem pode ser perdida; cada uma ou continua na DLQ ou já está de volta na fila de origem.
- Duas pessoas reprocessam a mesma DLQ ao mesmo tempo: cada mensagem volta uma única vez à fila de origem, sem duplicar.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST oferecer um resumo com a quantidade de mensagens em cada DLQ do pipeline (as 9 filas de `docs/01-dominio-e-contratos.md` §4).
- **FR-002**: O sistema MUST permitir listar as mensagens de uma DLQ informada, devolvendo para cada uma: identificador da mensagem, `order_id` e `correlation_id` quando existirem, instante de ocorrência e conteúdo.
- **FR-003**: Listar mensagens MUST ser somente leitura: a mensagem permanece na DLQ e fica novamente visível para a próxima consulta.
- **FR-004**: Nenhuma resposta MUST expor documento de cliente em claro; `customer_document` aparece mascarado como nas demais consultas.
- **FR-005**: O sistema MUST permitir reprocessar uma DLQ inteira ou apenas uma mensagem específica, identificada pelo identificador exibido na listagem, devolvendo-a à fila de origem correspondente e informando quantas mensagens foram movidas.
- **FR-006**: O reprocessamento MUST preservar o conteúdo original da mensagem, de modo que a idempotência dos consumidores (por `message_id`) impeça duplicação.
- **FR-007**: O reprocessamento MUST NOT perder mensagens: uma mensagem só deixa a DLQ depois de reenviada com sucesso à fila de origem.
- **FR-008**: Pedir uma DLQ inexistente MUST resultar em resposta de "não encontrada", distinta de DLQ vazia.
- **FR-009**: Toda consulta e todo reprocessamento MUST gerar log estruturado com a DLQ envolvida e a quantidade de mensagens, sem documento em claro.
- **FR-010**: O sistema MUST NOT alterar a tabela de pedidos nem a máquina de estados por conta própria: quem muda o estado do pedido continua sendo o Order Processor, ao consumir a mensagem reprocessada.

### Key Entities *(include if feature involves data)*

- **DLQ**: fila de mensagens que esgotaram as tentativas, uma por fila do pipeline; tem nome, fila de origem e contagem de mensagens.
- **Mensagem em DLQ**: mensagem não processada, com identificador, `order_id`/`correlation_id` (quando houver), instante, conteúdo e a fila de origem a que deve voltar.
- **Reprocessamento**: operação que devolve à fila de origem todas as mensagens de uma DLQ ou uma mensagem específica dela; resultado é a quantidade movida.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O operador descobre, em uma única consulta e em menos de 3 segundos, se existe alguma mensagem parada em qualquer DLQ.
- **SC-002**: Para 100% das mensagens em DLQ com envelope comum, a listagem permite identificar o pedido afetado sem consultar logs ou a infraestrutura diretamente.
- **SC-003**: Após corrigir a causa de uma falha técnica, o operador recupera todos os pedidos parados reprocessando a DLQ, sem editar dados manualmente e sem pedidos duplicados ou PDFs repetidos.
- **SC-004**: Nenhuma resposta ou log do recurso contém documento de cliente em claro.
- **SC-005**: Reprocessar uma DLQ com N mensagens move exatamente N mensagens, e uma segunda execução imediata move 0.

## Assumptions

- O público é o operador do sistema (desenvolvedor/ops). Resumo, listagem e reprocessamento ficam abertos, sem autenticação nem token, como na feature 010; o acesso restrito fica para uma feature de segurança futura. Por isso o recurso é operacional, pensado para o ambiente local, e não deve ser exposto a clientes finais.
- A entrada continua sendo o API Gateway como ingresso HTTP único (constitution I.1); nenhum serviço de processamento passa a chamar outro por HTTP.
- Não há descarte (purge) nem edição de mensagem em DLQ nesta feature; só ver e reprocessar.
- Alertas ativos (e-mail, chat) e métricas de série temporal ficam fora de escopo; o resumo é consultado sob demanda.
- O pedido afetado não recebe indicador nem muda de estado enquanto a mensagem está na DLQ; a listagem não traz o status do pedido, e o operador o consulta pelo `order_id` na consulta de pedidos existente.
- Reprocessar não corrige a causa da falha: o operador a corrige antes (ex.: sobe o serviço que estava fora).
- Ambiente local via Ministack, que suporta SQS com DLQ e redrive já criados pelo bootstrap.
- O mapeamento DLQ → fila de origem segue a convenção de nome `{fila}_dlq` já existente.
