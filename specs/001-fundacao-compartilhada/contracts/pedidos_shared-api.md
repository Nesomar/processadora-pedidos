# Contrato: superfície pública de `pedidos_shared`

Este pacote não expõe HTTP nem CLI — o "contrato" é a API Python que os demais serviços importam.
Qualquer mudança nesta superfície é uma mudança de contrato entre serviços (constitution III).

```
pedidos_shared/
├── models.py       # Pedido, ItemPedido, PedidoSolicitado, PedidoParaValidar, PedidoValidado,
│                    # PedidoRejeitado, PedidoParaGerarPdf, PdfGerado
├── status.py        # StatusPedido (enum), is_valid_transition(current, next) -> bool
├── settings.py       # Settings (Pydantic BaseSettings)
├── masking.py         # mask_document(document: str) -> str
├── logging.py          # get_logger(name: str) -> logging.Logger, JsonFormatter
├── parsing.py           # FieldSpec, parse_fixed_width(line, layout) -> dict[str, str],
│                          # LinhaCurtaError
└── clients/
    ├── sqs.py            # SqsClient(settings: Settings)
    ├── dynamodb.py        # DynamoDbClient(settings: Settings)
    └── s3.py               # S3Client(settings: Settings)
```

## Regras de contrato

1. **Nenhum serviço redefine** `StatusPedido`, `Settings` ou qualquer modelo de `models.py`
   localmente (FR-003) — sempre `from pedidos_shared import ...`.
2. **Mudança breaking** (remover/renomear campo obrigatório, remover valor do enum) exige bump de
   versão do pacote no workspace `uv` e atualização coordenada de todos os serviços consumidores
   antes do merge — não há tolerância a schema divergente entre serviços (constitution I.1/III).
3. **`is_valid_transition`** é a única função autorizada a decidir se uma transição de `status` é
   permitida; nenhum serviço reimplementa essa checagem localmente (constitution VIII, regra
   "nenhuma escrita em orders fora do Order Processor" depende de uma fonte única de verdade sobre
   transições válidas).
4. Todo modelo de `models.py` que representa mensagem SQS **MUST** incluir `correlation_id: str`.
5. `clients/*` **MUST** receber `Settings` por injeção de dependência (construtor) — nenhum cliente
   instancia `Settings()` internamente (constitution VIII: DI explícita, sem singleton global).
