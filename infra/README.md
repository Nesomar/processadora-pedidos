# infra — Ministack local + bootstrap

Ambiente de desenvolvimento local: `docker-compose.yml` sobe o Ministack (emulador AWS: SQS,
DynamoDB, S3) e dispara automaticamente um serviço `bootstrap` one-shot que cria/verifica todos
os recursos do domínio (`docs/01-dominio-e-contratos.md` §3, §4, §7).

## Subir o ambiente

```bash
cp .env.example .env      # uma vez
docker compose -f infra/docker-compose.yml up -d
# ou: make up
```

`ministack` fica saudável; `bootstrap` dispara automaticamente (`depends_on: condition:
service_healthy`), cria os recursos e sai com código 0. Rodar de novo não falha nem duplica nada
(idempotente).

## Variáveis de ambiente (`.env.example`, raiz do repo)

| Variável | Papel |
|---|---|
| `AWS_ENDPOINT_URL` | Endpoint do Ministack. `http://localhost:4566` para ferramentas no host (aws cli, pytest, `uv run` direto); dentro do compose, o serviço `bootstrap` sobrescreve para `http://ministack:4566` (nome do serviço na rede do compose) |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Credenciais fixas do Ministack |
| `ORDERS_TABLE_NAME`, `PROCESSED_MESSAGES_TABLE_NAME` | Nomes das tabelas DynamoDB |
| `PEDIDOS_BUCKET_NAME` | Nome do bucket S3 |
| `*_QUEUE_URL` (9 variáveis) | Uma URL por fila SQS do domínio (§4); preenchidas após o bootstrap criar as filas |

Essas são as mesmas variáveis lidas por `Settings` de `pedidos_shared` (feature
`001-fundacao-compartilhada`) — o bootstrap e os serviços compartilham a mesma fonte de nomes
(contrato: [`../specs/002-infraestrutura-local/contracts/bootstrap-resources.md`](../specs/002-infraestrutura-local/contracts/bootstrap-resources.md)).

## Recursos criados

- 9 filas SQS (cada uma com sua DLQ, `maxReceiveCount=3`, `visibility_timeout=60s`,
  `message_retention=4 dias`)
- Tabela `orders` (`PK`/`SK` + `GSI1` por cliente + `GSI2` por status)
- Tabela `processed_messages` (`PK` + TTL nativo de 7 dias no atributo `ttl`)
- Bucket `pedidos-bucket` com notificação de evento `s3:ObjectCreated:*` (prefixo `uploads/`,
  sufixo `.txt`) publicando em `s3_notifications_queue`

Recurso pré-existente com configuração divergente da esperada **não falha o bootstrap** — vira log
de aviso (constitution I.5).

## Makefile

```bash
make up          # docker compose up -d
make down        # docker compose down
make bootstrap   # roda só o bootstrap manualmente, sem reiniciar o Ministack
make test        # pytest em todos os pacotes do workspace que já existem
make e2e         # pytest em tests/e2e (quando existir)
make seed-file   # gera um arquivo posicional de exemplo válido e envia pra uploads/ no bucket
```

## Testes

```bash
uv run --package infra-bootstrap pytest infra/bootstrap/tests -v
```

Rodam contra um Ministack real (`docker compose -f infra/docker-compose.yml up -d` primeiro) —
são pulados automaticamente se o Ministack não estiver acessível em `AWS_ENDPOINT_URL`.
