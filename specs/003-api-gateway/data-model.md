# Data Model: API Gateway

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## Entidades reaproveitadas (não redefinidas nesta feature)

`Order`, `OrderItem`, `MessageEnvelope`, `OrderStatus`, `is_valid_transition`, `mask_document` —
todos de `pedidos_shared` (feature `001-fundacao-compartilhada`). Ver
[data-model.md de 001](../001-fundacao-compartilhada/data-model.md) pros campos completos. Esta
feature só importa (`from pedidos_shared import ...`), nunca redefine.

## Schemas da API (Pydantic, próprios desta feature — `schemas.py`)

Distintos de `Order`/`OrderItem`: são a forma de entrada/saída HTTP, não o registro persistido.

### `SolicitarPedidoRequest` (body de `POST /pedidos`)

| Campo | Tipo | Nota |
|---|---|---|
| `customer_id` | `str` | ≤20 chars, alfanumérico (FR-002) |
| `customer_name` | `str` | — |
| `customer_document` | `str` | só dígitos (FR-002) |
| `channel` | `Literal["HTTP", "BATCH"]` | default `"HTTP"` |
| `items` | `list[ItemRequest]` | 1..50 itens (FR-002) |
| `source_file` | `str \| None` | preenchido só quando `channel == "BATCH"` |
| `source_line` | `int \| None` | preenchido só quando `channel == "BATCH"` |

### `ItemRequest`

| Campo | Tipo | Nota |
|---|---|---|
| `product_id` | `int` | — |
| `quantity` | `int` | `> 0` (FR-002) |

### `EditarPedidoRequest` (body de `PUT /pedidos/{order_id}`)

Mesmos campos de `SolicitarPedidoRequest`, incluindo `channel` — `docs/01-dominio-e-contratos.md`
§5 mostra `channel` no payload de `editar_pedido_queue`, igual ao de `solicitar_pedido_queue`.

### `CancelarPedidoRequest` (body de `POST /pedidos/{order_id}/cancelamento`)

| Campo | Tipo | Nota |
|---|---|---|
| `reason` | `str` | obrigatório (FR-007) |

### `AceitePedidoResponse` (resposta 202 de criar/editar/cancelar)

| Campo | Tipo | Nota |
|---|---|---|
| `order_id` | `str` | UUID v4 gerado nesta requisição (criar) ou o existente (editar/cancelar) |
| `correlation_id` | `str` | UUID v4 gerado nesta requisição (criar) ou o existente, propagado sem alteração (editar/cancelar) — `correlation_id` é imutável após gerado (`docs/01-dominio-e-contratos.md` §2.2) |

### `PedidoResponse` (resposta 200 de `GET /pedidos/{order_id}` e itens de `GET /pedidos`)

Espelha `Order` de `pedidos_shared`, com uma diferença: `customer_document` sempre mascarado
(`mask_document`, FR-008). Demais campos idênticos a `Order` (`order_id`, `customer_id`,
`customer_name`, `channel`, `items`, `subtotal`, `discount_total`, `total`, `status`,
`status_reason`, `invoice_s3_key`, `correlation_id`, `source_file`, `source_line`, `created_at`,
`updated_at`, `version`).

### `ListaPedidosResponse` (corpo de `GET /pedidos?customerId=X`)

| Campo | Tipo | Nota |
|---|---|---|
| `pedidos` | `list[PedidoResponse]` | ordenados do mais recente pro mais antigo (GSI1) |

### `ErrorResponse` (400/404/409)

| Campo | Tipo | Nota |
|---|---|---|
| `detail` | `str` | mensagem de erro legível |

## Leitura em `orders` (via `adapters/orders_repository.py`)

- `get_by_id(order_id) -> Order | None`: `get_item` com `PK=ORDER#{order_id}`, `SK=METADATA`.
- `query_by_customer(customer_id) -> list[Order]`: `query` em `GSI1`, `GSI1PK=CUSTOMER#{customer_id}`,
  `ScanIndexForward=False` (mais recente primeiro, por `GSI1SK={created_at}#{order_id}`).

Nenhum método de escrita é exposto (research.md #3).
