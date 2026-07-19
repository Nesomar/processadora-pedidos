# Contrato: superfície pública de `pedidos_shared`

Não há HTTP nem CLI — o "contrato" é a API Python importada pelos demais serviços. Nomes e campos
espelham `docs/01-dominio-e-contratos.md`.

```
pedidos_shared/
├── models.py        # Order, OrderItem, MessageEnvelope
├── status.py         # OrderStatus (enum), is_valid_transition(current, next) -> bool
├── settings.py         # Settings (Pydantic BaseSettings)
├── idempotency.py        # mark_message_processed(message_id, consumer, settings) -> bool
├── masking.py               # mask_document(document: str) -> str
├── logging.py                 # get_logger(name: str) -> logging.Logger, JsonFormatter
├── file_layout.py               # parse_file(lines) -> ParsedFile; ArquivoInvalidoError,
│                                  # LinhaInvalidaError, PedidoInvalidoError
└── clients/
    ├── sqs.py                     # SqsClient(settings: Settings)
    ├── dynamodb.py                  # DynamoDbClient(settings: Settings)
    └── s3.py                          # S3Client(settings: Settings)
```

## Regras de contrato

1. **Nenhum serviço redefine** `Order`, `OrderItem`, `OrderStatus` ou `MessageEnvelope` localmente
   (FR-004) — sempre `from pedidos_shared import ...`.
2. **Mudança breaking** (remover/renomear campo obrigatório, remover valor do enum, mudar layout
   posicional) exige bump de versão do pacote no workspace `uv` e atualização coordenada de todos
   os serviços consumidores antes do merge.
3. **`is_valid_transition`** é a única função autorizada a decidir se uma transição de `status` é
   permitida; nenhuma escrita em `orders` acontece fora do Order Processor, e o Order Processor não
   reimplementa essa checagem localmente.
4. **`mark_message_processed`** MUST ser chamada por todo consumidor de fila antes de processar o
   corpo da mensagem (constitution I.3) — é a única fonte de verdade de idempotência do sistema.
5. Todo modelo de `models.py` que representa mensagem SQS **MUST** ser envelopado em
   `MessageEnvelope`, nunca enviado "cru".
6. `clients/*` **MUST** receber `Settings` por injeção de dependência (construtor) — nenhum cliente
   instancia `Settings()` internamente.
