# Data Model: Observabilidade e Reprocessamento de DLQ

Nenhuma tabela, fila ou mensagem nova. Nenhuma escrita em `orders` ou `processed_messages`.

## Entidades (transientes, só em respostas HTTP)

- **DlqResumo**: `queue` (nome da fila de origem), `dlq` (`{queue}_dlq`), `messages` (int ≥ 0).
- **MensagemDlq**:
  - `message_id` — `MessageId` nativo do SQS (usado para reprocessar uma só mensagem)
  - `sent_at` — ISO 8601 UTC a partir de `SentTimestamp` (ou `null`)
  - `order_id`, `correlation_id` — envelope; senão `null`
  - `source_file`, `source_line` — arquivo/linha; senão `null`
  - `body` — corpo JSON com `customer_document` mascarado (texto truncado se não for JSON)
- **Reprocessamento**: `queue`, `reprocessed` (quantidade movida).

## Constante de domínio

`FILAS` (`domain/dlq.py`): as 9 filas de `docs/01-dominio-e-contratos.md` §4; DLQ de cada uma é
`{fila}_dlq`. Qualquer outro nome → 404.

## Regras

1. Listar: receber com 1 s e liberar (`release`) na hora; resultado deduplicado por `MessageId`, no máximo `limit`.
2. Reprocessar: `send` na origem → `delete` na DLQ, nessa ordem, por mensagem.
3. Mascarar: toda chave `customer_document` em qualquer nível do JSON passa por `mask_document`.
4. `identificar` nunca levanta: corpo desconhecido → campos de identificação nulos.

## Mudanças em `SqsClient` (shared)

| Método | Papel |
|---|---|
| `queue_url(name)` | `get_queue_url`; `QueueDoesNotExist` propaga |
| `message_count(url)` | visíveis + em voo + atrasadas |
| `peek(url, max_messages)` | recebe com 1 s e libera na hora, devolve mensagens cruas (`MessageId`, `Body`, `SentTimestamp`) |
| `receive_raw_messages(url, max_messages)` | recebe com visibilidade padrão, devolvendo `MessageId`, `Body`, `ReceiptHandle` |
| `send_body(url, body: str)` | reenvia o corpo exato |
| `delete(url, receipt)` | já existe |
