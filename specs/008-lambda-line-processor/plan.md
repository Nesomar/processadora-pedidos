# Implementation Plan: Lambda Line Processor

**Branch**: `feature/008-lambda-line-processor` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-lambda-line-processor/spec.md`.

## Summary

Worker Python (`services/lambda-line-processor/`) sem tabela própria — consome `pedido_lines_queue`
(sem `MessageEnvelope`, mesma decisão de `007-file-consumer`) e, para cada mensagem, chama o
endpoint HTTP correspondente do `api-gateway` já existente (`POST /pedidos`, `PUT
/pedidos/{order_id}` ou `POST /pedidos/{order_id}/cancelamento`), fechando o pipeline de entrada em
lote iniciado pelo File Consumer. Esta é a segunda exceção documentada ao princípio I.1 da
constitution (v1.0.2): o API Gateway é a porta de entrada HTTP única do sistema tanto pro fluxo
online quanto pro batch, e este serviço reaproveita essa porta em vez de duplicar geração de
`order_id` e validação de payload que só existem em `api_gateway/schemas.py`. Resposta `2xx`
confirma a mensagem; `400`/`404`/`409` é rejeição de negócio permanente (confirma sem retry);
qualquer outra falha (timeout, erro de conexão, `5xx`) é técnica e não confirma a mensagem.
Idempotente pelo `MessageId` nativo do SQS, reaproveitando o `worker_loop` raw de
`007-file-consumer` sem nenhuma mudança em `pedidos_shared`.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `pedidos_shared` (SQS/idempotência/logging/Settings); `httpx` (cliente
HTTP — segunda exceção documentada de HTTP síncrono, constitution I.1 v1.0.2) com timeout explícito
e retry curto, mesmo padrão de `005-order-validator`

**Storage**: nenhuma tabela ou bucket próprio; usa `processed_messages` (idempotência) só para
dedup de mensagem; nunca escreve em `orders` (FR-010, único escritor é o Order Processor)

**Testing**: pytest; testes unitários com `httpx` mockado cobrindo `domain/chamada_api.py` e o
handler (sucesso, recusa permanente, comando inválido, falha técnica); teste de integração real
contra Ministack **e** um `api-gateway` real (ambos no mesmo `docker-compose.yml`) — diferente de
`005-order-validator`, o alvo HTTP aqui é um serviço do próprio monorepo, não uma API externa, então
o teste automatizado bate nele de verdade (research.md #5)

**Target Platform**: container Docker (Linux), local via Ministack; "Lambda" descreve o papel
arquitetural (função de tradução sem estado, sem tabela própria — constitution VI já classifica
este serviço como variante "serverless" da skill de implementação), mas a execução local segue o
mesmo padrão de processo persistente + `/health` dos demais workers (spec.md Assumptions)

**Project Type**: worker assíncrono (um serviço do monorepo, `services/lambda-line-processor/`,
sem interface HTTP de negócio própria — só consome fila e chama HTTP de saída)

**Performance Goals**: sem meta de latência numérica nesta spec — SC-001 exige corretude, não
velocidade

**Constraints**: nunca escreve em `orders` nem publica em nenhuma fila (FR-010); `400`/`404`/`409`
do API Gateway nunca geram retry (FR-006); falha técnica nunca é tratada como recusa de negócio
(FR-008); idempotência obrigatória (FR-009); chamada ao `api-gateway` é a segunda exceção
documentada de HTTP síncrono em I.1 — nenhuma OUTRA chamada HTTP entre serviços de processamento é
introduzida por esta feature

**Scale/Scope**: consome 1 fila, produz 0 filas — 1 chamada HTTP de saída por mensagem

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution v1.0.2) | Status | Nota |
|---|---|---|
| I.1 Event-driven, nunca síncrono entre serviços de processamento | PASS (exceção documentada) | A chamada a `api-gateway` é a segunda exceção explícita de I.1 — o Lambda não é um serviço de processamento chamando outro, é o adaptador que fecha o pipeline batch reaproveitando a porta de entrada HTTP única do sistema. Nenhuma outra chamada HTTP entre serviços de processamento é introduzida. |
| I.2 Máquina de estados explícita | N/A nesta feature | Lambda Line Processor não é dono de nenhuma transição de status — o API Gateway já aplica `pode_editar`/`pode_cancelar` e o Order Processor aplica as transições reais. |
| I.3 Idempotência obrigatória | PASS | `is_message_processed`/`mark_message_processed` pelo `MessageId` nativo do SQS — mesmo padrão de `007-file-consumer`, reaproveitado sem mudança. |
| I.4 Toda fila tem DLQ | N/A nesta feature | `pedido_lines_queue`/DLQ já criadas em `002-infraestrutura-local`; este serviço só consome. |
| I.5 Falha é dado | PASS | Recusa de negócio (`400`/`404`/`409`, comando inválido) vira log estruturado — nunca exceção silenciosa. Falha técnica gera log estruturado e mensagem não confirmada (redrive nativo). |
| I.6 Local-first | PASS | SQS via Ministack; a chamada ao `api-gateway` é para um serviço do próprio ambiente local (container do mesmo `docker-compose.yml`), não uma dependência externa. |
| II Stack obrigatória | PASS | Python 3.12, `pedidos_shared`, `httpx` (cliente HTTP com timeout+retry, mandado pela seção II), `ruff`, pytest. |
| III Contratos só em `shared/pedidos_shared` | PASS | Reaproveita `Settings`/`SqsClient`/idempotência/logging sem nenhuma mudança nesta feature. `api_gateway_base_url` vive na subclasse local de `Settings` (mesmo padrão de `catalog_products_base_url` em `005-order-validator`), não no shared. |
| IV Sem infra hardcoded / logs JSON / type hints / `/health` | PASS | `Settings` de `pedidos_shared` pra fila/tabela; `API_GATEWAY_BASE_URL` por variável de ambiente; thread HTTP simples na porta 8084 servindo `/health`. |
| V Fluxo de trabalho com Git | PASS | Branch `feature/008-lambda-line-processor` criada antes de qualquer código. |
| VII Code review obrigatório | PASS (guia a implementação) | Executar review antes do PR, cobrindo os itens da seção VII (agora incluindo a checagem das duas exceções documentadas em I.1). |
| VIII Design de código | PASS | `handlers/processar_linha.py` (único handler); `domain/chamada_api.py` (função pura, mapeamento operação→chamada); `adapters/api_gateway_client.py` (único ponto de I/O HTTP) e `adapters/worker_loop.py` (I/O de fila); `config.py`; `main.py`. |
| IX Definição de pronto | PASS (guia a implementação) | Branch `feature/008-lambda-line-processor`, testes unitários + integração contra Ministack e `api-gateway` reais, `docker-compose`, `ruff`, code review, README, PR. |

Nenhuma violação a justificar além da exceção de I.1, já documentada na própria constitution
(v1.0.2) antes desta feature ser planejada.

## Project Structure

### Documentation (this feature)

```text
specs/008-lambda-line-processor/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── lambda-line-processor-calls.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
services/lambda-line-processor/
├── pyproject.toml
├── src/lambda_line_processor/
│   ├── __init__.py
│   ├── main.py                          # composition root: 1 thread de consumo + thread /health (porta 8084)
│   ├── config.py                        # LambdaLineProcessorSettings(Settings) + api_gateway_base_url
│   ├── handlers/
│   │   └── processar_linha.py           # consome pedido_lines_queue, orquestra domain+adapters (US1-US4)
│   ├── domain/
│   │   └── chamada_api.py               # montar_chamada(body) -> (method, path, body); ComandoInvalidoError (US1/US2)
│   └── adapters/
│       ├── api_gateway_client.py        # httpx.Client com timeout+retry (US1, US3)
│       └── worker_loop.py               # loop raw (send/receive já existentes), idempotência por MessageId (US4)
└── tests/
    ├── conftest.py
    ├── test_chamada_api.py
    ├── test_api_gateway_client.py
    ├── test_processar_linha.py
    ├── test_worker_loop.py
    ├── test_health.py
    └── test_idempotencia.py
```

**Structure Decision**: serviço único em `services/lambda-line-processor/`, mesma subdivisão
`handlers/`/`domain/`/`adapters/`/`config.py`/`main.py` das demais features de serviço. Diferente
de `007-file-consumer`, esta feature não precisa tocar `shared/pedidos_shared/` — toda a
infraestrutura raw (SQS sem envelope, idempotência por `MessageId` nativo) já existe. `domain/`
não importa `httpx` nem infraestrutura — `chamada_api.py` só decide método/path/corpo, função pura
testável sem mock de rede; `adapters/api_gateway_client.py` isola o único ponto de I/O HTTP de saída
deste serviço.

## Complexity Tracking

*Vazio — a única exceção de constitution (I.1, chamada ao `api-gateway`) já está documentada na
própria constitution (v1.0.2), não precisa ser rejustificada aqui.*
