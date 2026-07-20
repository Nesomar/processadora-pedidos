# Quickstart: file-consumer

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **Contrato**: [contracts/file-consumer-messages.md](./contracts/file-consumer-messages.md)

## Pré-requisitos

- Python 3.12, `uv` instalado
- Ministack rodando com os recursos já criados (`docker compose -f infra/docker-compose.yml up -d`)
- Sem dependência de rede externa — todo o fluxo (S3 + SQS) roda local via Ministack

## Setup

```bash
uv sync --package file-consumer
```

## Testes unitários e de integração (Ministack real)

```bash
uv run --package file-consumer pytest services/file-consumer/tests -v
uv run --package pedidos-shared pytest shared/pedidos_shared/tests/test_file_layout.py -v
```

## Subir o worker localmente

```bash
source .env
uv run --package file-consumer python -m file_consumer.main
```

**Esperado**: `GET http://localhost:8083/health` responde `{"status":"ok"}`; log estruturado
confirma o consumidor de `s3_notifications_queue` iniciado. Uma mensagem `s3:TestEvent` pode
aparecer nos logs como descartada — comportamento esperado (research.md #4).

## Validar US1 — arquivo válido processado linha a linha (SC-001)

```bash
uv run --package infra-bootstrap python infra/bootstrap/seed_file.py
```

**Esperado**: em segundos, uma mensagem aparece em `pedido_lines_queue` com `operation="SOLICITAR"`,
`source_file` igual ao nome gerado pelo seed, `parsed.channel="BATCH"` e os dados do cliente/itens
do arquivo de exemplo.

## Validar US2 — arquivo inteiro inválido (SC-002)

Fazer upload manual de um arquivo `.txt` em `uploads/` sem registro de rodapé (ex.: usando
`aws s3 cp` ou um script Python com `boto3` apontando pro Ministack).

**Esperado**: nenhuma mensagem em `pedido_lines_queue`; log estruturado registra
`ArquivoInvalidoError` com o nome do arquivo.

## Validar US3 — pedido individual invalido, arquivo continua (SC-003)

Fazer upload de um arquivo com 2 pedidos válidos e 1 com `item_count` divergente (mesma técnica de
`shared/pedidos_shared/tests/test_file_layout.py`).

**Esperado**: 2 mensagens em `pedido_lines_queue` (uma por pedido válido); log estruturado registra
`PedidoInvalidoError` para o pedido divergente, sem mensagem publicada para ele.

## Validar US5 — idempotência (SC-004)

Reenviar a mesma notificação (ou reprocessar o mesmo objeto do S3) e confirmar que nenhuma nova
mensagem aparece em `pedido_lines_queue` para os pedidos daquele arquivo.
