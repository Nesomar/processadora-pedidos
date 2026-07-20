# Contratos de Mensagem: PDF Generator

Fonte de verdade: `docs/01-dominio-e-contratos.md` §5. Os campos aqui são idênticos aos já
documentados lá — este arquivo só acrescenta o caso de falha de negócio (`success=false` por
dados incompletos, FR-005) que a doc original não detalhava.

## `pdf_request_queue` — consumida

```json
{
  "customer_name": "Maria Silva",
  "customer_document": "12345678901",
  "items": [
    {
      "product_id": 1,
      "quantity": 3,
      "unit_price": "9.99",
      "discount_percentage": "10.48",
      "line_total": "26.82",
      "product_title": "Essence Mascara Lash Princess",
      "product_sku": "BEA-ESS-ESS-001"
    }
  ],
  "subtotal": "29.97",
  "discount_total": "3.15",
  "total": "26.82"
}
```

## `pdf_response_queue` — publicada

### Sucesso

```json
{
  "success": true,
  "s3_key": "invoices/2026/07/20/{order_id}.pdf",
  "error_message": null
}
```

### Falha de negócio — dados incompletos (extensão desta feature, FR-005)

```json
{
  "success": false,
  "s3_key": null,
  "error_message": "lista de itens vazia — nada para faturar"
}
```

Falha técnica (S3 indisponível/timeout/5xx) **não** publica nenhuma mensagem em
`pdf_response_queue` — a mensagem original permanece em `pdf_request_queue` para retry via redrive
(FR-006).

## Armazenamento gerado

`PUT` no bucket de pedidos (`Settings.pedidos_bucket_name`), chave
`invoices/{ano:04d}/{mes:02d}/{dia:02d}/{order_id}.pdf` (data do processamento, UTC), `Content-Type:
application/pdf` (`data-model.md`, research.md #2/#3).
