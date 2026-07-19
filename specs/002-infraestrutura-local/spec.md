# Feature Specification: Infraestrutura Local (Ministack)

**Feature Branch**: `002-infraestrutura-local`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "Ambiente local de desenvolvimento e testes: docker-compose.yml
orquestrando o Ministack localmente, e scripts idempotentes em infra/bootstrap/ que criam as
filas SQS (com DLQ, maxReceiveCount=3), a tabela DynamoDB de pedidos e o bucket S3 de PDFs contra
o Ministack, para que qualquer serviço (a começar pelo pedidos_shared) consiga rodar seus testes
de integração localmente sem configuração manual, conforme constitution seções I.4, I.6 e IX."

## Clarifications

### Session 2026-07-18

- Q: O bootstrap roda automático como parte do `docker-compose up`, ou é um comando manual
  separado? → A: Automático — um serviço one-shot no próprio `docker-compose.yml` espera o
  healthcheck do Ministack e roda o bootstrap sozinho; nenhum segundo comando é necessário no
  dia a dia.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Subir o ambiente local com um comando (Priority: P1)

Como desenvolvedor de qualquer serviço do sistema, preciso subir o Ministack **e** ter os recursos
de infraestrutura (filas, tabela, bucket) já criados com um único comando, para começar a
desenvolver e testar sem depender de uma conta AWS real nem de nenhum passo manual adicional.

**Why this priority**: Sem o Ministack rodando, nenhum outro cenário desta feature nem de nenhuma
outra feature do sistema pode ser validado — é o alicerce de todo o desenvolvimento local
(constitution I.6).

**Independent Test**: Rodar o comando de subida do ambiente numa máquina limpa e confirmar que o
Ministack responde a uma checagem de saúde e que os recursos de infraestrutura já existem logo em
seguida, sem nenhum passo manual além desse único comando.

**Acceptance Scenarios**:

1. **Given** uma máquina com Docker instalado e nenhum ambiente rodando, **When** o desenvolvedor
   roda o comando de subida do ambiente, **Then** o Ministack fica disponível (checagem de saúde
   passa) e o serviço de bootstrap dispara automaticamente logo em seguida.
2. **Given** o ambiente já rodando, **When** o desenvolvedor roda o comando de subida novamente,
   **Then** o ambiente continua disponível sem erro e o bootstrap roda de novo sem duplicar
   recursos (idempotência de subida — ver User Story 3).

---

### User Story 2 - Recursos de infraestrutura já existem ao subir o ambiente (Priority: P1)

Como desenvolvedor, preciso que as filas SQS (cada uma com sua própria DLQ), a tabela DynamoDB de
pedidos e o bucket S3 de PDFs já existam contra o Ministack assim que o bootstrap roda, para não
precisar criar esses recursos manualmente antes de rodar qualquer teste de integração.

**Why this priority**: É o requisito que efetivamente desbloqueia o teste de integração de
`pedidos_shared` (feature 001, User Story 2) e de toda feature futura que dependa de SQS/DynamoDB/S3
— tem o mesmo nível de urgência que subir o Ministack em si.

**Independent Test**: Depois de rodar o bootstrap, consultar o Ministack (via CLI ou SDK) e
confirmar que cada fila, a tabela e o bucket existem com a configuração esperada — incluindo a DLQ
de cada fila com `maxReceiveCount = 3`.

**Acceptance Scenarios**:

1. **Given** o Ministack rodando e vazio, **When** o script de bootstrap é executado, **Then**
   todas as filas necessárias existem, cada uma com uma DLQ associada e `maxReceiveCount = 3`.
2. **Given** o Ministack rodando e vazio, **When** o script de bootstrap é executado, **Then** a
   tabela DynamoDB de pedidos e o bucket S3 de PDFs existem com os nomes esperados pelos serviços.
3. **Given** os recursos já criados, **When** um serviço lê os nomes de fila/tabela/bucket das suas
   variáveis de ambiente, **Then** esses nomes correspondem exatamente aos recursos criados pelo
   bootstrap (sem deriva de nome).

---

### User Story 3 - Rodar o bootstrap de novo não quebra nem duplica (Priority: P2)

Como desenvolvedor, preciso que rodar o script de bootstrap mais de uma vez (ex: depois de um
restart do Ministack, ou ao atualizar o repositório) não falhe nem duplique recursos, para poder
iterar no ambiente local sem ritual de limpeza manual antes.

**Why this priority**: Sem idempotência, cada restart do ambiente vira um passo manual de "apagar
tudo antes" — viola constitution local-first (I.6) na prática, mesmo que o Ministack em si suba
com um comando.

**Independent Test**: Rodar o script de bootstrap duas vezes seguidas contra o mesmo Ministack e
confirmar que a segunda execução termina sem erro e sem criar recurso duplicado ou alterar a
configuração dos recursos já existentes.

**Acceptance Scenarios**:

1. **Given** os recursos já criados por uma execução anterior do bootstrap, **When** o bootstrap é
   executado novamente, **Then** a execução termina sem erro e o número de filas/tabela/bucket
   permanece o mesmo (nenhuma duplicata).
