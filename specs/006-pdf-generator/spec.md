# Feature Specification: PDF Generator

**Feature Branch**: `006-pdf-generator`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "Worker que consome `pdf_request_queue`, gera a nota fiscal em PDF do pedido aprovado, armazena o arquivo no S3 e publica o resultado em `pdf_response_queue`, permitindo ao Order Processor concluir ou reprovar tecnicamente o pedido (docs/01-dominio-e-contratos.md)."

## Clarifications

### Session 2026-07-20

- Q: Item sem campos numéricos (`quantity`/`unit_price`/`discount_percentage`/`line_total`) — dado incompleto (`success=false`, sem retry) ou falha técnica (exceção, retry via redrive)? → A: Dado incompleto — mesmo padrão de FR-005, `success=false` sem retry.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Emitir nota fiscal de pedido aprovado (Priority: P1) MVP

Depois que um pedido é validado com sucesso, o sistema precisa gerar automaticamente o documento
fiscal (nota fiscal) em PDF com os dados do cliente e dos itens comprados, guardar esse arquivo de
forma duradoura e avisar quem orquestra o pedido que ele já pode ser concluído.

**Why this priority**: Sem a nota fiscal emitida, o pedido nunca chega ao estado final
`COMPLETED` — é o último passo obrigatório do fluxo principal e o motivo de existir deste serviço.

**Independent Test**: Publicar uma mensagem em `pdf_request_queue` com nome do cliente, documento,
itens e totais completos; verificar que um PDF aparece no S3 sob
`invoices/{ano}/{mes}/{dia}/{order_id}.pdf` e que `pdf_response_queue` recebe `success=true` com o
`s3_key` correspondente.

**Acceptance Scenarios**:

1. **Given** uma mensagem de pedido aprovado com cliente, documento, 1 a 50 itens e totais
   preenchidos, **When** o worker processa a mensagem, **Then** um arquivo PDF é gravado no bucket
   de pedidos na chave `invoices/{ano}/{mes}/{dia}/{order_id}.pdf` (data corrente) contendo nome do
   cliente, documento, cada item (título, SKU, quantidade, preço unitário, desconto) e os totais
   (subtotal, desconto total, total).
2. **Given** o PDF foi gravado com sucesso, **When** o worker publica o resultado, **Then**
   `pdf_response_queue` recebe `success=true`, `s3_key` com o caminho gerado e `error_message`
   nulo.
3. **Given** um pedido com múltiplos itens de categorias e descontos variados, **When** o PDF é
   gerado, **Then** todos os itens aparecem no documento e o total exibido bate com a soma dos
   valores de linha informados na mensagem (o worker não recalcula totais, apenas os exibe).

---

### User Story 2 - Reportar falha de geração sem travar o pedido (Priority: P1)

Quando os dados recebidos não permitem montar uma nota fiscal válida (por exemplo, mensagem sem
itens ou com campo obrigatório ausente), o sistema precisa avisar isso como um resultado de
negócio, e não travar o pedido esperando um PDF que nunca vai existir.

**Why this priority**: Sem esse retorno, um pedido com dados incompletos ficaria para sempre em
`INVOICING`, exigindo intervenção manual. É tão crítico quanto o caminho feliz para a integridade
do fluxo.

**Independent Test**: Publicar uma mensagem em `pdf_request_queue` sem itens (lista vazia) ou sem
`customer_document`; verificar que `pdf_response_queue` recebe `success=false` com `error_message`
descritivo e que nenhum arquivo é gravado no S3.

**Acceptance Scenarios**:

1. **Given** uma mensagem com lista de itens vazia, **When** o worker processa a mensagem,
   **Then** `pdf_response_queue` recebe `success=false`, `s3_key` nulo e `error_message` explicando
   que não há itens para faturar; nenhum objeto é criado no S3.
2. **Given** uma mensagem sem `customer_document` ou sem `customer_name`, **When** o worker
   processa a mensagem, **Then** `pdf_response_queue` recebe `success=false` com `error_message`
   indicando o campo ausente.

---

### User Story 3 - Preservar disponibilidade diante de falha técnica de armazenamento (Priority: P2)

