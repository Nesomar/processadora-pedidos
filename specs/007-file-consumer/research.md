# Research: File Consumer

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## 1. Tolerância parcial em `pedidos_shared.file_layout.parse_file` (decisão do usuário)

**Decision**: Redesenhar `parse_file` (feature `001-fundacao-compartilhada`, já mergeada) para
coletar erros de linha/pedido em vez de levantar exceção na primeira ocorrência. `ArquivoInvalidoError`
continua sendo levantada (arquivo inteiro rejeitado) apenas para: cabeçalho ausente/inválido,
rodapé ausente/inválido, ou contadores do rodapé (`total_orders`/`total_items`) divergentes da
contagem **bruta** de registros tipo `1`/`2` fisicamente encontrados no arquivo (independente de
serem depois aceitos ou rejeitados individualmente). `LinhaInvalidaError` (linha com tamanho
errado, item órfão, `record_type` desconhecido) e `PedidoInvalidoError` (`item_count` divergente)
deixam de ser levantadas — passam a ser instanciadas e acumuladas em `ParsedFile.errors: list[Exception]`,
e o parsing continua para as próximas linhas/pedidos. `ParsedFile.orders` só contém pedidos que
passaram em todas as checagens.

**Rationale**: `docs/01-dominio-e-contratos.md` §6 já documentava esse comportamento
("...linha rejeitada... processamento continua", "...pedido rejeitado (o pedido, não o arquivo)")
desde antes da implementação atual — a versão mergeada em `001-fundacao-compartilhada` não seguia
essa regra à risca (tratava tudo como fatal). Esta é a primeira feature que realmente consome
`parse_file` ponta a ponta, e US2/US3/FR-003/FR-004/FR-005 desta spec exigem o comportamento
correto. Corrigir na origem (shared) evita duplicar a lógica de parsing do layout posicional em
`file-consumer` (constitution III — contratos e parsing vivem só em `pedidos_shared`).

**Contagem bruta vs. contagem válida**: os contadores do rodapé são comparados contra quantos
registros tipo `1`/`2` foram **fisicamente encontrados** (pelo primeiro caractere da linha),
independente de item_count bater depois — não contra `len(orders)` (só os aceitos). Isso separa a
checagem estrutural do arquivo (o rodapé bate com o que existe fisicamente) da checagem de negócio
por pedido (item_count bate com os itens daquele pedido) — cada uma vira uma categoria de erro
diferente, como o §6 descreve como regras independentes.

**Alternatives considered**: `file-consumer` reimplementar o parsing tolerante por conta própria,
ignorando `parse_file` — rejeitado pelo usuário (duplicaria regras de layout já implementadas);
relaxar o spec para tratar qualquer erro de linha/pedido como arquivo inteiro inválido — rejeitado
pelo usuário (diverge do contrato documentado em §6).

**Testes afetados**: `shared/pedidos_shared/tests/test_file_layout.py` — 3 dos 7 testes existentes
precisam ser reescritos porque hoje esperam exceção onde o novo comportamento tolerante retorna
sucesso com erros coletados (`test_parse_file_rejects_line_with_wrong_length`,
`test_parse_file_rejects_orphan_item_record`, `test_parse_file_rejects_order_with_divergent_item_count`).
Novos testes cobrem um arquivo com múltiplos pedidos onde um é inválido e os demais continuam
sendo retornados em `ParsedFile.orders`.

## 2. Filas fora do envelope comum (`s3_notifications_queue`, `pedido_lines_queue`)

