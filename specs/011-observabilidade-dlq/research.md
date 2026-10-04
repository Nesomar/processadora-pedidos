# Research: Observabilidade e Reprocessamento de DLQ

## 1. Descobrir as URLs das DLQs

- **Decision**: resolver por nome com `get_queue_url(QueueName=f"{fila}_dlq")` e `{fila}` para a de
  origem; lista fechada das 9 filas em `domain/dlq.py`.
- **Rationale**: o gateway só exige 3 URLs de fila em `Settings`; resolver por nome evita 12
  variáveis novas e segue a convenção `{nome}_dlq` já garantida pelo bootstrap. `QueueDoesNotExist`
  vira 404 só para nomes fora da lista; fila da lista ausente é erro técnico (502).
- **Alternatives**: uma env por DLQ (poluiria `.env`/compose sem ganho); `list_queues` com prefixo
  (aceitaria filas arbitrárias).

## 2. Contagem

- **Decision**: `ApproximateNumberOfMessages` + `ApproximateNumberOfMessagesNotVisible` (+
  `Delayed`).
- **Rationale**: mensagem recém-recebida por alguém fica "not visible"; somar evita subcontar
  durante um reprocessamento ou inspeção.
- **Risco**: contagens são aproximadas por natureza no SQS; confirmar no Ministack em teste de
  integração e ajustar o teste (não o contrato) se for eventual.

## 3. Listar sem consumir

- **Decision**: `receive_message(VisibilityTimeout=1, AttributeNames=["SentTimestamp"])` seguido de `change_message_visibility(0)` em cada mensagem, em até 5
  rodadas, deduplicando por `MessageId`, até `limit` (padrão 10, máx 50).
- **Rationale**: receber e liberar na hora devolve a mensagem à fila imediatamente, então listar duas
  vezes seguidas dá o mesmo resultado (FR-003). Cada receive devolve um subconjunto arbitrário (até
  10), por isso as rodadas e a deduplicação. DLQ não tem redrive próprio, então o `ReceiveCount`
  incrementado não causa efeito.
- **Ministack**: `VisibilityTimeout=0` direto no `receive_message` é tratado como o padrão (60 s) e esconde a mensagem (verificado na implementação); `=1` mais `change_message_visibility(0)` funciona no Ministack e na AWS real.
- **Ordem de entrega** (verificado no Ministack): a fila entrega em ordem de chegada. Se a varredura liberasse cada mensagem logo após vê-la, toda rodada releria as mesmas 10 e o resto da DLQ ficaria inalcançável. Por isso `peek` mantém as mensagens vistas escondidas (30 s) durante a varredura e libera todas no fim; o reprocessamento por `message_id` faz o mesmo (`recebidas` − `apagadas` liberadas no `finally`).
- **Resposta**: `has_more` é `true` quando a contagem excede o devolvido.

## 4. Reprocessar: ordem e atomicidade

- **Decision**: para cada mensagem, `send_message` na fila de origem **e só então**
  `delete_message` na DLQ; repetir lotes de 10 até a DLQ esvaziar ou 20 rodadas sem progresso.
  Por `message_id`: receber em rodadas até achar o `MessageId`; se não achar, 404.
- **Rationale**: FR-007. Falha entre enviar e deletar deixa a mensagem duplicada (na origem e na
  DLQ), nunca perdida — aceitável porque os consumidores são idempotentes por `message_id`
  (constitution I.3). Concorrência (edge case): mensagens recebidas ficam invisíveis por
  `VisibilityTimeout` (60 s), então dois operadores não movem a mesma mensagem.
- **Corpo**: reenviado exatamente como está (`MessageBody` cru), preservando `message_id` do
  envelope; para as duas filas fora do envelope também (S3 event / linha), sem reinterpretar.
- **Receipt handle**: usar o da própria rodada de recebimento (visibilidade padrão), nunca o de uma
  listagem anterior.

## 5. Identificar a mensagem

- **Decision**: função pura `identificar(body: dict)`:
  - envelope (`order_id` + `correlation_id` no topo) → `order_id`, `correlation_id`;
  - evento S3 (`Records[0].s3.object.key`) → `source_file`;
  - linha de lote (`source_file` + `line_number`) → `source_file`, `source_line`;
  - corpo ilegível/desconhecido → todos os campos nulos, corpo ainda devolvido.
- **Rationale**: cobre as 9 filas e o edge case de pedido inexistente; nunca falha por corpo
  inesperado.

## 6. Máscara

- **Decision**: percorrer o JSON recursivamente e aplicar `mask_document` a toda chave
  `customer_document`; corpo não-JSON é devolvido como texto sem alteração (não contém campos
  estruturados a mascarar) — mas truncado a 2 000 caracteres.
- **Rationale**: FR-004 sem conhecer o formato de cada fila; o `parsed` da `pedido_lines_queue` e o
  `payload` do envelope usam o mesmo nome de campo.
- **Alternatives**: whitelist de campos devolvidos (perderia o conteúdo exigido por FR-002).

## 7. Rotas e nomes

- **Decision**: `/dlqs`, `/dlqs/{fila}/mensagens`, `/dlqs/{fila}/reprocessamento`, onde `{fila}` é
  o nome da fila **de origem** (ex.: `validar_pedido_queue`).
- **Rationale**: o operador pensa na fila do pipeline; a DLQ é derivada. `reprocessamento` espelha
  `/pedidos/{id}/cancelamento`. Corpo opcional `{"message_id": "..."}` no POST.

## 8. Autenticação

- **Decision**: nenhuma (clarificação 1). Documentar o risco no README e em `quickstart.md`.