2. **Given** uma fila já existente com a DLQ correta, **When** o bootstrap roda de novo, **Then** a
   configuração da DLQ (`maxReceiveCount = 3`) permanece inalterada.

---

### Edge Cases

- O que acontece se o script de bootstrap rodar antes do Ministack estar pronto para aceitar
  conexões (condição de corrida na subida)?
- O que acontece se `docker-compose up` for executado sem o Docker instalado ou sem o daemon
  rodando?
- Como o bootstrap se comporta se um recurso já existir com uma configuração diferente da esperada
  (ex: fila sem DLQ, criada manualmente fora do script)?
- O que acontece se faltar uma variável de ambiente que o bootstrap precisa pra nomear um recurso?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer um `docker-compose.yml` que sobe o Ministack e dispara o
  bootstrap automaticamente (serviço one-shot que aguarda o healthcheck do Ministack) com um único
  comando, sem exigir nenhum passo manual adicional de configuração.
- **FR-002**: O sistema MUST fornecer scripts de bootstrap que criam a fila `pedido-solicitado` —
  necessária pelo teste de integração de `pedidos_shared` (feature 001) — com sua própria fila de
  dead-letter (DLQ) e redrive policy `maxReceiveCount = 3` (constitution I.4). Specs de serviço
  futuras (order-processor, order-validator, pdf-generator, file-consumer, lambda-line-processor)
  MUST estender este bootstrap com suas próprias filas, seguindo a mesma regra de DLQ, ao serem
  especificadas.
- **FR-003**: Os scripts de bootstrap MUST criar a tabela DynamoDB usada para persistir o estado
  dos pedidos.
- **FR-004**: Os scripts de bootstrap MUST criar o bucket S3 usado para armazenar os PDFs gerados.
- **FR-005**: Os scripts de bootstrap MUST ser idempotentes — executá-los múltiplas vezes contra o
  mesmo ambiente não MUST falhar nem duplicar nenhum recurso (constitution "IaC local").
- **FR-006**: Os nomes de fila, tabela e bucket criados pelo bootstrap MUST corresponder
  exatamente aos valores que os serviços esperam ler das próprias variáveis de ambiente (mesmo
  contrato de nomes usado por `Settings` do pacote compartilhado).
- **FR-007**: Depois de um único `docker-compose up` (que já dispara o bootstrap automaticamente),
  qualquer serviço MUST conseguir rodar seus testes de integração contra o Ministack sem nenhuma
  configuração manual adicional.
- **FR-008**: O ambiente MUST documentar em README as variáveis de ambiente relevantes e o comando
  para subir e popular o ambiente localmente (constitution IX).

### Key Entities

- **Ambiente Ministack**: instância local que emula os serviços AWS usados pelo sistema (SQS,
  DynamoDB, S3), orquestrada via `docker-compose.yml`.
- **Fila SQS**: recurso de mensageria criado pelo bootstrap; sempre acompanhado de uma DLQ e de uma
  redrive policy com `maxReceiveCount = 3`.
- **Tabela de pedidos (DynamoDB)**: recurso de persistência do estado dos pedidos, criado pelo
  bootstrap.
- **Bucket de PDFs (S3)**: recurso de armazenamento dos PDFs gerados, criado pelo bootstrap.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um desenvolvedor consegue ter um ambiente local pronto para testes (Ministack +
  filas + tabela + bucket) executando um único comando (`docker-compose up`), sem nenhum passo
  manual adicional além de uma cópia inicial de `.env.example` pra `.env` (feita uma vez, não a
  cada subida do ambiente).
- **SC-002**: Executar o bootstrap uma segunda vez contra o mesmo ambiente não produz erro nem
  altera a contagem ou a configuração dos recursos já existentes.
- **SC-003**: 100% das filas criadas pelo bootstrap têm uma DLQ configurada com
  `maxReceiveCount = 3`.
- **SC-004**: O teste de integração de qualquer serviço que dependa de SQS/DynamoDB/S3 (a começar
  pelo `pedidos_shared`) roda com sucesso contra este ambiente sem nenhuma configuração de endpoint
  feita manualmente pelo desenvolvedor.

## Assumptions

- Nesta primeira versão, o bootstrap cria o conjunto mínimo de recursos necessário para o teste de
  integração do `pedidos_shared` (feature 001) — uma fila de exemplo com sua DLQ, a tabela de
  pedidos e o bucket de PDFs. Cada spec de serviço futura (order-processor, order-validator,
  pdf-generator, file-consumer, lambda-line-processor) adiciona suas próprias filas ao bootstrap
  quando for especificada, em vez de esta feature antecipar todo o desenho de filas do sistema.
- O bootstrap roda automaticamente a cada `docker-compose up` (ver Clarifications) — é seguro
  rodar repetidas vezes por ser idempotente (FR-005, User Story 3); o desenvolvedor também pode
  reexecutá-lo manualmente se precisar, mas isso não é o fluxo padrão documentado no README
  (FR-008).
- O Ministack expõe uma API compatível com SQS, DynamoDB e S3 suficiente para os scripts de
  bootstrap usarem boto3/awslocal CLI sem adaptação.
