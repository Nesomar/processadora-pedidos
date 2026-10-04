# Contrato: `GET /pedidos/{order_id}/nota-fiscal`

Extensão de `docs/01-dominio-e-contratos.md` — não altera mensagens de fila.

## Request

`GET /pedidos/{order_id}/nota-fiscal` — sem corpo, sem parâmetros de query.

## Respostas

| Status | Quando | Corpo |
|---|---|---|
| 200 | pedido `COMPLETED` e objeto existe | bytes do PDF; `Content-Type: application/pdf`; `Content-Disposition: inline; filename="nota-fiscal-{order_id}.pdf"` |
| 404 | pedido inexistente | `{"detail": "Pedido não encontrado"}` |
| 404 | `COMPLETED` sem chave ou objeto ausente | `{"detail": "PDF não encontrado no armazenamento"}` |
| 409 | pedido em andamento (`RECEIVED`, `PROCESSING`, `VALIDATING`, `VALIDATED`, `INVOICING`) | `{"detail": "Nota fiscal ainda não disponível, tente novamente"}` |
| 410 | `REJECTED`, `FAILED` ou `CANCELLED` | `{"detail": "Nenhum PDF será gerado para este pedido"}` |
| 500 | falha técnica do armazenamento | erro genérico, sem detalhes internos |

Nenhuma resposta contém chave, bucket, endpoint ou credenciais do S3.

## Mudança em `GET /pedidos/{order_id}` e `GET /pedidos`

- Removido: `invoice_s3_key`.
- Adicionado: `invoice_available: bool` — `true` somente quando o PDF pode ser baixado em
  `/pedidos/{order_id}/nota-fiscal`.

## Log

Um log JSON por acesso, com `orderId`, `correlationId` e resultado; sem `customer_document`.
