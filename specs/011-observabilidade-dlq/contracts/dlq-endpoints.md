# Contrato: endpoints de DLQ

Extensão de `docs/01-dominio-e-contratos.md` — não altera mensagens de fila. Sem autenticação
(uso operacional, ambiente local). `{fila}` é a fila de origem, uma das 9 de §4.

## `GET /dlqs`

`200`:

```json
{ "dlqs": [ { "queue": "validar_pedido_queue", "dlq": "validar_pedido_queue_dlq", "messages": 1 } ] }
```

Sempre as 9 filas, em ordem fixa. Falha técnica ao consultar o SQS → `502`.

## `GET /dlqs/{fila}/mensagens?limit=10`

`limit`: 1–50, padrão 10. Somente leitura.

`200`:

```json
{
  "queue": "validar_pedido_queue",
  "messages": [
    {
      "message_id": "…", "sent_at": "2026-10-03T21:00:00Z",
      "order_id": "…", "correlation_id": "…",
      "source_file": null, "source_line": null,
      "body": { "payload": { "customer_document": "*******8901" } }
    }
  ],
  "has_more": false
}
```

| Status | Quando |
|---|---|
| 200 | DLQ conhecida (lista pode ser vazia) |
| 404 | `{fila}` fora das 9 (`{"detail": "Fila não encontrada"}`) |
| 400 | `limit` fora de 1–50 (o gateway converte erro de validação em 400) |
| 502 | falha técnica do SQS |

## `POST /dlqs/{fila}/reprocessamento`

Corpo opcional: `{"message_id": "…"}`. Sem corpo (ou `message_id` ausente) → DLQ inteira.

`200`: `{"queue": "validar_pedido_queue", "reprocessed": 3, "has_more": false}` — `0` para DLQ vazia ou
já esvaziada. Uma chamada varre até ~1000 mensagens; se a DLQ for maior, `has_more` é `true` e basta
chamar de novo. Com `message_id` não achado após varredura limitada, o `404` informa isso no `detail`.

| Status | Quando |
|---|---|
| 200 | operação concluída |
| 404 | `{fila}` fora das 9, ou `message_id` não está na DLQ |
| 502 | falha técnica; mensagens ainda não movidas permanecem na DLQ |

Garantias: a mensagem só é deletada da DLQ depois de reenviada à origem; corpo reenviado idêntico.

## Logs

Um log JSON por chamada: fila, DLQ, quantidade (listada/movida) e resultado; nunca
`customer_document` em claro.
