# Contrato: API HTTP do api-gateway

Único serviço do sistema com contrato HTTP externo (constitution I.1, com a exceção documentada
em plan.md pro fluxo BATCH). Schemas completos em [data-model.md](../data-model.md).

## `POST /pedidos`

Cria um novo pedido (US1 + US2). Mesmo endpoint pra clientes HTTP externos e pra chamada interna
do Lambda Line Processor (fluxo BATCH) — `channel` no body distingue a origem.

- **Body**: `SolicitarPedidoRequest`
- **202 Accepted**: `AceitePedidoResponse` — publicado em `solicitar_pedido_queue`, `order_id`
  e `correlation_id` recém-gerados
- **400 Bad Request**: `ErrorResponse` — payload inválido (FR-002); nenhum `order_id` gerado
- **502 Bad Gateway**: `ErrorResponse` — falha técnica ao publicar em `solicitar_pedido_queue`
  (spec.md Edge Cases); nenhum `order_id` retornado como aceito

## `PUT /pedidos/{order_id}`

Edita um pedido existente (US3), reabrindo o ciclo de processamento.

- **Body**: `EditarPedidoRequest`
- **202 Accepted**: `AceitePedidoResponse` — publicado em `editar_pedido_queue`
- **400 Bad Request**: `ErrorResponse` — payload inválido
- **404 Not Found**: `ErrorResponse` — `order_id` não existe em `orders`
- **409 Conflict**: `ErrorResponse` — pedido em estado que não permite edição (`is_valid_transition`
  reprova a transição pra `PROCESSING`)
- **502 Bad Gateway**: `ErrorResponse` — falha técnica ao publicar em `editar_pedido_queue`

## `POST /pedidos/{order_id}/cancelamento`

Cancela um pedido existente (US4).

- **Body**: `CancelarPedidoRequest`
- **202 Accepted**: `AceitePedidoResponse` — publicado em `cancelar_pedido_queue` com `reason`
- **400 Bad Request**: `ErrorResponse` — `reason` ausente (FR-007)
- **404 Not Found**: `ErrorResponse` — `order_id` não existe
- **409 Conflict**: `ErrorResponse` — pedido em estado que não permite cancelamento
  (`is_valid_transition` reprova a transição pra `CANCELLED`)
- **502 Bad Gateway**: `ErrorResponse` — falha técnica ao publicar em `cancelar_pedido_queue`

## `GET /pedidos/{order_id}`

Consulta um pedido específico (US5).

- **200 OK**: `PedidoResponse` — `customer_document` mascarado (FR-008)
- **404 Not Found**: `ErrorResponse` — `order_id` não existe (inclui a janela de consistência
  eventual antes do Order Processor persistir o registro)

## `GET /pedidos?customerId={customer_id}`

Lista os pedidos de um cliente (US6), mais recentes primeiro.

- **200 OK**: `ListaPedidosResponse` — lista vazia se o cliente não tem pedidos, nunca erro

## `GET /health`

Liveness check (constitution IV).

- **200 OK**: `{"status": "ok"}`

## Regras de contrato

1. Toda resposta de erro (400/404/409/502) usa `ErrorResponse` (`detail: str`) — formato único em
   toda a API.
2. `202 Accepted`, nunca `201 Created`, pras operações de escrita (criar/editar/cancelar) — o
   recurso ainda não foi persistido no momento da resposta (FR-005, consistência eventual).
3. Nenhuma rota deste serviço escreve em `orders` — `PUT`/`POST` de criação/edição/cancelamento só
   publicam mensagem; `GET` só lê.
