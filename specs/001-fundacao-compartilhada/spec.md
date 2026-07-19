# Feature Specification: Fundação Compartilhada (pedidos_shared)

**Feature Branch**: `001-fundacao-compartilhada`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "001-fundacao-compartilhada"

## Clarifications

### Session 2026-07-18

- Q: Estados da máquina de estados do pedido (enum StatusPedido)? → A: Fluxo mínimo — RECEBIDO,
  VALIDANDO, VALIDADO, REJEITADO, GERANDO_PDF, CONCLUIDO, ERRO.
- Q: Regra de mascaramento do documento do cliente em logs? → A: Mostra só os últimos 4 dígitos,
  resto mascarado (ex: `***.***.***-12`).
- Q: Quem gera e propaga o correlationId entre serviços? → A: Ponto de entrada (api-gateway ou
  lambda-line-processor) gera um correlationId único por pedido/arquivo e o embute em toda
  mensagem subsequente; cada serviço downstream repassa o mesmo id ao publicar a próxima mensagem.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Contrato de mensagem e status únicos (Priority: P1)

Como desenvolvedor de qualquer serviço do sistema (api-gateway, order-processor, order-validator,
pdf-generator, file-consumer, lambda-line-processor), preciso importar os modelos Pydantic de
contrato de mensagem e o enum de status do pedido de um único pacote compartilhado, para que
nenhum serviço redefina esse contrato localmente e todas as transições de estado usem o mesmo
vocabulário.

**Why this priority**: Sem um contrato único, cada serviço poderia divergir na forma da mensagem
ou nos nomes de estado, quebrando a máquina de estados e a comunicação assíncrona entre
componentes — é a base de tudo o mais no sistema.

**Independent Test**: Em um serviço de teste isolado, importar o pacote, instanciar cada modelo
de mensagem definido, serializar para JSON e validar que a validação Pydantic rejeita um payload
com campo obrigatório ausente ou com um valor de status fora do enum.

**Acceptance Scenarios**:

1. **Given** o pacote compartilhado instalado em um serviço, **When** o serviço importa um modelo
   de mensagem (ex: pedido solicitado), **Then** o modelo valida corretamente um payload válido e
   rejeita um payload inválido com erro claro.
2. **Given** dois serviços diferentes que leem o mesmo tipo de mensagem, **When** cada um importa
   o modelo do pacote compartilhado, **Then** ambos usam exatamente a mesma definição de campos,
   sem cópia local do contrato.
3. **Given** o enum de status do pedido, **When** um serviço tenta persistir uma transição para um
   valor que não existe no enum, **Then** a tentativa falha na validação antes de qualquer escrita
   no DynamoDB.

---

### User Story 2 - Configuração e clientes de infraestrutura sem valores hardcoded (Priority: P2)

Como desenvolvedor de um serviço, preciso de um `Settings` Pydantic e de clientes SQS/DynamoDB/S3
pré-configurados que leem o endpoint do Ministack e os nomes de fila/tabela/bucket de variáveis de
ambiente, para que nenhum serviço hardcode um valor de infraestrutura.

**Why this priority**: É pré-requisito para o princípio local-first da constitution — sem isso,
cada serviço reimplementaria sua própria configuração de forma inconsistente.

**Independent Test**: Definir as variáveis de ambiente apontando para uma instância local do
Ministack, instanciar o cliente SQS do pacote, enviar uma mensagem de teste para uma fila e
confirmar que ela é recebida, sem nenhum valor de endpoint escrito em código.

**Acceptance Scenarios**:

1. **Given** as variáveis de ambiente de infraestrutura definidas, **When** um serviço instancia
   `Settings`, **Then** os valores de fila, tabela, bucket e endpoint do Ministack são carregados
   corretamente.
2. **Given** uma variável de ambiente obrigatória ausente, **When** um serviço tenta instanciar
   `Settings`, **Then** a inicialização falha imediatamente com uma mensagem indicando qual
   variável está faltando.
3. **Given** o cliente SQS do pacote compartilhado, **When** um serviço envia e depois consome uma
   mensagem, **Then** a operação usa o `endpoint_url` do Ministack sem nenhuma URL fixa no código
   do serviço.

---

### User Story 3 - Logging estruturado rastreável (Priority: P3)

