# Data Model: Infraestrutura Local (Ministack)

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

Não há entidade de domínio (Pedido, etc.) nesta feature — o "modelo de dados" aqui é o conjunto de
recursos de infraestrutura que o bootstrap cria e sua fonte de nomes.

## Recursos criados pelo bootstrap (versão inicial — ver Assumptions em spec.md)

| Recurso | Nome (env var) | Configuração |
|---|---|---|
| Fila SQS (exemplo, usada pelo teste de integração de `pedidos_shared`) | `PEDIDO_SOLICITADO_QUEUE_URL` (nome base: `pedido-solicitado`) | DLQ associada `pedido-solicitado-dlq`, redrive policy `maxReceiveCount = 3` |
| DLQ da fila acima | `pedido-solicitado-dlq` (sem env var própria — resolvida via redrive policy da fila principal) | Sem redrive policy própria (fila terminal) |
| Tabela DynamoDB de pedidos | `ORDERS_TABLE_NAME` (valor: `orders`) | Chave primária `order_id` (string) |
| Bucket S3 de PDFs | `ORDERS_BUCKET_NAME` (valor: `orders-pdf`) | Sem versionamento (fora de escopo desta feature) |

## Fonte única de nomes

`.env.example` (raiz do repo) — ver research.md #2. Campos:

| Variável | Exemplo de valor | Consumida por |
|---|---|---|
| `MINISTACK_ENDPOINT_URL` | `http://localhost:4566` | bootstrap, `Settings` de todo serviço |
| `AWS_REGION` | `us-east-1` | bootstrap, `Settings` de todo serviço |
| `ORDERS_TABLE_NAME` | `orders` | bootstrap, `Settings` |
| `ORDERS_BUCKET_NAME` | `orders-pdf` | bootstrap, `Settings` |
| `PEDIDO_SOLICITADO_QUEUE_URL` | `http://localhost:4566/000000000000/pedido-solicitado` | bootstrap, `Settings` |

## Estado de execução do bootstrap

Não há estado persistido pelo próprio bootstrap (nenhum "banco de controle de execuções") — a
idempotência (research.md #3) é obtida checando o estado real do Ministack a cada execução, não um
registro próprio de "já rodei antes".
