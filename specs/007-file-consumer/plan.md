# Implementation Plan: File Consumer

**Branch**: `feature/007-file-consumer` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-file-consumer/spec.md`.

## Summary

Worker Python (`services/file-consumer/`) sem porta HTTP de negócio — consome
`s3_notifications_queue` (evento nativo do S3, não `MessageEnvelope`) e publica em
`pedido_lines_queue` (também fora do envelope comum, research.md #2). Busca o arquivo posicional
notificado no S3, faz o parse via `pedidos_shared.file_layout.parse_file` — redesenhado nesta
feature para tolerância parcial (research.md #1) — e publica uma mensagem por pedido válido.
Arquivo estruturalmente inválido (cabeçalho/rodapé ausente, contadores divergentes) é rejeitado
por inteiro sem publicar nada; linha ou pedido individualmente inválido é registrado em log e não
interrompe o processamento dos demais. Nunca escreve em `orders` nem chama o API Gateway — isso é
responsabilidade do Lambda Line Processor (fora do escopo). Idempotente pelo `MessageId` nativo do
SQS (research.md #3), já que a notificação do S3 não carrega um `message_id` de domínio.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `pedidos_shared` (S3/SQS/idempotência/logging/Settings/file_layout);
nenhuma dependência HTTP externa (diferente de `005-order-validator`) — toda a integração é
S3 + SQS via Ministack

**Storage**: bucket `pedidos-bucket` (leitura, via `S3Client.get_object`) e tabela
`processed_messages` (idempotência); nenhuma tabela própria; não escreve em `orders` (FR-009)

**Testing**: pytest; testes unitários para montagem de mensagem por operação, extração de
notificações S3 (incluindo descarte de `s3:TestEvent`) e orquestração do handler (arquivo
válido/inválido/parcialmente inválido, S3 e SQS mockados); teste de integração real contra
Ministack cobrindo upload real → notificação real → leitura → publicação real; testes do
`parse_file` tolerante ficam em `shared/pedidos_shared/tests/test_file_layout.py`, não duplicados

**Target Platform**: container Docker (Linux), local via Ministack

**Project Type**: worker assíncrono (um serviço do monorepo, `services/file-consumer/`, sem
interface HTTP de negócio)

**Performance Goals**: sem meta de latência numérica nesta spec — SC-001 exige corretude, não
velocidade

**Constraints**: nunca escreve em `orders` nem chama o API Gateway (FR-009); arquivo
estruturalmente inválido nunca publica mensagem (FR-003); linha/pedido individualmente inválido
nunca interrompe o restante do arquivo (FR-004/FR-005); falha técnica de S3 nunca gera resposta de
negócio (FR-007); idempotência obrigatória por `MessageId` nativo do SQS (FR-008, research.md #3);
`s3_notifications_queue`/`pedido_lines_queue` não usam `MessageEnvelope` (research.md #2)

**Scale/Scope**: consome 1 fila, publica em 0..N mensagens por notificação (uma por pedido válido
do arquivo, até 50 itens por pedido herdado do layout §6); um arquivo pode conter múltiplos pedidos

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution) | Status | Nota |
|---|---|---|
| I.1 Event-driven, sem HTTP entre serviços | PASS | Nenhuma chamada HTTP nesta feature — nem entre serviços, nem externa. Único I/O é S3 + SQS via Ministack. |
| I.2 Máquina de estados explícita | N/A nesta feature | File Consumer não é dono de nenhuma transição de status — não escreve em `orders`, não chama o API Gateway. |
| I.3 Idempotência obrigatória | PASS | `is_message_processed`/`mark_message_processed` pelo `MessageId` nativo do SQS (research.md #3) — mesmo padrão de checar antes/marcar depois já corrigido em `004-order-processor`. |
| I.4 Toda fila tem DLQ | N/A nesta feature | Filas e DLQs já criadas em `002-infraestrutura-local`; este serviço só consome/publica. |
| I.5 Falha é dado | PASS | Arquivo/linha/pedido inválido vira log estruturado (Clarifications) — nunca exceção silenciosa. Falha técnica (S3 indisponível) gera log estruturado e mensagem não confirmada (redrive nativo). |
| I.6 Local-first | PASS | S3 e SQS via Ministack, sem nenhuma dependência de rede externa. |
| II Stack obrigatória | PASS | Python 3.12, `pedidos_shared` (boto3/Pydantic v2), `ruff`, pytest. Nenhuma dependência nova fora da stack (research.md não introduz biblioteca externa). |
| III Contratos só em `shared/pedidos_shared` | PASS | Reaproveita `Settings`/`S3Client`/idempotência/logging/`file_layout.parse_file`. `SqsClient` ganha `send_raw`/`receive_raw_with_receipt` (extensão aditiva, não redefinição); `file_layout.parse_file` corrigido para bater com o contrato original de §6 (research.md #1), não uma reinvenção. |
| IV Sem infra hardcoded / logs JSON / type hints / `/health` | PASS | `Settings` de `pedidos_shared` pra fila/bucket/tabela; thread HTTP simples na porta 8083 servindo `/health` (8000/8080/8081/8082 já usados). |
| V Fluxo de trabalho com Git | PASS | Branch `feature/007-file-consumer` criada antes de qualquer código. |
| VII Code review obrigatório | PASS (guia a implementação) | Executar review (skill `code-review` ou `/review`) antes de abrir o PR. |
| VIII Design de código | PASS | `handlers/processar_notificacao.py` (único handler); `domain/mensagens.py` (função pura, sem I/O); `adapters/notificacoes_s3.py` (parsing do evento S3, puro) e `adapters/worker_loop.py` (I/O de fila); `config.py`; `main.py`. |
| IX Definição de pronto | PASS (guia a implementação) | Branch `feature/007-file-consumer`, testes unitários + integração contra Ministack, `docker-compose`, `ruff`, code review, README, PR. |

Nenhuma violação a justificar. A extensão de `pedidos_shared` (SqsClient, file_layout) é aditiva
ou corretiva (bugfix contra o contrato original já documentado), não uma nova camada ou dependência
— não exige entrada em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/007-file-consumer/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── file-consumer-messages.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
shared/pedidos_shared/
├── src/pedidos_shared/
│   ├── file_layout.py               # parse_file redesenhado: tolerância parcial (research.md #1)
│   └── clients/sqs.py               # + send_raw, + receive_raw_with_receipt (research.md #2)
└── tests/
    └── test_file_layout.py          # 3 testes reescritos + novo teste multi-pedido tolerante

services/file-consumer/
├── pyproject.toml
├── src/file_consumer/
│   ├── __init__.py
│   ├── main.py                      # composition root: 1 thread de consumo + thread /health (porta 8083)
│   ├── config.py                    # Settings de pedidos_shared (fila, bucket, tabela de idempotência)
│   ├── handlers/
│   │   └── processar_notificacao.py # consome s3_notifications_queue, orquestra domain+adapters (US1-US5)
│   ├── domain/
│   │   └── mensagens.py             # montar_linha_pedido(source_file, line_number, order, raw_line) (US1)
│   └── adapters/
│       ├── notificacoes_s3.py       # extrair_notificacoes(body) — Records[], descarta TestEvent (US1)
│       └── worker_loop.py           # loop raw (send_raw/receive_raw_with_receipt), idempotência por MessageId (US5)
└── tests/
    ├── conftest.py
    ├── test_mensagens.py
    ├── test_notificacoes_s3.py
    ├── test_processar_notificacao.py
    ├── test_worker_loop.py
    ├── test_health.py
    └── test_idempotencia.py
```

**Structure Decision**: serviço único em `services/file-consumer/`, mesma subdivisão
`handlers/`/`domain/`/`adapters/`/`config.py`/`main.py` das demais features de serviço. Diferente
de `005-order-validator`/`006-pdf-generator`, parte do trabalho desta feature vive em
`shared/pedidos_shared/` (correção de `file_layout.parse_file` e extensão de `SqsClient`) porque o
parsing do layout posicional e o envio/recebimento de mensagens são contratos compartilhados, não
específicos deste serviço — mesma regra da constitution III já seguida quando `S3Client.put_object`
ganhou `content_type` em `006-pdf-generator`.

## Complexity Tracking

*Vazio — nenhuma violação de constitution a justificar.*
