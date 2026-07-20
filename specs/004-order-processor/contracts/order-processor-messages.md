# Contrato: mensagens consumidas/publicadas pelo order-processor

Sem HTTP — o "contrato" deste serviço é o conjunto de filas que consome e publica, via
`pedidos_shared` (constitution I.1). Schemas completos de payload em
`docs/01-dominio-e-contratos.md` §5; mapeamento fila→transição em
[data-model.md](../data-model.md).

## Filas consumidas

| Fila | Handler | Idempotência |
|---|---|---|
| `solicitar_pedido_queue` | `handlers/solicitar_pedido.py` | `mark_message_processed` antes de criar o registro |
| `editar_pedido_queue` | `handlers/editar_pedido.py` | idem |
| `cancelar_pedido_queue` | `handlers/cancelar_pedido.py` | idem |
| `validar_pedido_response_queue` | `handlers/validar_pedido_response.py` | idem |
| `pdf_response_queue` | `handlers/pdf_response.py` | idem |

## Filas publicadas

| Fila | Produzida por | Payload |
|---|---|---|
| `validar_pedido_queue` | `solicitar_pedido`, `editar_pedido`, `validar_pedido_response` (quando aprovado, reinicia após edição) | `{customer_document, items}` |
| `pdf_request_queue` | `validar_pedido_response` (quando aprovado) | `{customer_name, customer_document, items enriquecidos, subtotal, discount_total, total}` |

## Regras de contrato

1. **Único escritor de `orders`** — nenhum outro serviço grava esse registro (contrato regra 3 de
   `pedidos_shared-api.md`); os demais serviços (API Gateway, futuros) só leem.
2. **Toda mensagem consumida passa por `mark_message_processed` antes de qualquer efeito
   colateral** — reentrega da mesma mensagem nunca duplica registro, publicação ou transição.
3. **Toda mutação de status usa `is_valid_transition`** — nenhuma transição fora da tabela de
   `docs/01-dominio-e-contratos.md` §2.3 é aplicada; tentativa inválida é erro de negócio (edição/
   cancelamento) ou técnico (resposta de validação/PDF pra pedido em estado incompatível), nunca
   aplicada silenciosamente.
4. **Escrita em `orders` sempre condicional em `version`** — conflito de concorrência recarrega e
   reavalia, até 3 tentativas, antes de tratar como falha técnica (research.md #3).
5. **`GET /health`** (porta 8080) — única superfície HTTP deste serviço, só liveness
   (constitution IV); não faz parte do fluxo de negócio.