Se o armazenamento de arquivos estiver temporariamente indisponível, o sistema não deve reportar
uma decisão de negócio (nem sucesso, nem falha definitiva) — deve deixar a mensagem para ser
tentada de novo mais tarde, como já acontece nos demais workers do sistema.

**Why this priority**: Reportar `success=false` por uma instabilidade passageira reprovaria
pedidos que na verdade eram válidos, exigindo reprocessamento manual. Preservar o redrive do SQS
evita esse retrabalho.

**Independent Test**: Simular indisponibilidade do S3 ao gravar o objeto; verificar que nenhuma
mensagem é publicada em `pdf_response_queue` e que a mensagem original não é confirmada nem
marcada como processada.

**Acceptance Scenarios**:

1. **Given** o armazenamento S3 está indisponível ou retorna erro técnico ao gravar o objeto,
   **When** o worker tenta processar a mensagem, **Then** nenhuma resposta é publicada em
   `pdf_response_queue`, a mensagem original permanece na fila para nova tentativa, e o erro é
   registrado em log.

---

### User Story 4 - Reprocessar a mesma mensagem sem duplicar a nota fiscal (Priority: P3)

Como qualquer fila pode entregar a mesma mensagem mais de uma vez, gerar e publicar a mesma nota
fiscal duas vezes desperdiçaria armazenamento e poderia confundir quem consome a resposta.

**Why this priority**: Reforça a garantia de idempotência já adotada pelos outros workers do
sistema; tem prioridade menor porque a duplicidade é rara, mas precisa ser coberta antes de ir para
produção.

**Independent Test**: Processar ou publicar duas vezes a mesma mensagem (mesmo `message_id`);
verificar que apenas um PDF é gravado e apenas uma resposta é publicada em
`pdf_response_queue`.

**Acceptance Scenarios**:

1. **Given** uma mensagem com `message_id` já processado com sucesso, **When** ela chega
   novamente ao worker, **Then** nenhum novo PDF é gerado, nenhuma nova mensagem é publicada em
   `pdf_response_queue`, e a duplicidade é registrada em log de nível informativo.

---

### Edge Cases

- Nome do cliente ou título de item muito longo ou com caracteres especiais/acentuados: o PDF deve
  ser gerado normalmente, sem quebrar o layout ou corromper o arquivo.
- `subtotal`, `discount_total` ou `total` ausentes ou nulos na mensagem: tratado como dado
  incompleto (US2), sem geração de PDF.
- Item sem `product_title` ou `product_sku`: exibido no PDF com um valor de fallback (ex.: "—")
  em vez de falhar a geração inteira, desde que os campos numéricos (quantidade, preço) estejam
  presentes.
- Item sem `quantity`, `unit_price`, `discount_percentage` ou `line_total` (Clarifications):
  tratado como dado incompleto (US2) — `success=false`, sem geração de PDF, sem retry.
- Duas mensagens para o mesmo `order_id` mas `message_id` diferentes (ex.: reemissão após edição
  de pedido): cada uma gera e sobrescreve o PDF na mesma chave `invoices/{ano}/{mes}/{dia}/{order_id}.pdf`
  do dia em que foi processada — não é considerado duplicidade.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE consumir mensagens de `pdf_request_queue` contendo nome do cliente,
  documento, itens enriquecidos e totais do pedido aprovado.
- **FR-002**: O sistema DEVE gerar um documento PDF de nota fiscal contendo nome do cliente,
  documento, cada item (título, SKU, quantidade, preço unitário, desconto aplicado) e os totais
  (subtotal, desconto total, total), sem recalcular esses valores — apenas exibindo o que veio na
  mensagem.
- **FR-003**: O sistema DEVE armazenar o PDF gerado no bucket de pedidos, na chave
  `invoices/{ano}/{mes}/{dia}/{order_id}.pdf`, usando a data em que o processamento ocorreu.
- **FR-004**: O sistema DEVE publicar em `pdf_response_queue` uma resposta com `success=true`,
  `s3_key` preenchido com a chave gerada, e `error_message` nulo, quando a geração e o
  armazenamento forem concluídos com sucesso.
