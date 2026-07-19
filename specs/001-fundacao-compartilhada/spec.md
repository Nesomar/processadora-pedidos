# Feature Specification: Fundação Compartilhada (pedidos_shared)

**Feature Branch**: `001-fundacao-compartilhada`

**Created**: 2026-07-18 | **Revised**: 2026-07-18 (realinhado a `docs/01-dominio-e-contratos.md`)

**Status**: Draft

**Input**: User description: "001-fundacao-compartilhada" — realinhado à fonte de verdade de
domínio do projeto, `docs/01-dominio-e-contratos.md`, que define entidades, máquina de estados,
filas, contratos de mensagem e layout do arquivo posicional exatos do sistema.

## Clarifications

### Session 2026-07-18 (rework pós-leitura de docs/01-dominio-e-contratos.md)

- Q: (implícita) Quais os estados exatos da máquina de estados, nomes de fila, mecanismo de
  idempotência e layout do arquivo posicional? → A: Todos definidos por
  `docs/01-dominio-e-contratos.md`, que é a fonte da verdade referenciada por todas as features
  deste sistema — substitui as decisões anteriores desta spec (enum de 7 estados em português,
  fila de exemplo única, parser genérico sem layout).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Contrato de mensagens e máquina de estados únicos (Priority: P1)

Como desenvolvedor de qualquer serviço do sistema (api-gateway, order-processor, order-validator,
pdf-generator, file-consumer, lambda-line-processor), preciso importar de um único pacote
compartilhado o modelo `Order`, o enum `OrderStatus` (com suas transições válidas) e o envelope de
mensagem `MessageEnvelope`, para que nenhum serviço redefina esses contratos localmente e todo o
sistema use exatamente o mesmo vocabulário de domínio descrito em
`docs/01-dominio-e-contratos.md`.

**Why this priority**: Sem um contrato único, cada serviço divergiria na forma da mensagem ou nos
nomes de estado, quebrando a máquina de estados e a comunicação assíncrona entre componentes — é a
base de tudo o mais no sistema.

**Independent Test**: Em um serviço de teste isolado, importar o pacote, instanciar `Order`,
`OrderItem` e `MessageEnvelope`, serializar para JSON e validar que a validação Pydantic rejeita um
payload com campo obrigatório ausente ou com um valor de `status` fora do enum `OrderStatus`.

**Acceptance Scenarios**:

1. **Given** o pacote compartilhado instalado em um serviço, **When** o serviço importa `Order` ou
   `MessageEnvelope`, **Then** o modelo valida corretamente um payload válido e rejeita um payload
   inválido com erro claro.
2. **Given** dois serviços diferentes que leem o mesmo tipo de mensagem, **When** cada um importa
   o modelo do pacote compartilhado, **Then** ambos usam exatamente a mesma definição de campos.
3. **Given** o enum `OrderStatus`, **When** um serviço tenta persistir uma transição que não consta
   na tabela de transições de `docs/01-dominio-e-contratos.md` §2.3, **Then** a tentativa falha na
   validação antes de qualquer escrita no DynamoDB.

---

### User Story 2 - Configuração e clientes de infraestrutura sem valores hardcoded (Priority: P1)

