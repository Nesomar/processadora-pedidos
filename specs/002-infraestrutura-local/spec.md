# Feature Specification: Infraestrutura Local (Ministack)

**Feature Branch**: `002-infraestrutura-local`

**Created**: 2026-07-18 | **Revised**: 2026-07-18 (realinhado a `docs/01-dominio-e-contratos.md`)

**Status**: Draft

**Input**: User description: "Ambiente local de desenvolvimento e testes: docker-compose.yml
orquestrando o Ministack localmente, e scripts idempotentes em infra/bootstrap/ que criam as
filas SQS (com DLQ, maxReceiveCount=3), as tabelas DynamoDB e o bucket S3 contra o Ministack" —
realinhado à fonte de verdade de domínio `docs/01-dominio-e-contratos.md` §3, §4, §7, §8.

## Clarifications

### Session 2026-07-18 (primeira rodada)

- Q: O bootstrap roda automático como parte do `docker-compose up`, ou é um comando manual
  separado? → A: Automático — serviço one-shot no `docker-compose.yml`, gate por
  `depends_on: condition: service_healthy`.

### Session 2026-07-18 (rework pós-leitura de docs/01-dominio-e-contratos.md)

- Q: (implícita) Quais as filas, tabelas e configuração de bucket exatas? → A: Todas definidas por
  `docs/01-dominio-e-contratos.md` §3/§4/§7 — substitui a Assumption anterior de "fila de exemplo
  única"; agora o conjunto completo (9 filas+DLQ, 2 tabelas, bucket com notificação de evento) é
  conhecido e é o que o bootstrap cria.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Subir o ambiente local com um comando (Priority: P1)

Como desenvolvedor de qualquer serviço do sistema, preciso subir o Ministack **e** ter todos os
recursos de infraestrutura do domínio já criados com um único comando, para começar a desenvolver
e testar sem depender de conta AWS real nem de nenhum passo manual adicional.

**Why this priority**: Sem o Ministack rodando e populado, nenhum outro cenário do sistema pode ser
validado — é o alicerce de todo o desenvolvimento local (constitution I.6).

**Independent Test**: Numa máquina limpa, rodar `docker compose up -d` e confirmar que o Ministack
fica saudável e que o serviço `bootstrap` dispara automaticamente, roda e sai com código 0.

**Acceptance Scenarios**:

1. **Given** uma máquina com Docker instalado e nenhum ambiente rodando, **When** o desenvolvedor
   roda o comando de subida, **Then** o Ministack fica disponível e o bootstrap dispara
   automaticamente logo em seguida.
2. **Given** o ambiente já rodando, **When** o desenvolvedor roda o comando de subida de novo,
   **Then** o ambiente continua disponível e o bootstrap roda de novo sem duplicar recursos.

---

### User Story 2 - Recursos completos do domínio existem ao subir o ambiente (Priority: P1)

Como desenvolvedor, preciso que as 9 filas (cada uma com sua DLQ), as tabelas `orders` e
`processed_messages`, e o bucket `pedidos-bucket` (com a notificação de evento pra
`s3_notifications_queue`) já existam contra o Ministack assim que o bootstrap roda, para não
precisar criar nenhum recurso manualmente antes de rodar um serviço ou teste de integração.

**Why this priority**: É o requisito que efetivamente desbloqueia o teste de integração de
`pedidos_shared` (feature 001) e de toda feature de serviço futura — mesmo nível de urgência que
subir o Ministack em si.

**Independent Test**: Depois de rodar o bootstrap, consultar o Ministack (CLI/SDK) e confirmar que
as 9 filas + DLQs, as 2 tabelas (com os índices esperados) e o bucket (com a notificação de evento)
existem com a configuração exata de `docs/01-dominio-e-contratos.md`.

**Acceptance Scenarios**:

1. **Given** o Ministack vazio, **When** o bootstrap roda, **Then** as 9 filas de §4 existem, cada
   uma com sua DLQ (`{nome}_dlq`) e `maxReceiveCount = 3`.
2. **Given** o Ministack vazio, **When** o bootstrap roda, **Then** a tabela `orders` existe com
   `PK`/`SK` e os índices `GSI1` (por cliente) e `GSI2` (por status) de §3.
