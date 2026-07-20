# Contratos de Mensagem: Order Validator

Fonte de verdade: `docs/01-dominio-e-contratos.md` §5. Os campos aqui são idênticos aos já
documentados lá — este arquivo só acrescenta os 2 códigos de erro novos (`INVALID_DOCUMENT`,
`ORDER_TOTAL_EXCEEDS_LIMIT`) definidos nesta feature (spec.md Assumptions) e explicita que
`product_id` é `null` para erros do pedido como um todo.

## `validar_pedido_queue` — consumida

```json
{
  "customer_document": "12345678901",
  "items": [{ "product_id": 1, "quantity": 50 }]
}
```

## `validar_pedido_response_queue` — publicada

### Aprovado

```json
{
  "approved": true,
  "errors": [],
  "enriched_items": [
    {
      "product_id": 1,
      "quantity": 50,
      "unit_price": "9.99",
      "discount_percentage": "10.48",
      "line_total": "447.05",
      "product_title": "Essence Mascara Lash Princess",
      "product_sku": "BEA-ESS-ESS-001"
    }
  ],
  "subtotal": "499.50",
  "discount_total": "52.45",
  "total": "447.05"
}
```

### Reprovado — item específico

```json
{
  "approved": false,
  "errors": [
    {
      "code": "BELOW_MINIMUM_ORDER_QUANTITY",
      "product_id": 1,
      "message": "Quantidade 10 abaixo do mínimo 48"
    },
    {
      "code": "INSUFFICIENT_STOCK",
      "product_id": 1,
      "message": "Quantidade 10 excede o estoque disponível (5)"
    }
  ],
  "enriched_items": null,
  "subtotal": null,
  "discount_total": null,
  "total": null
}
```

Um item pode gerar mais de um erro simultâneo (US3 AC4) — exceto `PRODUCT_NOT_FOUND`, que
exclui as demais checagens daquele item.

### Reprovado — documento inválido

```json
{
  "approved": false,
  "errors": [
    {
      "code": "INVALID_DOCUMENT",
      "product_id": null,
      "message": "customer_document '111.111.111-11' não é um CPF/CNPJ válido"
    }
  ],
  "enriched_items": null,
  "subtotal": null,
  "discount_total": null,
  "total": null
}
```

### Reprovado — limite de total excedido

```json
{
  "approved": false,
  "errors": [
    {
      "code": "ORDER_TOTAL_EXCEEDS_LIMIT",
      "product_id": null,
      "message": "Total do pedido (152340.00) excede o limite máximo de 100000.00"
    }
  ],
  "enriched_items": null,
  "subtotal": null,
  "discount_total": null,
  "total": null
}
```

## Códigos de erro (`errors[].code`)

| Código | Nível | Documentado em |
|---|---|---|
| `PRODUCT_NOT_FOUND` | item (`product_id` preenchido) | extensão desta feature (spec.md Assumptions) |
| `BELOW_MINIMUM_ORDER_QUANTITY` | item (`product_id` preenchido) | `docs/01-dominio-e-contratos.md` §5 |
| `INSUFFICIENT_STOCK` | item (`product_id` preenchido) | extensão desta feature |
| `INVALID_DOCUMENT` | pedido (`product_id` nulo) | extensão desta feature |
| `ORDER_TOTAL_EXCEEDS_LIMIT` | pedido (`product_id` nulo) | extensão desta feature |

## API externa consumida (catálogo)

`GET https://dummyjson.com/products/{id}` — campos usados: `id`, `title`, `price`, `stock`,
`minimumOrderQuantity`, `availabilityStatus`, `sku`, `discountPercentage`
(`docs/01-dominio-e-contratos.md` §2.1). `404` → `PRODUCT_NOT_FOUND` (erro de negócio). Timeout
ou `5xx` (após retry curto do cliente HTTP, research.md #1) → falha técnica, mensagem não
confirmada.
