# Data Model: Fundação Compartilhada (pedidos_shared)

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## StatusPedido (enum)

| Valor | Significado |
|---|---|
| `RECEBIDO` | Pedido aceito pelo ponto de entrada, ainda não validado |
| `VALIDANDO` | Order Validator consumiu a mensagem e está aplicando as regras de negócio |
| `VALIDADO` | Todas as regras de negócio passaram |
| `REJEITADO` | Ao menos uma regra de negócio falhou (`statusReason` preenchido) |
| `GERANDO_PDF` | PDF Generator está montando o documento do pedido |
| `CONCLUIDO` | Pedido processado com sucesso, PDF disponível |
| `ERRO` | Falha técnica não recuperável (`statusReason` preenchido) |

### Transições válidas

```
RECEBIDO    → VALIDANDO
VALIDANDO   → VALIDADO | REJEITADO
VALIDADO    → GERANDO_PDF
GERANDO_PDF → CONCLUIDO
{qualquer}  → ERRO
```

- `REJEITADO`, `CONCLUIDO` e `ERRO` são estados finais (nenhuma transição de saída).
- Toda transição fora deste grafo MUST ser rejeitada por `is_valid_transition()` antes de qualquer
  escrita no DynamoDB (constitution I.2, I.3 — `ConditionExpression` usa o estado atual como parte
  da condição de idempotência).

## Pedido (Order)

| Campo | Tipo | Regra |
|---|---|---|
| `order_id` | `str` (UUID) | Identificador único, gerado no ponto de entrada |
| `status` | `StatusPedido` | Estado atual; toda mutação passa por `is_valid_transition()` |
| `status_reason` | `str \| None` | Obrigatório quando `status` é `REJEITADO` ou `ERRO`; `None` nos demais |
| `items` | `list[ItemPedido]` | Não vazio |
| `customer_document` | `str` | Nunca logado em claro — sempre via `mask_document()` |
| `correlation_id` | `str` (UUID) | Gerado uma vez no ponto de entrada, imutável pelo resto da cadeia |
| `created_at` / `updated_at` | `datetime` (UTC) | `updated_at` atualizado a cada transição |

## Contratos de mensagem (Pydantic, um por evento SQS)

Todos herdam um campo comum `correlation_id: str` e `order_id: str` (exceto eventos anteriores à
criação do pedido, que carregam apenas `correlation_id`).

| Modelo | Publicado por | Consumido por | Campos próprios |
|---|---|---|---|
| `PedidoSolicitado` | api-gateway | order-processor | `items`, `customer_document` |
| `PedidoParaValidar` | order-processor | order-validator | `items`, `customer_document` |
| `PedidoValidado` | order-validator | order-processor | — |
| `PedidoRejeitado` | order-validator | order-processor | `status_reason` |
| `PedidoParaGerarPdf` | order-processor | pdf-generator | `items` |
| `PdfGerado` | pdf-generator | order-processor | `pdf_s3_key` |

**Nota**: o conjunto exato de mensagens do fluxo de arquivo (lambda-line-processor/file-consumer)
fica para a spec desse fluxo (ver Assumptions em spec.md); esta lista cobre o fluxo síncrono via
api-gateway descrito nas User Stories 1–3.

## Settings

| Campo | Origem (env var) | Obrigatório |
|---|---|---|
| `ministack_endpoint_url` | `MINISTACK_ENDPOINT_URL` | Sim |
| `orders_table_name` | `ORDERS_TABLE_NAME` | Sim |
| `orders_bucket_name` | `ORDERS_BUCKET_NAME` | Sim |
| `*_queue_url` (uma por fila que o serviço usa) | `{NOME}_QUEUE_URL` | Sim, por fila usada |
| `aws_region` | `AWS_REGION` | Sim (Ministack exige região válida) |

Falha de instanciação (`pydantic.ValidationError`) na ausência de qualquer variável obrigatória —
cobre FR-005.

## Função de mascaramento

`mask_document(document: str) -> str`

- `len(document) > 4`: mantém os últimos 4 caracteres, substitui o restante por `*`.
- `len(document) <= 4`: retorna `"*" * len(document)` (mascaramento total).
- Preserva o comprimento original em ambos os casos.

## FieldSpec / parse_fixed_width

| Campo | Tipo |
|---|---|
| `name` | `str` |
| `start` | `int` (0-based, inclusivo) |
| `end` | `int` (exclusivo) |

`parse_fixed_width(line: str, layout: list[FieldSpec]) -> dict[str, str]` levanta
`LinhaCurtaError` (exceção de domínio) quando `len(line) < max(f.end for f in layout)`.