3. **Given** o Ministack vazio, **When** o bootstrap roda, **Then** a tabela `processed_messages`
   existe com TTL habilitado no atributo `ttl`.
4. **Given** o Ministack vazio, **When** o bootstrap roda, **Then** o bucket `pedidos-bucket`
   existe com notificação de evento `s3:ObjectCreated:*` (prefixo `uploads/`, sufixo `.txt`)
   configurada para publicar em `s3_notifications_queue`.
5. **Given** os recursos já criados, **When** um serviço lê os nomes de fila/tabela/bucket das
   próprias variáveis de ambiente, **Then** esses nomes correspondem exatamente aos recursos
   criados pelo bootstrap.

---

### User Story 3 - Rodar o bootstrap de novo não quebra nem duplica (Priority: P2)

Como desenvolvedor, preciso que rodar o bootstrap mais de uma vez não falhe nem duplique nenhum dos
recursos (filas, DLQs, tabelas, bucket, notificação de evento), para poder reiniciar o ambiente ou
atualizar o repositório sem ritual de limpeza manual.

**Why this priority**: Sem idempotência, cada restart vira um passo manual — viola local-first
(I.6) na prática.

**Independent Test**: Rodar o bootstrap duas vezes seguidas contra o mesmo Ministack; segunda
execução não falha e a contagem/configuração de todos os recursos permanece igual.

**Acceptance Scenarios**:

1. **Given** os recursos já criados, **When** o bootstrap roda de novo, **Then** termina sem erro
   e nenhum recurso é duplicado (filas, tabelas, bucket, notificação de evento).
2. **Given** uma fila já existente com a DLQ correta, **When** o bootstrap roda de novo, **Then**
   a configuração da DLQ permanece inalterada.
3. **Given** a notificação de evento do bucket já configurada, **When** o bootstrap roda de novo,
   **Then** a configuração de notificação não é duplicada nem sobrescrita de forma inconsistente.

---

### User Story 4 - Atalhos de Makefile para operações comuns (Priority: P3)

Como desenvolvedor, preciso de atalhos `make up`, `make down`, `make bootstrap`, `make test`,
`make e2e` e `make seed-file` (docs/01-dominio-e-contratos.md §8), para não precisar decorar os
comandos completos de `docker compose`/`uv run` no dia a dia.

**Why this priority**: É conveniência, não bloqueia nenhum outro cenário — os comandos completos já
funcionam sem o Makefile.

**Independent Test**: Rodar cada alvo do Makefile numa máquina limpa e confirmar que ele produz o
mesmo efeito do comando completo equivalente.

**Acceptance Scenarios**:

1. **Given** o ambiente parado, **When** o desenvolvedor roda `make up`, **Then** o efeito é
   idêntico a `docker compose up -d` (Ministack + bootstrap automático).
2. **Given** o ambiente rodando, **When** o desenvolvedor roda `make down`, **Then** o ambiente é
   derrubado.
3. **Given** o ambiente rodando, **When** o desenvolvedor roda `make seed-file`, **Then** um
   arquivo posicional de exemplo válido é gerado e enviado para `uploads/` no bucket.

---

### Edge Cases

- Bootstrap rodar antes do Ministack aceitar conexões (condição de corrida na subida).
- `docker compose up` sem Docker instalado/rodando.
- Recurso já existir com configuração diferente da esperada (ex: fila sem DLQ, criada manualmente).
- Variável de ambiente ausente que o bootstrap precisa pra nomear um recurso.
- Notificação de evento do bucket já configurada de forma diferente da esperada (ex: apontando pra
  outra fila) — bootstrap deve logar aviso, não sobrescrever silenciosamente uma config divergente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST fornecer um `docker-compose.yml` que sobe o Ministack e dispara o
  bootstrap automaticamente (serviço one-shot, `depends_on: condition: service_healthy`) com um
  único comando.
- **FR-002**: Os scripts de bootstrap MUST criar as 9 filas de `docs/01-dominio-e-contratos.md`
  §4 (`solicitar_pedido_queue`, `editar_pedido_queue`, `cancelar_pedido_queue`,
  `validar_pedido_queue`, `validar_pedido_response_queue`, `pdf_request_queue`,
  `pdf_response_queue`, `s3_notifications_queue`, `pedido_lines_queue`), cada uma com sua DLQ
  (`{nome}_dlq`) e `maxReceiveCount = 3` (constitution I.4).