- **FR-005**: O sistema DEVE publicar em `pdf_response_queue` uma resposta com `success=false`,
  `s3_key` nulo e `error_message` descritivo, quando os dados da mensagem não permitirem montar uma
  nota fiscal válida (ex.: lista de itens vazia, `customer_document` ou `customer_name` ausentes,
  totais ausentes, ou item sem `quantity`/`unit_price`/`discount_percentage`/`line_total`,
  Clarifications) — sem tentar novamente, já que os mesmos dados nunca produziriam um resultado
  diferente.
- **FR-006**: O sistema NÃO DEVE publicar nenhuma resposta nem confirmar a mensagem original
  quando uma falha técnica de armazenamento (indisponibilidade, timeout, erro 5xx do S3) impedir a
  gravação do PDF — a mensagem deve permanecer disponível para nova tentativa via redrive da fila.
- **FR-007**: O sistema DEVE preservar a idempotência por `message_id`: reprocessar a mesma
  mensagem não deve gerar um novo PDF nem publicar uma nova resposta em `pdf_response_queue`.
- **FR-008**: O sistema NUNCA DEVE escrever diretamente na tabela `orders` — a única saída de
  negócio deste serviço é a mensagem publicada em `pdf_response_queue` (mais o próprio arquivo PDF
  no S3).
- **FR-009**: O sistema DEVE expor um endpoint de verificação de saúde (`health check`) para
  orquestração local, seguindo o mesmo padrão dos demais workers do sistema.
- **FR-010**: O sistema DEVE evitar registrar em log o `customer_document` sem mascaramento.

### Key Entities

- **Solicitação de nota fiscal**: dados recebidos via `pdf_request_queue` — nome do cliente,
  documento do cliente, lista de itens enriquecidos (produto, quantidade, preço, desconto, total de
  linha) e os totais do pedido (subtotal, desconto total, total).
- **Nota fiscal (PDF)**: arquivo binário gerado a partir da solicitação, armazenado no S3 sob
  `invoices/{ano}/{mes}/{dia}/{order_id}.pdf`; representa o documento fiscal definitivo do pedido.
- **Resultado da emissão**: dados publicados via `pdf_response_queue` — indicador de sucesso,
  chave do arquivo no S3 (quando bem-sucedido) e mensagem de erro (quando reprovado).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos pedidos aprovados com dados completos resultam em um PDF armazenado e uma
  resposta `success=true` publicada em até alguns segundos após a chegada da mensagem.
- **SC-002**: 100% das mensagens com dados incompletos (sem itens, sem documento, sem nome)
  resultam em `success=false` com uma mensagem de erro compreensível, sem exigir nova tentativa.
- **SC-003**: Nenhuma nota fiscal é perdida ou gerada em duplicidade quando a mesma mensagem é
  entregue mais de uma vez pela fila.
- **SC-004**: Nenhuma decisão de negócio (sucesso ou falha) é reportada quando o armazenamento
  está temporariamente indisponível — 100% desses casos preservam a mensagem original para nova
  tentativa.

## Assumptions

- O Order Processor é o único publicador de `pdf_request_queue` e o único consumidor de
  `pdf_response_queue`; este serviço nunca lê nem escreve na tabela `orders` diretamente
  (docs/01-dominio-e-contratos.md §4).
- Os totais monetários (`subtotal`, `discount_total`, `total`) já vêm calculados e validados pelo
  Order Validator/Order Processor; este serviço apenas os exibe no documento, sem recalcular.
- "Dados incompletos" (US2/FR-005) é tratado como falha de negócio permanente porque a mesma
  mensagem, reenviada sem alteração, nunca produziria um resultado diferente — mesmo padrão já
  adotado para `PRODUCT_NOT_FOUND` no Order Validator (specs/005-order-validator).
- Falhas técnicas de armazenamento (S3 indisponível, timeout, erro 5xx) seguem o mesmo padrão de
  não confirmação de mensagem já usado pelo Order Validator para falhas do catálogo externo
  (specs/005-order-validator), permitindo que o redrive do SQS repita a tentativa.
- O layout exato do PDF (fontes, cores, cabeçalho) não é coberto por este spec — é uma decisão de
  implementação, desde que contenha todos os campos exigidos pelos FR-002.
- Bucket, prefixo `invoices/` e nomenclatura de chave já estão definidos no contrato existente
  (docs/01-dominio-e-contratos.md §5, §"Armazenamento de arquivos") e não são reabertos aqui.
