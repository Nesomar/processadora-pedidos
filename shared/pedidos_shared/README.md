# pedidos_shared

Biblioteca Python compartilhada do Sistema de Processamento de Pedidos: contratos de mensagem,
máquina de estados, clientes de infraestrutura (SQS/DynamoDB/S3), idempotência, logging
estruturado, mascaramento de documento e o parser do layout posicional. Nomes, estados e formatos
espelham literalmente `docs/01-dominio-e-contratos.md` — nenhuma invenção nesta biblioteca.

## Instalação (workspace uv)

```bash
uv sync --package pedidos-shared
```

## Variáveis de ambiente (`Settings`)

| Variável | Obrigatória | Default |
|---|---|---|
| `AWS_ENDPOINT_URL` | Sim | — |
| `AWS_REGION` | Sim | — |
| `AWS_ACCESS_KEY_ID` | Sim | — |
| `AWS_SECRET_ACCESS_KEY` | Sim | — |
| `PROCESSED_MESSAGES_TABLE_NAME` | Sim | — |
| `ORDERS_TABLE_NAME` | Não | `orders` |
| `PEDIDOS_BUCKET_NAME` | Não | `pedidos-bucket` |
| `SOLICITAR_PEDIDO_QUEUE_URL` | Não | `None` |
| `EDITAR_PEDIDO_QUEUE_URL` | Não | `None` |
| `CANCELAR_PEDIDO_QUEUE_URL` | Não | `None` |
| `VALIDAR_PEDIDO_QUEUE_URL` | Não | `None` |
| `VALIDAR_PEDIDO_RESPONSE_QUEUE_URL` | Não | `None` |
| `PDF_REQUEST_QUEUE_URL` | Não | `None` |
| `PDF_RESPONSE_QUEUE_URL` | Não | `None` |
| `S3_NOTIFICATIONS_QUEUE_URL` | Não | `None` |
| `PEDIDO_LINES_QUEUE_URL` | Não | `None` |

Cada serviço só precisa declarar as filas que de fato consome/produz.

## Contrato de mensagens exposto

```
pedidos_shared/
├── models.py        # Order, OrderItem, MessageEnvelope
├── status.py         # OrderStatus (enum), is_valid_transition(current, next) -> bool
├── settings.py         # Settings (pydantic-settings)
├── idempotency.py        # mark_message_processed(message_id, consumer, settings) -> bool
├── masking.py               # mask_document(document: str) -> str
├── logging.py                 # get_logger(name: str) -> logging.Logger, JsonFormatter
├── file_layout.py               # parse_file(lines) -> ParsedFile; ArquivoInvalidoError,
│                                  # LinhaInvalidaError, PedidoInvalidoError
└── clients/
    ├── sqs.py                     # SqsClient(settings)
    ├── dynamodb.py                  # DynamoDbClient(settings)
    └── s3.py                          # S3Client(settings)
```

Regras completas em [`specs/001-fundacao-compartilhada/contracts/pedidos_shared-api.md`](../../specs/001-fundacao-compartilhada/contracts/pedidos_shared-api.md).

**`Order.customer_document` MUST passar por `mask_document` antes de qualquer log** —
nunca logar o documento em claro.

## Testes

```bash
# unitários (não requerem Ministack)
uv run --package pedidos-shared pytest shared/pedidos_shared/tests -v

# lint/format
uv run --package pedidos-shared ruff check shared/pedidos_shared
uv run --package pedidos-shared ruff format --check shared/pedidos_shared
```

O teste de integração de `SqsClient` (`tests/clients/test_sqs.py`) é pulado automaticamente
quando o Ministack local (`002-infraestrutura-local`) não está rodando.
