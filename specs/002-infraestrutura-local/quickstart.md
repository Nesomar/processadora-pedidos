# Quickstart: Infraestrutura Local (Ministack)

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md) | **Contrato**: [contracts/bootstrap-resources.md](./contracts/bootstrap-resources.md)

## Pré-requisitos

- Docker + Docker Compose instalados e rodando
- Python 3.12, `uv` instalado

## Subir o ambiente já populado (User Story 1 + User Story 2)

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d
# ou: make up
```

**Esperado**: `ministack` fica `healthy`; `bootstrap` dispara automaticamente, roda e sai
(`exited (0)`). Validar os recursos:

```bash
aws --endpoint-url $AWS_ENDPOINT_URL sqs list-queues
aws --endpoint-url $AWS_ENDPOINT_URL dynamodb list-tables
aws --endpoint-url $AWS_ENDPOINT_URL s3 ls
aws --endpoint-url $AWS_ENDPOINT_URL s3api get-bucket-notification-configuration --bucket pedidos-bucket
```

**Esperado**: 9 filas (+9 DLQs), tabelas `orders` e `processed_messages`, bucket `pedidos-bucket`
com notificação apontando pra `s3_notifications_queue`.

## Validar idempotência (User Story 3)

```bash
docker compose -f infra/docker-compose.yml up -d
```

**Esperado**: `bootstrap` roda de novo sem erro; contagem de filas/tabelas/bucket e a notificação
de evento permanecem iguais.

## Validar upload de arquivo → notificação (SC-005)

```bash
echo "conteúdo de teste" > /tmp/teste.txt
aws --endpoint-url $AWS_ENDPOINT_URL s3 cp /tmp/teste.txt s3://pedidos-bucket/uploads/teste.txt
aws --endpoint-url $AWS_ENDPOINT_URL sqs receive-message --queue-url $S3_NOTIFICATIONS_QUEUE_URL
```

**Esperado**: a mensagem de notificação do S3 aparece em `s3_notifications_queue`.

## Validar que um serviço consumidor funciona sem configuração manual (SC-004)

```bash
uv run --package pedidos-shared pytest shared/pedidos_shared/tests/clients/test_sqs.py -v
```

**Esperado**: passa, usando só as variáveis de `.env`.

## Atalhos de Makefile (User Story 4)

```bash
make up          # docker compose up -d
make down         # docker compose down
make bootstrap     # roda só o bootstrap manualmente (sem reiniciar o Ministack)
make test            # pytest em todos os pacotes do workspace
make e2e               # tests/e2e/
make seed-file           # gera arquivo posicional de exemplo e faz upload em uploads/
```
