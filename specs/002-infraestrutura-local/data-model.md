# Data Model: Infraestrutura Local (Ministack)

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

Todo nome/config abaixo é copiado de `docs/01-dominio-e-contratos.md` §3, §4, §7, §8.

## Filas SQS (9 + suas DLQs)

| Fila | Produtor | Consumidor |
|---|---|---|
| `solicitar_pedido_queue` | API Gateway | Order Processor |
| `editar_pedido_queue` | API Gateway | Order Processor |
| `cancelar_pedido_queue` | API Gateway | Order Processor |
| `validar_pedido_queue` | Order Processor | Order Validator |
| `validar_pedido_response_queue` | Order Validator | Order Processor |
| `pdf_request_queue` | Order Processor | PDF Generator |
| `pdf_response_queue` | PDF Generator | Order Processor |
| `s3_notifications_queue` | S3 (event notification) | File Consumer |
| `pedido_lines_queue` | File Consumer | Lambda Line Processor |

Todas: `visibility_timeout = 60s`, `message_retention = 4 dias`, DLQ `{nome}_dlq`,
`maxReceiveCount = 3`.

## Tabela `orders`

| Atributo | Papel |
|---|---|
| `PK` = `ORDER#{order_id}` | partition key |
| `SK` = `METADATA` | sort key |
| `GSI1PK` = `CUSTOMER#{customer_id}`, `GSI1SK` = `{created_at}#{order_id}` | consulta por cliente |
| `GSI2PK` = `STATUS#{status}`, `GSI2SK` = `{created_at}#{order_id}` | consulta por status |

## Tabela `processed_messages`

| Atributo | Papel |
|---|---|
| `PK` = `MSG#{message_id}` | partition key |
| `consumer`, `processed_at` | metadados |
| `ttl` | TTL nativo, expiração em 7 dias |

## Bucket `pedidos-bucket`

- Prefixo `uploads/` — arquivos posicionais enviados; evento `s3:ObjectCreated:*` (prefixo
  `uploads/`, sufixo `.txt`) → `s3_notifications_queue`.
- Prefixo `invoices/YYYY/MM/DD/{order_id}.pdf` — notas fiscais geradas.

## Fonte única de nomes (`.env.example`, raiz do repo)

| Variável | Valor de exemplo | Consumida por |
|---|---|---|
| `AWS_ENDPOINT_URL` | `http://localhost:4566` | bootstrap, `Settings` |
| `AWS_REGION` | `us-east-1` | bootstrap, `Settings` |
| `AWS_ACCESS_KEY_ID` | `test` | bootstrap, `Settings` |
| `AWS_SECRET_ACCESS_KEY` | `test` | bootstrap, `Settings` |
| `ORDERS_TABLE_NAME` | `orders` | bootstrap, `Settings` |
| `PROCESSED_MESSAGES_TABLE_NAME` | `processed_messages` | bootstrap, `Settings` |
| `PEDIDOS_BUCKET_NAME` | `pedidos-bucket` | bootstrap, `Settings` |
| `SOLICITAR_PEDIDO_QUEUE_URL` … `PEDIDO_LINES_QUEUE_URL` (9 variáveis, uma por fila) | `http://localhost:4566/000000000000/{fila}` | bootstrap, `Settings` |

## Estado de execução do bootstrap

Nenhum estado próprio persistido — idempotência obtida checando o estado real do Ministack a cada
execução (research.md #3, #5).
