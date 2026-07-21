# Data Model: Lambda Line Processor

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## Entidades reaproveitadas (não redefinidas nesta feature)

`Settings`, `SqsClient` (`receive_raw_with_receipt`, já existente desde `007-file-consumer`),
`is_message_processed`, `mark_message_processed`, `get_logger`, `mask_document` — todos de
`pedidos_shared`. Este serviço **não** usa `MessageEnvelope` para consumir (research.md #4) e
**não** usa `Order`/`OrderItem`/`OrderStatus` — não escreve na tabela `orders` nem em nenhuma fila;
sua única saída é a chamada HTTP ao `api-gateway` (FR-010).

## Entidades próprias desta feature

### Mensagem de `pedido_lines_queue` (dict cru, sem dataclass própria)

| Campo | Tipo | Origem |
|---|---|---|
| `source_file` | `str` | contrato de `007-file-consumer` |
| `line_number` | `int` | idem |
| `operation` | `str` | `"SOLICITAR"` \| `"EDITAR"` \| `"CANCELAR"` (ou desconhecida, Edge Cases) |
| `raw_line` | `str` | idem |
| `order_id` | `str \| None` | idem — `None` só é válido para `SOLICITAR` |
| `parsed` | `dict` | corpo pronto pra chamada HTTP correspondente |

Sem dataclass própria: o handler acessa os campos diretamente via `dict` — não há transformação
de dado a fazer além de decidir método/path (research.md #3).

## `domain/` — contrato (função pura, sem I/O)

| Função/Classe | Papel |
|---|---|
| `class ComandoInvalidoError(Exception)` | `operation` desconhecida ou `order_id` ausente para `EDITAR`/`CANCELAR` — tratado no handler como rejeição de negócio permanente (FR-007) |
| `chamada_api.montar_chamada(body: dict) -> tuple[str, str, dict]` | `(método HTTP, path, corpo)` a partir de `operation`/`order_id`/`parsed` (research.md #3) |

## `adapters/` — contrato

| Função/Classe | Papel |
|---|---|
| `api_gateway_client.chamar(client: httpx.Client, method: str, path: str, body: dict) -> httpx.Response` | `httpx.Client` com timeout 5s e retry curto só para erro de conexão/timeout (research.md #1); devolve a `Response` mesmo para status `>= 400` — quem decide ack/no-ack é o handler |
| `worker_loop` | idêntico ao padrão raw de `007-file-consumer` (research.md #4): `is_message_processed`/`mark_message_processed` pelo `MessageId` nativo do SQS; falha técnica não marca nem confirma |

## Mapeamento mensagem consumida → chamada HTTP → decisão

| Fila consumida | Processamento (em ordem) | Saída |
|---|---|---|
| `pedido_lines_queue` | (1) `chamada_api.montar_chamada` — `ComandoInvalidoError` é rejeição de negócio permanente, log e retorno (FR-007); (2) `api_gateway_client.chamar` — erro de conexão/timeout após retries propaga como falha técnica (FR-008); (3) `status_code < 300` → sucesso (FR-005); `status_code` em `{400, 404, 409}` → rejeição de negócio permanente, log e retorno (FR-006); qualquer outro `status_code` → falha técnica, levanta exceção (FR-008) | chamada HTTP ao `api-gateway` (`POST /pedidos`, `PUT /pedidos/{order_id}` ou `POST /pedidos/{order_id}/cancelamento`) |
