# Implementation Plan: Suite de Testes End-to-End

**Branch**: `feature/009-e2e-tests` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-e2e-tests/spec.md`.

## Summary

Suíte de testes de sistema em `tests/e2e/` (sem `pyproject.toml` próprio — não é membro do
workspace uv) que valida o pipeline inteiro rodando de verdade via `docker-compose` (Ministack + os
6 serviços), sem mockar nada, incluindo a chamada real ao catálogo externo. Cobre 5 cenários: fluxo
online até `COMPLETED` (US1), rejeição de negócio até `REJECTED` (US2), fluxo batch até um pedido
criado (US3), edição (US4) e cancelamento (US5). Cada cenário entra pelo mesmo ponto de entrada que
um usuário real usaria (HTTP do API Gateway ou upload de arquivo no armazenamento) e espera o
processamento assíncrono via poll curto com timeout. Uma checagem prévia de ambiente falha a suíte
inteira em segundos se qualquer um dos 6 `/health` estiver inacessível, em vez de deixar cada
cenário estourar seu próprio timeout. Executável via `make e2e` (alvo já existente no `Makefile`).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `pedidos_shared` (`S3Client`, `Settings` — só para o upload do cenário
batch, FR-007); `httpx` (cliente HTTP pro API Gateway, já presente no ambiente compartilhado via
`order-validator`/`lambda-line-processor`); pytest

**Storage**: nenhuma — a suíte não lê DynamoDB nem filas diretamente (FR-007), só observa efeitos
pelos endpoints HTTP do API Gateway e por um upload real no bucket

**Testing**: a própria feature É a suíte de testes — não há "testes dos testes"; cada cenário é
validado rodando-o de fato contra o ambiente completo (`quickstart.md`)

**Target Platform**: executado do host (ou de dentro de CI), contra os containers do
`docker-compose.yml` já no ar — não roda dentro de um container próprio

**Project Type**: suíte de testes de sistema, distinta dos testes de integração por serviço já
existentes em cada `services/*/tests/`

**Performance Goals**: cada cenário conclui em até 30s (poll interno), teto de 60s por cenário
(SC-002); checagem de ambiente fora do ar falha em segundos (SC-004)

**Constraints**: nunca escreve em tabela ou fila diretamente (FR-007); identificadores únicos por
execução para não colidir entre execuções repetidas (FR-004, SC-003); não sobe nem derruba o
ambiente sozinha (Assumptions — `make up`/`make down` continuam separados de `make e2e`)

**Scale/Scope**: 5 cenários de sistema, um arquivo de teste por cenário, mais utilitários
compartilhados (`conftest.py`, `_poll.py`, `_file_builder.py`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution v1.0.2) | Status | Nota |
|---|---|---|
| I.1 Event-driven, nunca síncrono entre serviços de processamento | N/A nesta feature | A suíte não é um serviço de processamento — é um cliente externo de teste, entrando pelos mesmos pontos de entrada (HTTP, upload de arquivo) que um usuário real usaria. Não introduz nenhuma chamada síncrona nova entre serviços do sistema. |
| I.2 Máquina de estados explícita | N/A nesta feature | A suíte só observa transições já aplicadas pelo Order Processor, nunca as aplica. |
| I.3 Idempotência obrigatória | N/A nesta feature | A suíte não é um consumidor de fila. |
| I.4 Toda fila tem DLQ | N/A nesta feature | Nenhuma fila nova. |
| I.5 Falha é dado | PASS | Timeout de cenário levanta `AssertionError` com contexto (FR-006) — nunca falha silenciosa. |
| I.6 Local-first | PASS | Roda 100% contra o ambiente local via Ministack; a única chamada de rede real fora do localhost é a mesma exceção já documentada em I.1 (catálogo externo), indiretamente exercida pelo Order Validator durante o pipeline. |
| II Stack obrigatória | PASS | Python 3.12, `pedidos_shared`, `httpx`, pytest — nenhuma dependência nova fora da stack. |
| III Contratos só em `shared/pedidos_shared` | PASS | Reaproveita `S3Client`/`Settings` sem modificação; não redefine nenhum contrato de mensagem. |
| IV Sem infra hardcoded / logs JSON / type hints / `/health` | PASS (parcial, N/A pro `/health` próprio) | Portas dos 6 serviços já fixas e documentadas; a suíte em si não é um serviço, não expõe `/health` próprio. |
| V Fluxo de trabalho com Git | PASS | Branch `feature/009-e2e-tests` criada a partir de `develop` antes de qualquer código. |
| VII Code review obrigatório | PASS (guia a implementação) | Executar review antes do PR. |
| VIII Design de código | PASS | Um arquivo de teste por cenário (US1-US5), utilitários (`_poll.py`, `_file_builder.py`) isolados por responsabilidade, `conftest.py` só com fixtures compartilhadas. |
| IX Definição de pronto | PASS (adaptado) | Esta feature *é* a suíte de teste de integração/sistema exigida pela seção IX — não precisa de "testes dos testes"; critério de pronto é `make e2e` passar consistentemente (SC-001/SC-003). |

Nenhuma violação a justificar.

## Project Structure

### Documentation (this feature)

```text
specs/009-e2e-tests/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks — NOT created here)
```

Sem `contracts/` — esta feature consome contratos já existentes e documentados, não introduz
nenhuma interface nova (research.md #6).

### Source Code (repository root)

```text
tests/e2e/
├── conftest.py               # checagem de ambiente (autouse), fixtures api_gateway/s3_client/settings
├── _poll.py                  # poll_until(fn, timeout, interval, description)
├── _file_builder.py          # montar_arquivo_valido(customer_id, product_id, quantity)
├── test_online_happy_path.py       # US1
├── test_business_rejection.py      # US2
├── test_batch_happy_path.py        # US3
├── test_editar_pedido.py           # US4
└── test_cancelar_pedido.py         # US5
```

**Structure Decision**: `tests/e2e/` na raiz, exatamente como já previsto na constitution III e no
`Makefile` — sem `pyproject.toml` próprio (research.md #1). Módulos utilitários com underscore
(`_poll.py`, `_file_builder.py`) para deixar claro que não são arquivos de teste (pytest não os
coleta) e para não colidirem com nomes de módulos de outros pacotes do workspace.

## Complexity Tracking

*Vazio — nenhuma violação de constitution a justificar.*