**Decision**: `s3_notifications_queue` carrega o evento nativo de notificação do S3 (schema AWS
padrão, `{"Records": [{"eventName": ..., "s3": {"bucket": {"name": ...}, "object": {"key": ...}}}]}`),
não um `MessageEnvelope`. `pedido_lines_queue` também não usa `MessageEnvelope` — carrega
diretamente o objeto de 6 campos (`source_file`, `line_number`, `operation`, `raw_line`, `order_id`,
`parsed`, ver research.md #5). Ambas as filas exigem métodos novos em `pedidos_shared.SqsClient`:
`receive_raw_with_receipt(queue_url) -> list[tuple[dict, str, str]]` (corpo JSON cru, receipt
handle, `MessageId` nativo do SQS) e `send_raw(queue_url, body: dict) -> str`.

**Rationale**: `MessageEnvelope.order_id` é obrigatório (`str`, não `str | None`), mas o layout do
arquivo diz explicitamente "`order_id`: UUID; espaços quando `SOLICITAR`" (§6) — ou seja, para um
pedido novo o `order_id` ainda não existe neste ponto do pipeline (só o API Gateway gera essa UUID,
e quem chama o API Gateway aqui é o Lambda Line Processor, fora do escopo). Forçar
`MessageEnvelope` exigiria inventar um `order_id` fictício, o que é pior do que simplesmente não
usar o envelope comum — que de qualquer forma já não é usado por `s3_notifications_queue` (evento
nativo do S3, produzido pelo próprio armazenamento, não por um serviço nosso).

**Alternatives considered**: gerar um `order_id` placeholder (ex.: UUID novo) só para satisfazer o
`MessageEnvelope` — rejeitado, criaria um identificador descartável sem significado, que poderia
ser confundido com um `order_id` real por quem consome a fila depois; usar `MessageEnvelope` com
`order_id=""` — rejeitado, viola a decisão de design de `Order.order_id` ser sempre um UUID v4
real.

## 3. Idempotência por `MessageId` nativo do SQS

**Decision**: como as mensagens de `s3_notifications_queue` não têm `message_id` de domínio,
`is_message_processed`/`mark_message_processed` (`pedidos_shared.idempotency`, já genéricos —
recebem `message_id: str` solto, não um `MessageEnvelope`) são chamados com o `MessageId` nativo
devolvido pelo próprio SQS na resposta de `receive_message`.

**Rationale**: FR-008. `is_message_processed`/`mark_message_processed` já não exigem um
`MessageEnvelope` — aceitam qualquer string como chave. O `MessageId` do SQS é único por
mensagem entregue (mesmo em reentregas do mesmo evento lógico, a AWS pode gerar um novo
`MessageId` em alguns cenários de redrive, mas dentro da mesma notificação original o `MessageId`
é estável entre tentativas de leitura/nack) — suficiente para o requisito de não duplicar
processamento da mesma entrega.

**Alternatives considered**: derivar uma chave de idempotência do próprio conteúdo do evento
(`bucket+key+eTag`) — mais robusto a reenvios genuinamente duplicados pelo S3, mas over-engineering
para o escopo desta feature; usar apenas `bucket+key` sem `eTag` arriscaria tratar um arquivo
reenviado com o mesmo nome (mas conteúdo diferente) como duplicata indevida.

## 4. Evento de notificação do S3: `TestEvent`, decodificação de `key`

**Decision**: ao configurar `PutBucketNotificationConfiguration`, o S3 (e o Ministack, confirmado
empiricamente) envia uma mensagem única de teste (`{"Service": "Amazon S3", "Event": "s3:TestEvent", ...}`,
sem a chave `"Records"`) para validar que a fila de destino existe. O adapter que interpreta o
corpo da mensagem detecta a ausência de `"Records"` e descarta a mensagem (ack, sem processar,
log informativo) em vez de tratá-la como notificação de arquivo malformada. Para cada
`Records[].s3.object.key` real, aplica `urllib.parse.unquote_plus` antes de usar como chave do
S3 (a AWS codifica a key em notificações reais; decodificar uma string já sem codificação é
no-op, então a chamada é sempre segura).

**Rationale**: confirmado rodando `docker compose up` + `make seed-file` localmente contra o
Ministack real — a mensagem de teste chega de fato na fila assim que a notificação é configurada
no bootstrap, antes de qualquer upload de arquivo. Sem esse tratamento, a primeira mensagem que o
worker consumir sempre seria essa notificação de teste, e tentar tratá-la como notificação de
arquivo geraria um erro técnico falso (campo `Records` ausente) a cada subida do ambiente.

**Alternatives considered**: nenhuma — comportamento observado do próprio Ministack, não uma
escolha de design.

## 5. Formato da mensagem publicada em `pedido_lines_queue`

**Decision**: `{"source_file": str, "line_number": int, "operation": str, "raw_line": str,
"order_id": str | None, "parsed": dict}`. `order_id` (adição sobre o exemplo ilustrativo de
`docs/01-dominio-e-contratos.md` §5) é o `ParsedOrder.order_id` bruto — `None` para `SOLICITAR`,
a UUID do arquivo para `EDITAR`/`CANCELAR`. `parsed` segue o formato de `solicitar_pedido_queue`/
`editar_pedido_queue` (`customer_id`, `customer_name`, `customer_document`, `channel="BATCH"`,
`items`, `source_file`, `source_line`) para `SOLICITAR`/`EDITAR`, ou o formato de
`cancelar_pedido_queue` (`{"reason": "Cancelamento via arquivo batch"}`, Clarifications) para
`CANCELAR` — itens parseados de um pedido `CANCELAR` são descartados ao montar `parsed` (spec.md
Assumptions).

**Rationale**: o Lambda Line Processor (fora do escopo) precisa saber a qual pedido uma linha
`EDITAR`/`CANCELAR` se refere para chamar o endpoint HTTP correto — essa informação só existe no
arquivo (`ParsedOrder.order_id`), não no `parsed` (que espelha o payload interno da fila
correspondente, sem `order_id` — o mesmo formato usado quando o `order_id` já viaja no
`MessageEnvelope` no caminho online). Como `pedido_lines_queue` não usa `MessageEnvelope`
(research.md #2), o `order_id` precisa aparecer em algum campo próprio da mensagem.

**Alternatives considered**: omitir `order_id` e deixar o Lambda Line Processor extraí-lo de dentro
de `parsed` — rejeitado, obrigaria `parsed` a ter um formato diferente do payload real das filas
online só para carregar essa informação, quebrando a promessa de "mesmo formato do payload de
solicitar_pedido" citada no contrato.

## 6. Estratégia de testes

**Decision**: testes unitários cobrindo `domain/mensagens.py` (montagem do `parsed` por operação),
o adapter de notificação S3 (extração de `Records`, descarte de `TestEvent`, decodificação de
`key`) e o handler orquestrando arquivo válido/inválido/parcialmente inválido (S3 e SQS mockados).
Um teste de integração real contra Ministack cobre o fluxo completo: upload real de um arquivo no
S3, notificação real entregue via `s3_notifications_queue`, leitura do arquivo, publicação real em
`pedido_lines_queue`. Testes de `parse_file` tolerante ficam em
`shared/pedidos_shared/tests/test_file_layout.py` (research.md #1), não duplicados aqui.

**Rationale**: mesma lógica das features anteriores — constitution IX exige ao menos um teste de
integração contra o Ministack; este serviço não tem nenhuma dependência de rede externa, então
toda a superfície de integração (S3 + SQS) já roda local.

**Alternatives considered**: nenhuma — consistente com o padrão já estabelecido em
`005-order-validator`/`006-pdf-generator`.
