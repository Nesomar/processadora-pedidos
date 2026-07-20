# order-processor

Worker orquestrador central do Sistema de Processamento de Pedidos
(`docs/01-dominio-e-contratos.md` §1). Sem porta HTTP de negócio — consome 5 filas e publica em
2, sempre via `pedidos_shared`. **Único serviço do sistema que escreve na tabela `orders`**
(contrato regra 3 de `pedidos_shared-api.md`).

## Filas consumidas → publicadas

| Consome | Handler | Publica |
|---|---|---|
| `solicitar_pedido_queue` | `handlers/solicitar_pedido.py` | `validar_pedido_queue` |
| `editar_pedido_queue` | `handlers/editar_pedido.py` | `validar_pedido_queue` |
| `cancelar_pedido_queue` | `handlers/cancelar_pedido.py` | — |
| `validar_pedido_response_queue` | `handlers/validar_pedido_response.py` | `pdf_request_queue` (se aprovado) |
| `pdf_response_queue` | `handlers/pdf_response.py` | — |

Contrato completo: [`specs/004-order-processor/contracts/order-processor-messages.md`](../../specs/004-order-processor/contracts/order-processor-messages.md).

## Garantias

- **Idempotência**: `is_message_processed` checa ANTES do handler rodar (só leitura, não marca);
  `mark_message_processed` só é chamado DEPOIS do handler concluir com sucesso ou rejeitar por
  erro de negócio — nunca antes. Isso garante que uma falha técnica não "queime" a mensagem: o
  redrive do SQS reentrega e o handler roda de verdade de novo, em vez de ser descartado como
  duplicata sem nunca ter processado.
- **Máquina de estados**: toda mutação de status usa `is_valid_transition` de `pedidos_shared` —
  nenhuma tabela de transição própria.
- **Concorrência otimista**: toda escrita em `orders` é condicionada a `version`; conflito
  recarrega e reavalia, até 3 tentativas, antes de virar falha técnica.
- **Erro de negócio vs técnico**: transição rejeitada (estado incompatível) grava `status_reason`
  no registro do pedido (constitution I.5) via `record_rejection`, confirma a mensagem e loga
  aviso — retry não ajudaria, o estado não muda sozinho. Falha técnica (ex.: Ministack
  indisponível) não confirma a mensagem — o redrive nativo do SQS assume.

## Variáveis de ambiente

Usa `pedidos_shared.Settings` — mesmo `.env` do resto do sistema. Requer, no mínimo:
`AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`PROCESSED_MESSAGES_TABLE_NAME`, `ORDERS_TABLE_NAME`, `SOLICITAR_PEDIDO_QUEUE_URL`,
`EDITAR_PEDIDO_QUEUE_URL`, `CANCELAR_PEDIDO_QUEUE_URL`, `VALIDAR_PEDIDO_QUEUE_URL`,
`VALIDAR_PEDIDO_RESPONSE_QUEUE_URL`, `PDF_REQUEST_QUEUE_URL`, `PDF_RESPONSE_QUEUE_URL`.

## Rodar localmente

```bash
uv sync --package order-processor
source .env  # Ministack já rodando (feature 002-infraestrutura-local)
uv run --package order-processor python -m order_processor.main
```

`GET http://localhost:8080/health` responde `{"status":"ok"}` (constitution IV).

## Testes

```bash
# unitários (não requerem Ministack)
uv run --package order-processor pytest services/order-processor/tests -v -k "not integration"

# lint/format
uv run --package order-processor ruff check services/order-processor
uv run --package order-processor ruff format --check services/order-processor
```

Testes de integração (nomeados `*_integration_*`) rodam contra Ministack real e pulam
automaticamente se ele não estiver acessível.
