# Implementation Plan: Order Validator

**Branch**: `feature/005-order-validator` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-order-validator/spec.md`.

## Summary

Worker Python (`services/order-validator/`) sem porta HTTP de negócio — consome
`validar_pedido_queue` e publica em `validar_pedido_response_queue`, ambas via `pedidos_shared`.
Valida documento do cliente (CPF/CNPJ, dígito verificador), consulta o catálogo externo
(dummyjson.com) por item pra checar existência/estoque/quantidade mínima, calcula preços e
totais, e reprova pedidos acima do limite de valor (R$ 100.000,00). Nunca escreve na tabela
`orders` — só produz a resposta que o Order Processor consome. Cache em memória com TTL de 5min
reduz chamadas repetidas ao catálogo. Idempotente via `is_message_processed`/
`mark_message_processed` de `pedidos_shared`, com a mesma correção de ordem (checar antes,
marcar só depois do sucesso) descoberta e corrigida na feature `004-order-processor`.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `pedidos_shared` (SQS/idempotência/logging/Settings); `httpx` (cliente
HTTP externo, único uso permitido de HTTP síncrono entre componentes — constitution I.1) com
timeout explícito e retry curto pra falhas de conexão transitórias, distinto do redrive nativo
do SQS

**Storage**: nenhuma tabela própria — não escreve em `orders` (FR-015); usa
`processed_messages` (idempotência, feature `001-fundacao-compartilhada`) só para dedup de
mensagem

**Testing**: pytest; testes unitários com catálogo externo mockado (rápidos, determinísticos,
sem depender de rede real); teste de integração contra Ministack real cobrindo o fluxo de fila
(SQS real, catálogo mockado); validação manual ao vivo contra a API real do dummyjson.com
documentada em `quickstart.md` (mesma abordagem de validação real usada em 003/004)

**Target Platform**: container Docker (Linux), local via Ministack

**Project Type**: worker assíncrono (um serviço do monorepo, `services/order-validator/`, sem
interface HTTP de negócio)

**Performance Goals**: sem meta de latência numérica nesta spec — SC-001/002 exigem corretude,
não velocidade; cache de 5min (FR-014) já cobre o principal ganho de performance esperado
(reduzir round-trips ao catálogo externo)

**Constraints**: nunca escreve em `orders` (FR-015, único escritor é o Order Processor); erro
técnico da API externa nunca gera resposta de validação (FR-012); erro de negócio nunca bloqueia
a fila (sempre confirma a mensagem); idempotência obrigatória (FR-013); limite de total fixo em
R$ 100.000,00 no código (não configurável nesta versão, ver spec.md Assumptions)

**Scale/Scope**: consome 1 fila, publica em 1 — volume dominado pelo volume de pedidos que
chegam à validação; até 50 itens por pedido (herdado do limite de `Order.items` em
`pedidos_shared`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution) | Status | Nota |
|---|---|---|
| I.1 Event-driven, sem HTTP entre serviços | PASS | Único HTTP de saída é a API externa de catálogo — exceção explícita da constitution. Nenhuma chamada a outro serviço interno. |
| I.2 Máquina de estados explícita | N/A nesta feature | Order Validator não é dono de nenhuma transição de status — só produz a resposta que o Order Processor usa pra aplicar `is_valid_transition`. |
| I.3 Idempotência obrigatória | PASS | `is_message_processed` (checa antes) / `mark_message_processed` (marca só após sucesso ou reprovação de negócio) — mesmo padrão corrigido em `004-order-processor`, aplicado aqui desde o início. |
| I.4 Toda fila tem DLQ | N/A nesta feature | Filas e DLQs já criadas em `002-infraestrutura-local`; este serviço só consome/publica. |
| I.5 Falha é dado | PASS | Reprovação de negócio (documento inválido, item reprovado, total excedido) vira `errors[]` na resposta — nunca exceção silenciosa. Falha técnica (timeout/5xx do catálogo) gera log estruturado e mensagem não confirmada (redrive nativo). |
| I.6 Local-first | PASS (com exceção documentada) | SQS via Ministack. A única saída de rede real é a API pública do catálogo (dummyjson.com) — a própria constitution II lista isso como dependência externa esperada, não uma violação de local-first. |
| II Stack obrigatória | PASS | Python 3.12, `pedidos_shared` (boto3/Pydantic v2), `httpx` (cliente HTTP externo com timeout+retry, mandado pela seção II), `ruff`, pytest. |
| III Contratos só em `shared/pedidos_shared` | PASS | Reaproveita `MessageEnvelope`/`Settings`/`SqsClient`/idempotência/logging. Nenhum contrato de mensagem redefinido — payload de `validar_pedido_queue`/`validar_pedido_response_queue` já documentado em `docs/01-dominio-e-contratos.md` §5. |
| IV Sem infra hardcoded / logs JSON / type hints / `/health` | PASS | `Settings` de `pedidos_shared` pra fila/tabela; URL base do catálogo externo por variável de ambiente (não hardcoded); thread HTTP simples na porta 8080 servindo `/health`. |
| VIII Design de código | PASS | `handlers/validar_pedido.py` (único handler); `domain/` com um módulo por regra (`documento.py`, `estoque.py`, `quantidade_minima.py`, `limite_total.py`, `calculo.py`, `mensagens.py`) — nomes literalmente sugeridos pela própria constitution VIII; `adapters/` (`catalogo_produtos.py` com cache TTL, `worker_loop.py`); `config.py`; `main.py`. |
| IX Definição de pronto | PASS (guia a implementação) | Branch `feature/005-order-validator`, testes unitários + integração contra Ministack, `docker-compose`, `ruff`, code review, README, PR. |

Nenhuma violação a justificar.

## Project Structure

### Documentation (this feature)

```text
specs/005-order-validator/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── order-validator-messages.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
services/order-validator/
├── pyproject.toml
├── src/order_validator/
│   ├── __init__.py
│   ├── main.py                          # composition root: 1 thread de consumo + thread /health
│   ├── config.py                        # Settings de pedidos_shared + URL base do catálogo externo
│   ├── handlers/
│   │   └── validar_pedido.py            # consome validar_pedido_queue, orquestra domain+adapters (US1-US6)
│   ├── domain/
│   │   ├── documento.py                 # validar_documento(document) — CPF/CNPJ dígito verificador (US2)
│   │   ├── estoque.py                   # validar_estoque(quantity, produto) — INSUFFICIENT_STOCK (US3)
│   │   ├── quantidade_minima.py         # validar_quantidade_minima(quantity, produto) — BELOW_MINIMUM_ORDER_QUANTITY (US3)
│   │   ├── limite_total.py              # validar_limite_total(total) — ORDER_TOTAL_EXCEEDS_LIMIT (US4)
│   │   ├── calculo.py                   # calcular_item / calcular_totais — puro, sem I/O (US1)
│   │   └── mensagens.py                 # montar_resposta_aprovada / montar_resposta_reprovada
│   └── adapters/
│       ├── catalogo_produtos.py         # httpx + cache TTL 5min; ProdutoNaoEncontradoError vs erro técnico (US5, US7)
│       └── worker_loop.py               # loop de consumo (idempotência check-antes/marca-depois, US8)
└── tests/
    ├── test_documento.py
    ├── test_estoque.py
    ├── test_quantidade_minima.py
    ├── test_limite_total.py
    ├── test_calculo.py
    ├── test_catalogo_produtos.py
    ├── test_validar_pedido.py
    ├── test_worker_loop.py
    ├── test_health.py
    └── test_idempotencia.py
```

**Structure Decision**: serviço único em `services/order-validator/`, mesma subdivisão
`handlers/`/`domain/`/`adapters/`/`config.py`/`main.py` das demais features de serviço (consistente
com `004-order-processor`). `domain/` não importa `httpx` nem `boto3` — cada regra é uma função
pura testável sem mock de rede (constitution VIII). `adapters/catalogo_produtos.py` isola o único
ponto de I/O de rede externo do sistema; `adapters/worker_loop.py` replica o padrão já corrigido
em `004-order-processor` (idempotência checada antes do handler, marcada só depois do sucesso ou
rejeição de negócio) desde a primeira versão, evitando reintroduzir o bug já corrigido lá.

## Complexity Tracking

*Vazio — nenhuma violação de constitution a justificar.*
