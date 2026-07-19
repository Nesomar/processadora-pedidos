# Data Model: Fundação Compartilhada (pedidos_shared)

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

Todo campo/tabela abaixo é copiado de `docs/01-dominio-e-contratos.md` (§2, §3, §5) — não é uma
decisão desta feature.

## OrderStatus (enum)

`RECEIVED, PROCESSING, VALIDATING, VALIDATED, REJECTED, INVOICING, COMPLETED, CANCELLED, FAILED`

### Transições válidas (§2.3)

| De | Para |
|---|---|
| — | `RECEIVED` |
| `RECEIVED` | `PROCESSING` |
| `PROCESSING` | `VALIDATING` |
| `VALIDATING` | `VALIDATED` \| `REJECTED` |
| `VALIDATED` | `INVOICING` |
| `INVOICING` | `COMPLETED` \| `FAILED` |
| `RECEIVED`, `PROCESSING`, `VALIDATING`, `VALIDATED` | `CANCELLED` |
| `RECEIVED`, `VALIDATED`, `REJECTED` | `PROCESSING` (edição reinicia o ciclo) |
| qualquer não-terminal | `FAILED` (erro técnico após esgotar retries) |

Terminais: `COMPLETED`, `CANCELLED`, `REJECTED`, `FAILED`. Comando sobre terminal (exceto edição
de `REJECTED`) → erro de negócio (409, tratado pelo serviço chamador, não por este pacote).

## OrderItem

| Campo | Tipo | Nota |
|---|---|---|
| `product_id` | `int` | — |
| `quantity` | `int` | `> 0` |
| `unit_price` | `Decimal \| None` | preenchido pelo Validator |
| `discount_percentage` | `Decimal \| None` | preenchido pelo Validator |
| `line_total` | `Decimal \| None` | `quantity * unit_price * (1 - discount/100)` |
| `product_title` | `str \| None` | snapshot pra nota fiscal |
| `product_sku` | `str \| None` | — |

## Order

| Campo | Tipo | Nota |
|---|---|---|
| `order_id` | `str` | UUID v4, gerado pelo API Gateway |
| `customer_id` | `str` | ≤20 chars, alfanumérico |
| `customer_name` | `str` | — |
| `customer_document` | `str` | CPF/CNPJ, só dígitos; nunca logado em claro (`mask_document`) |
| `channel` | `Literal["HTTP", "BATCH"]` | — |
| `items` | `list[OrderItem]` | 1..50 itens |
| `subtotal`, `discount_total`, `total` | `Decimal \| None` | — |
| `status` | `OrderStatus` | toda mutação passa por `is_valid_transition()` |
| `status_reason` | `str \| None` | obrigatório em `REJECTED`/`FAILED` |
| `invoice_s3_key` | `str \| None` | — |
| `correlation_id` | `str` | rastreio ponta a ponta, imutável após gerado |
| `source_file`, `source_line` | `str \| None`, `int \| None` | preenchidos quando `channel == BATCH` |
| `created_at`, `updated_at` | `datetime` (UTC) | — |
| `version` | `int` | controle de concorrência otimista |

## MessageEnvelope

| Campo | Tipo |
|---|---|
| `message_id` | `str` (UUID v4, gerado pelo produtor) |
| `correlation_id` | `str` (propagado sem alteração por todo o fluxo) |
| `order_id` | `str` |
| `occurred_at` | `datetime` (UTC) |
| `payload` | `dict` (específico por tipo de mensagem, §5) |

## ProcessedMessage (idempotência, tabela `processed_messages`)

| Atributo | Papel |
|---|---|
| `PK` = `MSG#{message_id}` | partition key |
| `consumer` | nome do serviço consumidor |
| `processed_at` | timestamp |
| `ttl` | expiração em 7 dias (TTL nativo DynamoDB) |

## Settings

| Campo | Origem (env var) | Obrigatório |
|---|---|---|
| `aws_endpoint_url` | `AWS_ENDPOINT_URL` | Sim |
| `aws_region` | `AWS_REGION` | Sim |
| `aws_access_key_id` | `AWS_ACCESS_KEY_ID` | Sim |
| `aws_secret_access_key` | `AWS_SECRET_ACCESS_KEY` | Sim |
| `orders_table_name` | `ORDERS_TABLE_NAME` (default `orders`) | Não — só order-processor usa |
| `processed_messages_table_name` | `PROCESSED_MESSAGES_TABLE_NAME` (default `processed_messages`) | Sim (todo consumidor precisa) |
| `pedidos_bucket_name` | `PEDIDOS_BUCKET_NAME` (default `pedidos-bucket`) | Não — só quem lê/escreve S3 |
| `solicitar_pedido_queue_url`, `editar_pedido_queue_url`, `cancelar_pedido_queue_url`, `validar_pedido_queue_url`, `validar_pedido_response_queue_url`, `pdf_request_queue_url`, `pdf_response_queue_url`, `s3_notifications_queue_url`, `pedido_lines_queue_url` | uma env var por fila (§4) | Não — cada serviço só declara as suas |

Falha de instanciação (`pydantic.ValidationError`) só quando falta um dos 4 campos de conexão ou
`processed_messages_table_name` — os demais são `Optional[str] = None`; cada serviço valida no
próprio `config.py` (constitution VIII) que as filas/tabelas/bucket que ele de fato usa estão
setadas.

## Função de mascaramento

`mask_document(document: str) -> str` — últimos 4 caracteres preservados, resto substituído por
`*`; `len(document) <= 4` → mascarado integralmente. Preserva o comprimento original.

## Parser posicional (§6)

| Registro | `record_type` | Tamanho fixo | Campos próprios |
|---|---|---|---|
| Header | `0` | 200 | `file_date`, `origin_system`, `sequence` |
| Detalhe — pedido | `1` | 200 | `operation`, `order_id`, `customer_id`, `customer_name`, `customer_document`, `item_count` |
| Detalhe — item | `2` | 200 | `product_id`, `quantity` |
| Trailer | `9` | 200 | `total_orders`, `total_items` |

Erros de domínio: `ArquivoInvalidoError` (header/trailer ausente, contadores divergentes),
`LinhaInvalidaError` (linha ≠200 chars, item órfão), `PedidoInvalidoError` (`item_count`
divergente da contagem real de itens daquele pedido).