Como desenvolvedor, preciso de um logger que emita logs estruturados em JSON incluindo `orderId` e
`correlationId` automaticamente quando disponíveis, para rastrear o fluxo de um pedido entre
serviços sem reescrever essa lógica em cada um.

**Why this priority**: Observabilidade é necessária desde a primeira mensagem processada, mas o
sistema funciona (de forma pior) sem logging estruturado — por isso vem depois do contrato e da
configuração.

**Independent Test**: Chamar o logger a partir de um contexto de teste com `orderId` e
`correlationId` definidos, capturar a saída padrão e validar que é um JSON bem formado contendo
ambos os campos.

**Acceptance Scenarios**:

1. **Given** um `orderId` e `correlationId` no contexto de execução, **When** o serviço registra um
   log, **Then** a linha de log é um JSON válido contendo esses dois campos.
2. **Given** nenhum `orderId` disponível (ex: log de inicialização do serviço), **When** o serviço
   registra um log, **Then** a linha ainda é um JSON válido, sem o campo `orderId` ou com valor
   nulo, sem lançar exceção.
3. **Given** uma mensagem recebida contendo `correlationId`, **When** o serviço processa e publica
   uma nova mensagem para a próxima etapa, **Then** o `correlationId` da nova mensagem é idêntico
   ao da mensagem recebida.

---

### User Story 4 - Parser de arquivo posicional reutilizável (Priority: P4)

Como desenvolvedor do file-consumer, preciso de um parser de arquivo posicional (layout de largura
fixa) compartilhado, para interpretar arquivos de pedido recebidos sem duplicar essa lógica fora do
pacote comum.

**Why this priority**: Só é usado por um serviço hoje (file-consumer), por isso tem prioridade mais
baixa que os itens usados por todos os serviços — mas ainda pertence à fundação porque outro
serviço pode vir a precisar do mesmo formato.

**Independent Test**: Passar uma linha de texto de largura fixa conhecida para o parser e validar
que os campos extraídos batem com os valores esperados; passar uma linha mais curta que o layout e
validar que o parser retorna um erro de domínio claro em vez de lançar uma exceção genérica.

**Acceptance Scenarios**:

1. **Given** uma linha de arquivo posicional bem formada, **When** o parser processa a linha,
   **Then** retorna os campos extraídos corretamente tipados.
2. **Given** uma linha mais curta que o layout esperado, **When** o parser processa a linha,
   **Then** retorna um erro de domínio específico identificando o problema, sem lançar exceção
   genérica não tratada.

---

### Edge Cases

- O que acontece quando uma variável de ambiente obrigatória de infraestrutura está ausente? O
  `Settings` deve falhar de forma clara na inicialização do serviço, não silenciosamente.
- Como o pacote lida com uma mensagem recebida que não corresponde a nenhum modelo Pydantic
  conhecido (schema desconhecido ou versão divergente)?
- Como o parser posicional lida com uma linha de arquivo mais curta ou mais longa que o layout
  esperado?
- Como o logger se comporta quando chamado antes de existir um `orderId` (ex: log de bootstrap do
  serviço)?
- O que acontece quando dois serviços diferentes tentam usar versões diferentes do pacote
  compartilhado ao mesmo tempo (deriva de contrato)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O pacote compartilhado MUST expor modelos Pydantic v2 para todo contrato de mensagem
  trocado entre serviços internos (ex: pedido solicitado, pedido validado, pedido rejeitado, arquivo
  processado).
- **FR-002**: O pacote compartilhado MUST expor um enum único `StatusPedido` com exatamente os
  estados RECEBIDO, VALIDANDO, VALIDADO, REJEITADO, GERANDO_PDF, CONCLUIDO e ERRO, representando
  todos os estados da máquina de estados do pedido.
- **FR-003**: Nenhum serviço MUST redefinir localmente um contrato de mensagem ou o enum de status
  — todo serviço importa essas definições do pacote compartilhado.
- **FR-004**: O pacote compartilhado MUST expor um `Settings` Pydantic que carrega valores de
  infraestrutura (URLs de fila, nome de tabela, nome de bucket, endpoint do Ministack)
  exclusivamente de variáveis de ambiente, sem nenhum valor hardcoded.
