# Data Model: Order Processor

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## Entidades reaproveitadas (não redefinidas nesta feature)

`Order`, `OrderItem`, `MessageEnvelope`, `OrderStatus`, `is_valid_transition`,
`mark_message_processed` — todos de `pedidos_shared` (feature `001-fundacao-compartilhada`). Ver
[data-model.md de 001](../001-fundacao-compartilhada/data-model.md) pros campos completos. Este
serviço é o único que escreve `Order` na tabela `orders`.

## Mapeamento fila consumida → transição → fila publicada

| Fila consumida | Transição aplicada | Dados armazenados em `Order` | Fila publicada |
|---|---|---|---|
| `solicitar_pedido_queue` | `—`→`RECEIVED`→`PROCESSING`→`VALIDATING` | todos os campos do payload (§5); `order_id`/`correlation_id` vêm do `MessageEnvelope` | `validar_pedido_queue` |
| `editar_pedido_queue` | `RECEIVED`/`VALIDATED`/`REJECTED`→`PROCESSING`→`VALIDATING` | campos do payload sobrescrevem os atuais | `validar_pedido_queue` |
| `cancelar_pedido_queue` | `RECEIVED`/`PROCESSING`/`VALIDATING`/`VALIDATED`→`CANCELLED` | `status_reason` = `reason` do payload | — |
| `validar_pedido_response_queue` (`approved=true`) | `VALIDATING`→`VALIDATED`→`INVOICING` | `items` (enriquecidos), `subtotal`, `discount_total`, `total` | `pdf_request_queue` |
| `validar_pedido_response_queue` (`approved=false`) | `VALIDATING`→`REJECTED` | `status_reason` = concatenação das mensagens de `errors[]` | — |
| `pdf_response_queue` (`success=true`) | `INVOICING`→`COMPLETED` | `invoice_s3_key` = `s3_key` do payload | — |
| `pdf_response_queue` (`success=false`) | `INVOICING`→`FAILED` | `status_reason` = `error_message` do payload | — |

Payloads exatos de cada fila: `docs/01-dominio-e-contratos.md` §5 (já implementados em
`pedidos_shared`, esta feature não inventa campo novo).

## `adapters/orders_repository.py` — contrato

| Função | Papel |
|---|---|
| `get_by_id(dynamodb, table_name, order_id) -> Order \| None` | leitura simples (`get_item`) |
| `create(dynamodb, table_name, order) -> None` | primeira escrita; `ConditionExpression = attribute_not_exists(PK)`; `version = 0` |
| `update_with_version(dynamodb, table_name, order_id, expected_version, apply_fn) -> Order` | recarrega o item, aplica `apply_fn(order) -> Order` (que já checou `is_valid_transition`), grava com `ConditionExpression = version = :expected_version`, incrementa `version`; em `ConditionalCheckFailedException`, recarrega e tenta de novo (até 3x — research.md #3); esgotadas as tentativas, levanta `ConflitoDeConcorrenciaError` |

## `domain/transicoes.py` — contrato

Cada função recebe o `Order` atual (ou seu `status`) e os dados novos, devolve o novo status (ou
levanta `TransicaoInvalidaError` se `is_valid_transition` reprovar) — nenhuma decide I/O.

| Função | Uso |
|---|---|
| `aplicar_solicitacao(order_atual: None) -> OrderStatus` | sempre `VALIDATING` (criação já publica em `validar_pedido_queue` na mesma operação — `PROCESSING` colapsado) |
| `aplicar_edicao(status_atual: OrderStatus) -> OrderStatus` | `VALIDATING` se `is_valid_transition(atual, PROCESSING)`, senão erro (mesmo colapso) |
| `aplicar_cancelamento(status_atual: OrderStatus) -> OrderStatus` | `CANCELLED` se `is_valid_transition(atual, CANCELLED)`, senão erro |
| `aplicar_resposta_validacao(status_atual: OrderStatus, approved: bool) -> OrderStatus` | `VALIDATED`→(imediato)`INVOICING` se aprovado, `REJECTED` se reprovado |
| `aplicar_resposta_pdf(status_atual: OrderStatus, success: bool) -> OrderStatus` | `COMPLETED` se sucesso, `FAILED` se falha |

## `domain/mensagens.py` — contrato

| Função | Papel |
|---|---|
| `montar_payload_validacao(order: Order) -> dict` | `{customer_document, items: [{product_id, quantity}]}` (§5) |
| `montar_payload_pdf(order: Order) -> dict` | `{customer_name, customer_document, items (enriquecidos), subtotal, discount_total, total}` (§5) |