- **FR-003**: Os scripts de bootstrap MUST criar a tabela `orders` com `PK`/`SK` e os índices
  `GSI1` (`CUSTOMER#{customer_id}` / `{created_at}#{order_id}`) e `GSI2`
  (`STATUS#{status}` / `{created_at}#{order_id}`), conforme §3.
- **FR-004**: Os scripts de bootstrap MUST criar a tabela `processed_messages` com TTL nativo
  habilitado no atributo `ttl`, conforme §3.
- **FR-005**: Os scripts de bootstrap MUST criar o bucket `pedidos-bucket` com notificação de
  evento `s3:ObjectCreated:*` (prefixo `uploads/`, sufixo `.txt`) publicando em
  `s3_notifications_queue`, conforme §7.
- **FR-006**: Os scripts de bootstrap MUST ser idempotentes — executá-los múltiplas vezes não MUST
  falhar nem duplicar nenhum recurso, incluindo a notificação de evento do bucket.
- **FR-007**: Os nomes de fila, tabela e bucket criados pelo bootstrap MUST corresponder
  exatamente aos valores que os serviços esperam ler das próprias variáveis de ambiente (mesmo
  contrato de nomes usado por `Settings` de `pedidos_shared`, feature 001).
- **FR-008**: Depois de um único `docker-compose up`, qualquer serviço MUST conseguir rodar seus
  testes de integração contra o Ministack sem nenhuma configuração manual adicional.
- **FR-009**: O ambiente MUST documentar em README as variáveis de ambiente e o comando para subir
  e popular o ambiente localmente (constitution IX).
- **FR-010**: O sistema MUST fornecer um `Makefile` com os alvos `up`, `down`, `bootstrap`, `test`,
  `e2e` e `seed-file`, conforme §8.

### Key Entities

- **Ambiente Ministack**: instância local emulando SQS, DynamoDB, S3, orquestrada via
  `docker-compose.yml`.
- **Fila SQS**: uma das 9 filas de §4; sempre acompanhada de DLQ e `maxReceiveCount = 3`.
- **Tabela `orders`**: persistência do pedido, com `GSI1` (por cliente) e `GSI2` (por status).
- **Tabela `processed_messages`**: registro de idempotência, TTL de 7 dias.
- **Bucket `pedidos-bucket`**: armazenamento de arquivos posicionais (`uploads/`) e notas fiscais
  (`invoices/YYYY/MM/DD/{order_id}.pdf`); notificação de evento liga upload a
  `s3_notifications_queue`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um desenvolvedor consegue ter o ambiente local completo pronto executando um único
  comando (`docker-compose up`), sem passo manual além de uma cópia inicial de `.env.example` pra
  `.env` (feita uma vez).
- **SC-002**: Executar o bootstrap uma segunda vez não produz erro nem altera a contagem ou
  configuração de nenhum recurso já existente, incluindo a notificação de evento do bucket.
- **SC-003**: 100% das filas criadas pelo bootstrap têm DLQ configurada com
  `maxReceiveCount = 3`.
- **SC-004**: O teste de integração de qualquer serviço que dependa de SQS/DynamoDB/S3 (a começar
  pelo `pedidos_shared`) roda com sucesso contra este ambiente sem configuração manual de endpoint.
- **SC-005**: Um arquivo `.txt` enviado pra `uploads/` no bucket gera uma mensagem em
  `s3_notifications_queue` sem nenhuma configuração adicional do desenvolvedor.

## Assumptions

- `docs/01-dominio-e-contratos.md` é a fonte de verdade para nomes de fila, tabela, bucket e
  configuração de notificação — esta spec não define nenhum recurso que divirja desse documento.
- Os 5 serviços Python + o runner da Lambda (§8) sobem em compose files próprios de cada spec de
  serviço futura, que referenciam este `infra/docker-compose.yml` como base — esta feature entrega
  só `ministack` + `bootstrap`.
- O bootstrap roda automaticamente a cada `docker-compose up` (idempotente, seguro repetir); o
  desenvolvedor também pode reexecutá-lo manualmente via `make bootstrap`.
- O Ministack expõe uma API compatível com SQS, DynamoDB, S3 e notificação de evento do S3
  suficiente para os scripts de bootstrap usarem boto3 sem adaptação.
