# Implementation Plan: PDF Generator

**Branch**: `feature/006-pdf-generator` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-pdf-generator/spec.md`.

## Summary

Worker Python (`services/pdf-generator/`) sem porta HTTP de negócio — consome
`pdf_request_queue` e publica em `pdf_response_queue`, ambas via `pedidos_shared`. Gera a nota
fiscal em PDF (ReportLab) com os dados já calculados pelo pedido aprovado (cliente, itens,
totais — sem recalcular nada), grava o arquivo no S3 sob
`invoices/{ano}/{mes}/{dia}/{order_id}.pdf` e responde `success=true`/`s3_key`. Mensagens com
dados incompletos (sem itens, sem documento, sem nome) são reprovadas como erro de negócio
(`success=false`), sem retry. Falha técnica de armazenamento nunca gera resposta — a mensagem
volta pra fila via redrive nativo do SQS. Nunca escreve na tabela `orders`. Idempotente via
`is_message_processed`/`mark_message_processed` de `pedidos_shared`, reaproveitando o mesmo padrão
de `worker_loop` já usado (e corrigido) em `004-order-processor` e `005-order-validator`.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `pedidos_shared` (SQS/S3/idempotência/logging/Settings); `reportlab`
(geração de PDF, única biblioteca de PDF permitida pela constitution II)

**Storage**: bucket `pedidos-bucket` (S3 via Ministack) — único ponto de escrita deste serviço,
além da resposta em fila; nenhuma tabela própria; não escreve em `orders` (FR-008); usa
`processed_messages` (idempotência, feature `001-fundacao-compartilhada`) só para dedup de
mensagem

**Testing**: pytest; testes unitários para validação de solicitação, montagem de chave S3 e
renderização de PDF (sem mock de rede — nenhuma chamada HTTP externa nesta feature); teste de
integração contra Ministack real cobrindo o fluxo completo (SQS + S3 reais)

**Target Platform**: container Docker (Linux), local via Ministack

**Project Type**: worker assíncrono (um serviço do monorepo, `services/pdf-generator/`, sem
interface HTTP de negócio)

**Performance Goals**: sem meta de latência numérica nesta spec — SC-001/002 exigem corretude,
não velocidade; volume de PDFs gerados é dominado pelo volume de pedidos aprovados

**Constraints**: nunca escreve em `orders` (FR-008, único escritor é o Order Processor); dados
incompletos são falha de negócio permanente, nunca retry (FR-005); falha técnica de storage nunca
gera resposta de negócio (FR-006); idempotência obrigatória (FR-007); layout do PDF não é
recalculado a partir dos valores recebidos (FR-002)

**Scale/Scope**: consome 1 fila, publica em 1, escreve em 1 bucket — até 50 itens por pedido
(herdado do limite de `Order.items` em `pedidos_shared`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate (constitution) | Status | Nota |
|---|---|---|
| I.1 Event-driven, sem HTTP entre serviços | PASS | Nenhuma chamada HTTP nesta feature — nem entre serviços, nem externa (diferente do Order Validator, que tem a exceção do catálogo). Único I/O é SQS + S3 via Ministack. |
| I.2 Máquina de estados explícita | N/A nesta feature | PDF Generator não é dono de nenhuma transição de status — só produz a resposta que o Order Processor usa pra aplicar `aplicar_resposta_pdf`. |
| I.3 Idempotência obrigatória | PASS | `is_message_processed` (checa antes) / `mark_message_processed` (marca só após sucesso ou reprovação de negócio) — mesmo padrão corrigido em `004-order-processor`, aplicado aqui desde o início. |
| I.4 Toda fila tem DLQ | N/A nesta feature | Filas e DLQs já criadas em `002-infraestrutura-local`; este serviço só consome/publica. |
| I.5 Falha é dado | PASS | Dados incompletos (US2) viram `success=false`/`error_message` — nunca exceção silenciosa. Falha técnica (S3 indisponível) gera log estruturado e mensagem não confirmada (redrive nativo). |
| I.6 Local-first | PASS | SQS e S3 via Ministack, sem nenhuma dependência de rede externa — mais estrito que `005-order-validator` (que tem a exceção documentada do catálogo). |
| II Stack obrigatória | PASS | Python 3.12, `pedidos_shared` (boto3/Pydantic v2), `reportlab` (mandado pela seção II), `ruff`, pytest. |
| III Contratos só em `shared/pedidos_shared` | PASS | Reaproveita `MessageEnvelope`/`Settings`/`SqsClient`/`S3Client`/idempotência/logging. Nenhum contrato de mensagem redefinido — payload de `pdf_request_queue`/`pdf_response_queue` já documentado em `docs/01-dominio-e-contratos.md` §5. `S3Client.put_object` ganha um parâmetro opcional (`content_type`), não uma redefinição de contrato. |
| IV Sem infra hardcoded / logs JSON / type hints / `/health` | PASS | `Settings` de `pedidos_shared` pra fila/tabela/bucket; thread HTTP simples na porta 8082 servindo `/health` (8000/8080/8081 já usados por api-gateway/order-processor/order-validator). |
| V Fluxo de trabalho com Git | PASS | Branch `feature/006-pdf-generator` criada antes de qualquer código. |
| VII Code review obrigatório | PASS (guia a implementação) | Executar review (skill `code-review` ou `/review`) antes de abrir o PR, cobrindo os 6 itens da seção VII. |
| VIII Design de código | PASS | `handlers/gerar_pdf.py` (único handler); `domain/` com um módulo por responsabilidade (`validacao.py`, `chave_s3.py`, `renderizador.py`, `mensagens.py`) — todas funções puras, sem I/O de rede/disco; `adapters/` (`armazenamento.py` sobre `S3Client`, `worker_loop.py`); `config.py`; `main.py`. |
| IX Definição de pronto | PASS (guia a implementação) | Branch `feature/006-pdf-generator`, testes unitários + integração contra Ministack, `docker-compose`, `ruff`, code review, README, PR. |

Nenhuma violação a justificar.

## Project Structure

### Documentation (this feature)

```text
specs/006-pdf-generator/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── pdf-generator-messages.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
services/pdf-generator/
├── pyproject.toml
├── src/pdf_generator/
│   ├── __init__.py
│   ├── main.py                      # composition root: 1 thread de consumo + thread /health (porta 8082)
│   ├── config.py                    # Settings de pedidos_shared (fila, bucket, tabela de idempotência)
│   ├── handlers/
│   │   └── gerar_pdf.py             # consome pdf_request_queue, orquestra domain+adapters (US1-US4)
│   ├── domain/
│   │   ├── validacao.py             # validar_solicitacao(payload) — dados incompletos (US2)
│   │   ├── chave_s3.py              # montar_chave_invoice(order_id, momento) — puro (US1)
│   │   ├── renderizador.py          # renderizar_nota_fiscal(dados) -> bytes, ReportLab platypus (US1)
│   │   └── mensagens.py             # montar_resposta_sucesso / montar_resposta_falha
│   └── adapters/
│       ├── armazenamento.py         # salvar_pdf — wrapper sobre S3Client.put_object (US1, US3)
│       └── worker_loop.py           # loop de consumo (idempotência check-antes/marca-depois, US4)
└── tests/
    ├── test_validacao.py
    ├── test_chave_s3.py
    ├── test_renderizador.py
    ├── test_gerar_pdf.py
    ├── test_armazenamento.py
    ├── test_worker_loop.py
    ├── test_health.py
    └── test_idempotencia.py
```

**Structure Decision**: serviço único em `services/pdf-generator/`, mesma subdivisão
`handlers/`/`domain/`/`adapters/`/`config.py`/`main.py` das demais features de serviço (consistente
com `004-order-processor`/`005-order-validator`). `domain/` não importa `boto3` nem infraestrutura
— cada módulo é testável isoladamente; `renderizador.py` usa `reportlab` mas não faz I/O de
rede/disco (escreve em `io.BytesIO`), permanecendo puro no sentido da constitution VIII.
`adapters/armazenamento.py` isola o único ponto de escrita externa do serviço (S3);
`adapters/worker_loop.py` replica o padrão já corrigido em `004-order-processor` (idempotência
checada antes do handler, marcada só depois do sucesso ou reprovação de negócio).

## Complexity Tracking

*Vazio — nenhuma violação de constitution a justificar.*
