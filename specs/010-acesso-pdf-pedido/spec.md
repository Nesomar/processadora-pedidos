# Feature Specification: Acesso ao PDF da Nota Fiscal do Pedido

**Feature Branch**: `feature/010-acesso-pdf-pedido`

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "quero ter acesso aos pdf que sao gerados no fluxo de solicitacao de pedidos, qual seria a melhor forma de ter acesso ao pdf gerado?"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Baixar o PDF de um pedido concluído (Priority: P1)

Quem solicitou um pedido (ou o operador do sistema) consulta o pedido e obtém uma forma direta de
abrir/baixar o PDF da nota fiscal gerado para ele, sem precisar conhecer a infraestrutura de
armazenamento nem navegar manualmente pelo bucket.

**Why this priority**: Hoje o PDF é gerado e guardado, mas o consumidor do sistema só enxerga uma
chave interna do armazenamento — o documento é inacessível na prática. Sem isso, o resultado final
do fluxo não chega a quem precisa dele.

**Independent Test**: Criar um pedido válido, aguardar `COMPLETED`, pedir o PDF pelo ponto de
entrada HTTP do sistema e verificar que o conteúdo recebido é um PDF válido daquele pedido.

**Acceptance Scenarios**:

1. **Given** um pedido em `COMPLETED` com nota fiscal gerada, **When** o cliente faz GET do PDF desse pedido, **Then** recebe diretamente o documento PDF correspondente àquele pedido.
2. **Given** o mesmo pedido, **When** o cliente consulta os dados do pedido, **Then** a resposta indica que há PDF disponível e como obtê-lo, sem expor detalhes internos de armazenamento.

---

### User Story 2 - Resposta clara quando o PDF ainda não existe (Priority: P2)

Se o pedido ainda está em processamento, foi rejeitado/falhou ou não existe, o cliente recebe uma
resposta que explica o motivo, em vez de erro genérico ou link quebrado.

**Why this priority**: Como o fluxo é assíncrono, é comum pedir o PDF antes de ele existir; o
cliente precisa saber se deve tentar de novo ou desistir.

**Independent Test**: Pedir o PDF de um pedido recém-criado (ainda não concluído), de um `REJECTED`/`FAILED` e de um id inexistente; cada caso retorna resposta distinta e compreensível.

**Acceptance Scenarios**:

1. **Given** um pedido ainda em andamento, **When** o PDF é solicitado, **Then** a resposta informa que o documento ainda não está disponível e que vale tentar novamente.
2. **Given** um pedido `REJECTED` ou `FAILED`, **When** o PDF é solicitado, **Then** a resposta informa que nenhum PDF será gerado para esse pedido.
3. **Given** um id de pedido inexistente, **When** o PDF é solicitado, **Then** a resposta indica pedido não encontrado.

---

### User Story 3 - Armazenamento permanece fechado (Priority: P3)

O PDF só é obtido através do ponto de entrada HTTP do sistema; o armazenamento continua sem
acesso público e nenhum link permanente ou chave interna é revelado.

**Why this priority**: Notas fiscais contêm dados de cliente; o P1 já entrega valor, mas o
fechamento do acesso direto garante que o endpoint seja o único caminho.

**Independent Test**: Concluir um pedido, baixar o PDF pelo endpoint e confirmar que nenhuma resposta contém chave, endereço ou credencial do armazenamento.

**Acceptance Scenarios**:

1. **Given** um pedido concluído, **When** o cliente baixa o PDF, **Then** a resposta traz apenas o documento, sem referência ao armazenamento interno.
2. **Given** o mesmo pedido, **When** o cliente consulta os dados do pedido, **Then** a chave interna do armazenamento não é exposta.

---

### Edge Cases

- Pedido `COMPLETED` cujo arquivo PDF sumiu do armazenamento: resposta de erro clara, sem link quebrado.
- Pedido editado e reprocessado: o PDF servido é o da versão mais recente concluída.
- Solicitações repetidas do mesmo PDF são seguras (leitura apenas, sem efeito colateral).
- Pedidos originados por arquivo em lote seguem o mesmo comportamento dos pedidos online.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST oferecer, por uma requisição de leitura (GET) no ponto de entrada HTTP único, a entrega direta do conteúdo PDF da nota fiscal de um pedido, identificado pelo seu id, como documento PDF baixável/abrível.
- **FR-002**: O sistema MUST entregar o PDF apenas para pedidos em `COMPLETED` com nota fiscal gerada.
- **FR-003**: O sistema MUST responder de forma distinta e descritiva para: pedido inexistente, pedido ainda em processamento, pedido sem PDF por `REJECTED`/`FAILED`, e PDF ausente no armazenamento.
- **FR-004**: O sistema MUST NOT expor ao cliente a chave interna nem credenciais do armazenamento.
- **FR-005**: O sistema MUST NOT gerar links públicos ou pré-assinados para o armazenamento; o conteúdo é entregue somente pela própria resposta.
- **FR-006**: A consulta de dados do pedido MUST indicar se o PDF está disponível.
- **FR-007**: O acesso ao PDF MUST ser somente leitura e não alterar o estado do pedido.
- **FR-008**: O acesso MUST ser registrado em log estruturado com o identificador do pedido, sem dados pessoais em claro (documento do cliente mascarado).
- **FR-009**: O fluxo existente de geração e transição de estados MUST permanecer inalterado.

### Key Entities

- **Pedido**: já existente; referencia o PDF da nota fiscal quando concluído.
- **Nota fiscal (PDF)**: documento gerado ao fim do fluxo, uma versão válida por pedido concluído.
- **Entrega do PDF**: resposta de leitura que carrega o conteúdo do documento de um pedido concluído.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Para 100% dos pedidos `COMPLETED`, o cliente obtém o PDF correto em uma única solicitação, em até 3 segundos.
- **SC-002**: Em 100% dos casos sem PDF disponível, o cliente recebe uma resposta que identifica a causa (não encontrado, em andamento, sem PDF, ausente).
- **SC-003**: Em 100% das respostas de sucesso, o cliente recebe um arquivo PDF válido (abre em qualquer leitor) sem passos adicionais.
- **SC-004**: Um usuário consegue, a partir do `order_id`, abrir o PDF em menos de 1 minuto seguindo apenas o README.
- **SC-005**: Nenhuma resposta do sistema revela chaves internas ou credenciais do armazenamento.

## Assumptions

- O sistema não tem autenticação de usuários hoje; conhecer o `order_id` é a única "credencial", e esta feature não introduz autenticação (fora de escopo).
- Decisão do usuário: entrega direta do conteúdo via GET no API Gateway (sem link temporário).
- O PDF é de tamanho pequeno (nota fiscal de um pedido), então a entrega direta pela API é adequada.
- Interface gráfica está fora de escopo; o acesso é via HTTP/CLI e documentado no README e em `examples/`.
- Depende do PDF Generator e do Order Processor existentes (que já gravam `invoice_s3_key`) e do ponto de entrada HTTP existente.