- **FR-005**: O `Settings` MUST falhar de forma explícita e imediata na inicialização quando uma
  variável de ambiente obrigatória estiver ausente.
- **FR-006**: O pacote compartilhado MUST expor clientes wrapper para SQS, DynamoDB e S3 que usam
  o `endpoint_url` do `Settings` em vez de um endpoint fixo.
- **FR-007**: O pacote compartilhado MUST expor um logger que emite logs estruturados em JSON,
  incluindo `orderId` e `correlationId` quando disponíveis no contexto de chamada.
- **FR-007a**: Todo contrato de mensagem do pacote compartilhado MUST incluir um campo
  `correlationId`, gerado uma única vez pelo serviço de entrada (api-gateway ou
  lambda-line-processor) e repassado inalterado por cada serviço downstream em toda mensagem que
  publicar para a mesma cadeia de processamento.
- **FR-008**: O pacote compartilhado MUST expor um parser de arquivo posicional (largura fixa)
  reutilizável, usado pelo file-consumer para interpretar arquivos de pedido.
- **FR-009**: O pacote compartilhado MUST ser instalável por cada serviço como dependência local
  (via `uv`), sem exigir publicação em índice de pacotes externo.
- **FR-010**: O pacote compartilhado MUST ter testes unitários cobrindo os modelos de mensagem, as
  transições válidas do enum de status e o parser posicional, incluindo seus caminhos de erro.
- **FR-011**: Toda função pública do pacote compartilhado MUST ter type hints e passar `ruff check`
  sem apontamentos.
- **FR-012**: O pacote compartilhado MUST expor uma função de mascaramento de documento que
  substitui todos os dígitos do documento por `*`, exceto os últimos 4, e o logger e os modelos de
  log MUST usar essa função sempre que o documento do cliente aparecer em log.

### Key Entities

- **Pedido (Order)**: representa o pedido em processamento; atributos incluem identificador,
  status atual (do enum compartilhado), itens, dados do cliente e `statusReason` quando há falha
  de negócio.
- **Contratos de mensagem**: um modelo Pydantic por tipo de evento trocado entre serviços via SQS
  (ex: pedido solicitado, pedido validado, pedido rejeitado, arquivo processado); todos incluem
  `correlationId` gerado no ponto de entrada e propagado sem alteração pela cadeia de serviços.
- **StatusPedido**: enum único com os estados RECEBIDO, VALIDANDO, VALIDADO, REJEITADO,
  GERANDO_PDF, CONCLUIDO e ERRO.
- **Settings**: modelo de configuração que centraliza todos os valores de infraestrutura lidos de
  variáveis de ambiente (endpoint do Ministack, URLs de fila, nome de tabela, nome de bucket).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Todo serviço do sistema consegue importar e usar o contrato de mensagem e o enum de
  status compartilhados sem reescrever nenhuma definição de campo localmente.
- **SC-002**: Existe exatamente uma definição de cada contrato de mensagem e do enum de status em
  todo o repositório (zero duplicação).
- **SC-003**: Um novo serviço consegue enviar e receber mensagens usando os clientes
  compartilhados sem escrever nenhum código de configuração de endpoint de infraestrutura.
- **SC-004**: 100% dos logs emitidos através do logger compartilhado são JSON válido, incluindo
  `orderId` e `correlationId` sempre que esses valores estiverem disponíveis no contexto.
- **SC-005**: As regras de transição de status e o parser posicional têm cobertura de teste
  unitário e passam antes de qualquer serviço declarar dependência do pacote.

## Assumptions

- O pacote `pedidos_shared` é consumido exclusivamente pelos serviços deste monorepo, sem
  publicação ou uso externo.
- O enum de status é o fluxo mínimo (RECEBIDO → VALIDANDO → VALIDADO → GERANDO_PDF → CONCLUIDO,
  com REJEITADO e ERRO como saídas de falha) — ver seção Clarifications. Estados adicionais para
  ingestão via arquivo (lambda-line-processor/file-consumer) ficam para a spec desse fluxo.
- Dados sensíveis do cliente (documento) são mascarados antes de qualquer log, conforme a seção
  VII da constitution — ver seção Clarifications para a regra concreta (últimos 4 dígitos visíveis).
- O Ministack expõe endpoints compatíveis com as APIs SQS, DynamoDB e S3 usadas via boto3.