Como desenvolvedor de um serviço, preciso de um `Settings` Pydantic e de clientes SQS/DynamoDB/S3
pré-configurados que leem o endpoint do Ministack e os nomes de fila/tabela/bucket de variáveis de
ambiente — usando os mesmos nomes de variável que o Ministack já usa nativamente
(`AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
docs/01-dominio-e-contratos.md §8) — para que nenhum serviço hardcode um valor de infraestrutura.

**Why this priority**: É pré-requisito para o princípio local-first da constitution — sem isso,
cada serviço reimplementaria sua própria configuração de forma inconsistente.

**Independent Test**: Definir as variáveis de ambiente apontando para uma instância local do
Ministack, instanciar o cliente SQS do pacote, enviar uma mensagem de teste para uma das 9 filas
descritas em `docs/01-dominio-e-contratos.md` §4 e confirmar que ela é recebida.

**Acceptance Scenarios**:

1. **Given** as variáveis de ambiente de infraestrutura definidas, **When** um serviço instancia
   `Settings`, **Then** os valores de conexão (`aws_endpoint_url`, `aws_region`,
   `aws_access_key_id`, `aws_secret_access_key`) e os nomes de recurso usados por aquele serviço
   são carregados corretamente.
2. **Given** uma variável de ambiente de conexão obrigatória ausente, **When** um serviço tenta
   instanciar `Settings`, **Then** a inicialização falha imediatamente com uma mensagem indicando
   qual variável está faltando.
3. **Given** o cliente SQS do pacote compartilhado, **When** um serviço envia e depois consome uma
   mensagem em qualquer uma das 9 filas do domínio, **Then** a operação usa o `endpoint_url` do
   Ministack sem nenhuma URL fixa no código do serviço.

---

### User Story 3 - Idempotência de consumo via tabela `processed_messages` (Priority: P2)

Como desenvolvedor de qualquer serviço consumidor de fila, preciso de uma função compartilhada que
verifica e registra o `message_id` na tabela `processed_messages` (`docs/01-dominio-e-contratos.md`
§3) antes de processar uma mensagem, para que reprocessar a mesma mensagem (redelivery do SQS) não
duplique pedidos, PDFs ou transições de estado (constitution I.3).

**Why this priority**: Sem isso, todo consumidor teria que reimplementar sua própria lógica de
idempotência, e o risco de duplicação em reprocessamento é alto — mas depende dos modelos e
clientes de US1/US2 já existirem.

**Independent Test**: Chamar a função de idempotência duas vezes seguidas com o mesmo `message_id`
contra uma tabela `processed_messages` real (Ministack) e confirmar que a segunda chamada indica
"já processado" sem levantar exceção, e que a gravação condicional da primeira chamada falha se
repetida em paralelo.

**Acceptance Scenarios**:

1. **Given** uma mensagem nunca processada, **When** o consumidor chama
   `mark_message_processed(message_id, consumer)`, **Then** a função grava o registro
   condicionalmente e retorna que a mensagem MUST ser processada.
2. **Given** uma mensagem cujo `message_id` já foi registrado por aquele mesmo `consumer`,
   **When** o consumidor chama a função de novo, **Then** ela retorna que a mensagem já foi
   processada, sem exceção — o chamador descarta a mensagem em log nível `info`
   (docs/01-dominio-e-contratos.md §3).
3. **Given** um registro de idempotência gravado, **When** o TTL nativo do DynamoDB expira (7 dias),
   **Then** o registro é removido automaticamente pelo Ministack/DynamoDB — nenhuma limpeza manual
   é responsabilidade do pacote compartilhado.

---

### User Story 4 - Logging estruturado rastreável e mascaramento de documento (Priority: P2)

Como desenvolvedor, preciso de um logger que emita logs estruturados em JSON incluindo `orderId` e
`correlationId` automaticamente quando disponíveis, e de uma função de mascaramento de documento do
cliente, para rastrear o fluxo de um pedido entre serviços sem expor dados sensíveis em log
(constitution VII.6).

**Why this priority**: Observabilidade e proteção de dado sensível são necessárias desde a primeira
mensagem processada, mas o sistema funciona (de forma pior/mais arriscada) sem isso — por isso vem
depois do contrato, da configuração e da idempotência.

**Independent Test**: Chamar o logger com `orderId`/`correlationId` no contexto, capturar stdout,
validar JSON bem formado; chamar `mask_document` e validar que só os últimos 4 caracteres do
`customer_document` ficam visíveis.

**Acceptance Scenarios**:

1. **Given** um `orderId` e `correlationId` no contexto de execução, **When** o serviço registra um
   log, **Then** a linha de log é um JSON válido contendo esses dois campos.
2. **Given** nenhum `orderId` disponível (ex: log de inicialização do serviço), **When** o serviço
   registra um log, **Then** a linha ainda é um JSON válido, sem lançar exceção.
3. **Given** uma mensagem recebida contendo `correlation_id` (via `MessageEnvelope`), **When** o
   serviço processa e publica uma nova mensagem para a próxima etapa, **Then** o `correlation_id`
   da nova mensagem é idêntico ao da mensagem recebida (docs/01-dominio-e-contratos.md §5).
4. **Given** um `customer_document` de 11 dígitos, **When** ele é logado através da função de
   mascaramento, **Then** só os últimos 4 dígitos aparecem em claro.

---

### User Story 5 - Parser do arquivo posicional do sistema (Priority: P3)

Como desenvolvedor do file-consumer / lambda-line-processor, preciso de um parser que interprete o
layout posicional exato descrito em `docs/01-dominio-e-contratos.md` §6 (header tipo `0`, detalhe
de pedido tipo `1`, detalhe de item tipo `2`, trailer tipo `9`, linhas de 200 caracteres), para
converter um arquivo de pedidos em lote nas mesmas estruturas usadas pelo fluxo HTTP.

**Why this priority**: Só é usado pelo fluxo de arquivo (canal `BATCH`), por isso vem por último —
mas o layout já é conhecido e fixo, não mais um placeholder genérico.

**Independent Test**: Parsear um arquivo de exemplo com header, um pedido com dois itens e trailer,
e validar que os registros extraídos batem com os campos esperados; testar cada regra de rejeição
da seção "Regras de parsing" do domínio isoladamente.

**Acceptance Scenarios**:

1. **Given** um arquivo bem formado (header + 1+ pedidos com seus itens + trailer, todas as linhas
   com 200 caracteres), **When** o parser processa o arquivo, **Then** retorna os registros de
   header, pedidos e itens corretamente tipados e associados.
2. **Given** uma linha com tamanho diferente de 200 caracteres, **When** o parser processa o
   arquivo, **Then** aquela linha é rejeitada e registrada no relatório de erros, e o processamento
   continua nas demais linhas.
3. **Given** um arquivo sem header ou sem trailer, **When** o parser processa o arquivo, **Then** o
   arquivo inteiro é rejeitado — nenhuma linha é enviada para fila.
4. **Given** um trailer cujos contadores (`total_orders`, `total_items`) divergem da contagem real
   de registros tipo `1`/`2`, **When** o parser processa o arquivo, **Then** o arquivo inteiro é
   rejeitado.
5. **Given** um registro tipo `2` (item) sem um registro tipo `1` (pedido) antecedente, **When** o
   parser processa o arquivo, **Then** aquela linha é rejeitada, sem rejeitar o arquivo inteiro.
6. **Given** um pedido cujo `item_count` declarado diverge da quantidade real de registros tipo `2`
   associados a ele, **When** o parser processa o arquivo, **Then** aquele pedido específico é
   rejeitado (não o arquivo inteiro).

---

### Edge Cases

- Variável de ambiente de conexão obrigatória ausente → `Settings` falha de forma clara na
  inicialização (US2).
- Mensagem recebida que não corresponde a nenhum modelo Pydantic conhecido (schema desconhecido ou
  versão divergente).
- `message_id` reprocessado (redelivery do SQS) → idempotência via `processed_messages` evita
  duplicação (US3).
- Linha de arquivo posicional com tamanho ≠ 200 caracteres → linha rejeitada, arquivo continua
  (US5).
- Header/trailer ausente, contadores do trailer divergentes, registro tipo `2` órfão, `item_count`
  divergente → tratados conforme "Regras de parsing" (US5).
- `customer_document` com menos de 4 caracteres → `mask_document` mascara integralmente (sem expor
  nenhum dígito real).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O pacote compartilhado MUST expor os modelos Pydantic v2 `Order` e `OrderItem`
  exatamente com os campos definidos em `docs/01-dominio-e-contratos.md` §2.2 (incluindo `version`
  para controle de concorrência otimista e `Decimal` em todo campo monetário).
- **FR-002**: O pacote compartilhado MUST expor o enum `OrderStatus` com exatamente os 9 estados de
  `docs/01-dominio-e-contratos.md` §2.3 (`RECEIVED, PROCESSING, VALIDATING, VALIDATED, REJECTED,
  INVOICING, COMPLETED, CANCELLED, FAILED`) e uma função `is_valid_transition(current, next) ->
  bool` que implementa exatamente a tabela de transições daquela seção.
- **FR-003**: O pacote compartilhado MUST expor `MessageEnvelope` (`message_id`, `correlation_id`,
  `order_id`, `occurred_at`, `payload`) conforme §5, usado por toda mensagem trocada entre serviços.
- **FR-004**: Nenhum serviço MUST redefinir localmente `Order`, `OrderItem`, `OrderStatus` ou
  `MessageEnvelope` — todo serviço importa essas definições do pacote compartilhado.
- **FR-005**: O pacote compartilhado MUST expor um `Settings` Pydantic que carrega, de variáveis de
  ambiente, os valores de conexão (`AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY` — obrigatórios) e os nomes de recurso (tabela `orders`, tabela
  `processed_messages`, bucket `pedidos-bucket`, URLs das 9 filas de §4 — cada um lido de uma
  variável própria, sem hardcode).
- **FR-006**: O `Settings` MUST falhar de forma explícita e imediata na inicialização quando uma
  variável de ambiente de conexão obrigatória estiver ausente.
- **FR-007**: O pacote compartilhado MUST expor clientes wrapper para SQS, DynamoDB e S3 que usam
  o `aws_endpoint_url` do `Settings` em vez de um endpoint fixo.
- **FR-008**: O pacote compartilhado MUST expor uma função de idempotência
  (`mark_message_processed(message_id, consumer) -> bool`) que grava condicionalmente na tabela
  `processed_messages` (PK `MSG#{message_id}`, TTL de 7 dias) e indica se a mensagem já havia sido
  processada por aquele consumidor, conforme §3.
- **FR-009**: O pacote compartilhado MUST expor um logger que emite logs estruturados em JSON,
  incluindo `orderId` e `correlationId` quando disponíveis no contexto de chamada.
- **FR-010**: O `correlation_id` de `MessageEnvelope` MUST ser propagado sem alteração por toda a
  cadeia de mensagens de um mesmo fluxo (gerado uma única vez pelo produtor original — API Gateway
  ou Lambda Line Processor).
- **FR-011**: O pacote compartilhado MUST expor uma função de mascaramento de documento que
  substitui todos os dígitos do `customer_document` por `*`, exceto os últimos 4; documentos com 4
  caracteres ou menos são mascarados integralmente.
- **FR-012**: O pacote compartilhado MUST expor um parser do layout posicional de
  `docs/01-dominio-e-contratos.md` §6, implementando as 5 regras da subseção "Regras de parsing"
  (linha ≠200 chars, header/trailer ausente, contadores do trailer divergentes, item órfão,
  `item_count` divergente).
- **FR-013**: O pacote compartilhado MUST ser instalável por cada serviço como dependência local
  (via `uv`), sem exigir publicação em índice de pacotes externo.
- **FR-014**: O pacote compartilhado MUST ter testes unitários cobrindo os modelos de mensagem, as
  transições válidas do `OrderStatus`, a função de idempotência e o parser posicional (incluindo
  todos os caminhos de rejeição da seção "Regras de parsing").
- **FR-015**: Toda função pública do pacote compartilhado MUST ter type hints e passar
  `ruff check` sem apontamentos.

### Key Entities

- **Order**: pedido em processamento — campos conforme §2.2 (`order_id`, `customer_id`,
  `customer_name`, `customer_document`, `channel`, `items`, totais em `Decimal`, `status`,
  `status_reason`, `invoice_s3_key`, `correlation_id`, `source_file`/`source_line` quando
  `channel == BATCH`, `created_at`/`updated_at`, `version`).
- **OrderItem**: item do pedido — `product_id`, `quantity`, `unit_price`, `discount_percentage`,
  `line_total`, `product_title`, `product_sku` (os 5 últimos preenchidos pelo Validator).
- **OrderStatus**: enum com os 9 estados e a tabela de transições de §2.3.
- **MessageEnvelope**: envelope comum a toda mensagem interna — `message_id`, `correlation_id`,
  `order_id`, `occurred_at`, `payload`.
- **ProcessedMessage** (registro de idempotência): `message_id` (PK), `consumer`, `processed_at`,
  `ttl` — tabela `processed_messages`, conforme §3.
- **Settings**: configuração centralizando conexão Ministack e nomes de todos os recursos de
  infraestrutura de `docs/01-dominio-e-contratos.md` §3, §4, §7.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Todo serviço do sistema consegue importar e usar `Order`, `OrderStatus` e
  `MessageEnvelope` sem reescrever nenhuma definição de campo localmente.
- **SC-002**: Existe exatamente uma definição de cada contrato de mensagem e do `OrderStatus` em
  todo o repositório (zero duplicação).
- **SC-003**: Um novo serviço consegue enviar e receber mensagens usando os clientes
  compartilhados, em qualquer uma das 9 filas do domínio, sem escrever código de configuração de
  endpoint.
- **SC-004**: 100% dos logs emitidos através do logger compartilhado são JSON válido, incluindo
  `orderId` e `correlationId` sempre que disponíveis.
- **SC-005**: Reprocessar a mesma mensagem (mesmo `message_id`) através da função de idempotência
  nunca resulta em processamento duplicado — validado por teste automatizado.
- **SC-006**: As regras de transição de `OrderStatus`, a função de idempotência e o parser
  posicional (incluindo as 5 regras de rejeição) têm cobertura de teste unitário e passam antes de
  qualquer serviço declarar dependência do pacote.

## Assumptions

- `docs/01-dominio-e-contratos.md` é a fonte de verdade para nomes de entidade, estados, filas,
  contratos de mensagem e layout de arquivo — esta spec não introduz nomes ou estruturas que
  divirjam desse documento.
- O pacote `pedidos_shared` é consumido exclusivamente pelos serviços deste monorepo.
- Cada serviço consumidor é responsável por validar, no próprio `config.py` (constitution VIII),
  que as variáveis de recurso específicas que ele usa (ex: só as filas que lê/escreve) estão
  definidas — o `Settings` compartilhado expõe os campos, mas só os 4 campos de conexão são
  universalmente obrigatórios em todo serviço.
- A criação real das 9 filas (+DLQs), das tabelas `orders`/`processed_messages`, do bucket
  `pedidos-bucket` e da configuração de notificação do S3 é responsabilidade da feature
  `002-infraestrutura-local`, não desta feature — aqui só se definem os contratos e clientes.
