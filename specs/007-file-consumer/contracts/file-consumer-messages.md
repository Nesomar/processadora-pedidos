# Contratos de Mensagem: File Consumer

Fonte de verdade: `docs/01-dominio-e-contratos.md` §5/§6. Diferente das demais features, as duas
filas desta feature **não** usam o `MessageEnvelope` comum (research.md #2) — o corpo da mensagem
SQS é o JSON abaixo diretamente.

## `s3_notifications_queue` — consumida

Evento nativo do S3 (schema AWS padrão, confirmado empiricamente contra o Ministack —
research.md #4):

```json
{
  "Records": [
    {
      "eventName": "ObjectCreated:Put",
      "s3": {
        "bucket": { "name": "pedidos-bucket" },
        "object": { "key": "uploads/pedidos_20260718.txt" }
      }
    }
  ]
}
```

Mensagem de teste automática (enviada uma vez ao configurar a notificação do bucket) — descartada
sem processar:

```json
{ "Service": "Amazon S3", "Event": "s3:TestEvent", "Bucket": "pedidos-bucket" }
```

## `pedido_lines_queue` — publicada

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

Para `operation="EDITAR"`, `order_id` traz a UUID do registro e `parsed` segue o mesmo formato
acima. Para `operation="CANCELAR"` (Clarifications):

```json
{
  "source_file": "pedidos_20260718.txt",
  "line_number": 55,
  "operation": "CANCELAR",
  "raw_line": "1CANCELAR ...",
  "order_id": "11111111-1111-1111-1111-111111111111",
  "parsed": { "reason": "Cancelamento via arquivo batch" }
}
```

## Erros de processamento (log estruturado, não publicados — Clarifications)

Todo erro (arquivo inteiro, linha ou pedido) é registrado em log estruturado JSON com pelo menos
`source_file` e, quando aplicável, `line_number` — nunca em um artefato de relatório separado no
armazenamento de arquivos (Clarifications).
