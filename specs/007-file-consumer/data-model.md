# Data Model: File Consumer

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## Entidades reaproveitadas (não redefinidas nesta feature)

`Settings`, `S3Client`, `is_message_processed`, `mark_message_processed`, `get_logger`,
`mask_document` — todos de `pedidos_shared` (feature `001-fundacao-compartilhada`). Este serviço
**não** usa `MessageEnvelope` para consumir/publicar (research.md #2) e **não** usa `Order`,
`OrderItem` nem `OrderStatus`/`is_valid_transition` — não escreve na tabela `orders` e não chama o
API Gateway (FR-009).

## Entidades estendidas nesta feature (em `pedidos_shared`, research.md #1/#2)

### `pedidos_shared.file_layout.ParsedFile` — campo novo

| Campo | Tipo | Nota |
|---|---|---|
| `errors` | `list[Exception]` | novo — instâncias de `LinhaInvalidaError`/`PedidoInvalidoError` coletadas durante o parse tolerante (research.md #1); nunca contém `ArquivoInvalidoError` (essa continua sendo levantada, não coletada) |

`ParsedOrder`/`ParsedItem`/`ParsedFile` (demais campos) inalterados.

### `pedidos_shared.clients.sqs.SqsClient` — métodos novos

| Método | Papel |
|---|---|
| `send_raw(queue_url: str, body: dict) -> str` | publica um corpo JSON cru (sem `MessageEnvelope`); devolve o `MessageId` do SQS |
| `receive_raw_with_receipt(queue_url: str, max_messages: int = 10) -> list[tuple[dict, str, str]]` | devolve `(corpo_json, receipt_handle, message_id_nativo)` por mensagem, sem tentar validar contra `MessageEnvelope` |

## Entidades próprias desta feature

### `NotificacaoArquivo` (dataclass, saída de `adapters/notificacoes_s3.py`)

| Campo | Tipo | Origem |
|---|---|---|
| `bucket` | `str` | `Records[].s3.bucket.name` |
| `key` | `str` | `Records[].s3.object.key`, decodificada com `urllib.parse.unquote_plus` (research.md #4) |

### `ErroProcessamento` (dataclass, usada só para logging estruturado — não é persistida nem publicada)

| Campo | Tipo | Nota |
|---|---|---|
| `source_file` | `str` | nome do objeto no S3 |
| `line_number` | `int \| None` | `None` quando o erro é do arquivo inteiro (`ArquivoInvalidoError`) |
| `mensagem` | `str` | `str(exception)` — já inclui o número da linha quando aplicável (research.md #1) |

## Mapeamento notificação → processamento → mensagens publicadas

| Fila consumida | Processamento (em ordem) | Fila publicada |
|---|---|---|
| `s3_notifications_queue` | (1) descarta mensagens sem `Records` (`s3:TestEvent`, research.md #4); (2) para cada `Records[]`: extrai `NotificacaoArquivo`; (3) busca o conteúdo via `S3Client.get_object` — falha aqui é técnica (FR-007, sem publicar nada, sem ack); (4) `parse_file(linhas)` — `ArquivoInvalidoError` é capturada e tratada como rejeição de negócio do arquivo inteiro (US2, log estruturado, sem publicar nada, mensagem confirmada); (5) para cada erro em `ParsedFile.errors`: log estruturado (US3); (6) para cada `ParsedOrder` em `ParsedFile.orders`: monta e publica uma mensagem | `pedido_lines_queue` |

Payloads exatos: `contracts/file-consumer-messages.md` (espelha `docs/01-dominio-e-contratos.md`
§5/§6, com o campo `order_id` documentado como extensão — research.md #5).

## `domain/` — contrato (funções puras, sem I/O)

| Função | Papel |
|---|---|
| `mensagens.montar_linha_pedido(source_file: str, line_number: int, order: ParsedOrder, raw_line: str) -> dict` | monta a mensagem de `pedido_lines_queue`; para `operation="CANCELAR"`, `parsed={"reason": "Cancelamento via arquivo batch"}` (Clarifications), ignorando `order.items`; para `SOLICITAR`/`EDITAR`, `parsed` segue o formato de `solicitar_pedido_queue`/`editar_pedido_queue` com `channel="BATCH"` |

## `adapters/` — contrato

| Função/Classe | Papel |
|---|---|
| `notificacoes_s3.extrair_notificacoes(body: dict) -> list[NotificacaoArquivo]` | lista vazia se `body` não tiver `"Records"` (`s3:TestEvent` ou formato inesperado); senão um `NotificacaoArquivo` por `Records[]`, com `key` decodificada |
| `worker_loop` | variante do padrão de `004-order-processor`/`005-order-validator`/`006-pdf-generator` (research.md #3): usa `receive_raw_with_receipt`/`send_raw` em vez das variantes tipadas em `MessageEnvelope`; idempotência pelo `MessageId` nativo do SQS; `is_message_processed` antes do handler, `mark_message_processed` só depois de sucesso ou rejeição de negócio (arquivo/linha/pedido inválido); falha técnica (S3 indisponível) não marca nem confirma |
