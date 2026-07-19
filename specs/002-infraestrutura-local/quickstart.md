# Quickstart: Infraestrutura Local (Ministack)

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **Contrato**: [contracts/bootstrap-resources.md](./contracts/bootstrap-resources.md)

## Pré-requisitos

- Docker + Docker Compose instalados e rodando
- Python 3.12, `uv` instalado

## Subir o ambiente já populado (User Story 1 + User Story 2)

Cópia do `.env` é feita uma única vez (não repete a cada subida):

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d
```

**Esperado**: o Ministack fica saudável em poucos segundos (`docker compose ps` mostra o serviço
`ministack` `healthy`); o serviço `bootstrap` dispara automaticamente logo depois, roda e sai
(`docker compose ps` mostra `bootstrap` como `exited (0)`) — nenhum segundo comando necessário.
Validar os recursos diretamente:

```bash
aws --endpoint-url $MINISTACK_ENDPOINT_URL sqs list-queues
aws --endpoint-url $MINISTACK_ENDPOINT_URL dynamodb list-tables
aws --endpoint-url $MINISTACK_ENDPOINT_URL s3 ls
```

**Nota**: o valor de `PEDIDO_SOLICITADO_QUEUE_URL` em `.env.example` assume o account-id simulado
padrão do Ministack (`000000000000`). Depois do primeiro `docker compose up`, confirme a URL real
com `aws --endpoint-url $MINISTACK_ENDPOINT_URL sqs get-queue-url --queue-name pedido-solicitado`
e ajuste seu `.env` local se divergir.

## Validar idempotência (User Story 3)

```bash
docker compose -f infra/docker-compose.yml up -d
```

**Esperado**: o serviço `bootstrap` roda de novo automaticamente (restart do compose) sem erro;
`list-queues`/`list-tables`/`s3 ls` mostram exatamente os mesmos recursos de antes (nenhuma
duplicata). Alternativa pra rodar só o bootstrap manualmente, sem reiniciar o Ministack:

```bash
uv run --package infra-bootstrap python infra/bootstrap/main.py
```

## Validar que um serviço consumidor funciona sem configuração manual (SC-004)

Depois do ambiente subido e populado, rodar o teste de integração de `pedidos_shared`
(feature 001, quickstart.md) sem nenhuma alteração de endpoint no código:

```bash
uv run --package pedidos-shared pytest shared/pedidos_shared/tests/clients/test_sqs.py -v
```

**Esperado**: passa, usando só as variáveis de `.env` — nenhuma configuração adicional.
