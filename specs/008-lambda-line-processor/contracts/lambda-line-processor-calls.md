# Contratos: Lambda Line Processor

Fonte de verdade dos payloads HTTP: `services/api-gateway/src/api_gateway/schemas.py` e
`docs/01-dominio-e-contratos.md` §5 (payload de `solicitar_pedido_queue`/`editar_pedido_queue`/
`cancelar_pedido_queue`, que é exatamente o corpo esperado por cada endpoint). Este arquivo só
documenta o mapeamento operação → chamada, não redefine os schemas.

## `pedido_lines_queue` — consumida

Mesmo contrato de `specs/007-file-consumer/contracts/file-consumer-messages.md` (esta feature não
o redefine):

```json
{
  "source_file": "pedidos_20260718.txt",
  "line_number": 42,
  "operation": "SOLICITAR",
  "raw_line": "1SOLICITAR ...",
  "order_id": null,
  "parsed": {
    "customer_id": "CUST00001",
    "customer_name": "MARIA SILVA",
    "customer_document": "12345678901",
    "channel": "BATCH",
    "items": [{ "product_id": 1, "quantity": 50 }],
    "source_file": "pedidos_20260718.txt",
    "source_line": 42
  }
}
```

## Mapeamento `operation` → chamada ao API Gateway

| `operation` | Método | Path | Corpo | Sucesso | Recusa permanente |
|---|---|---|---|---|---|
| `SOLICITAR` | `POST` | `/pedidos` | `parsed` | `202` | `400` |
| `EDITAR` | `PUT` | `/pedidos/{order_id}` | `parsed` | `202` | `400`, `404`, `409` |
| `CANCELAR` | `POST` | `/pedidos/{order_id}/cancelamento` | `parsed` | `202` | `404`, `409` |

Qualquer `operation` fora dessas três, ou `order_id` ausente para `EDITAR`/`CANCELAR`, é tratado
como recusa de negócio permanente sem chamar o API Gateway (Edge Cases do spec.md).

Qualquer status fora de `2xx`/`400`/`404`/`409` (em especial `5xx`, ou o API Gateway não
responder) é falha técnica — a mensagem original não é confirmada.
