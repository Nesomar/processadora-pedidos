# Research: Infraestrutura Local (Ministack)

**Feature**: [spec.md](./spec.md) | **Date**: 2026-07-18 (revisado)

## 1. boto3 vs awslocal CLI

**Decision**: `boto3` puro em Python, mesma lib de `pedidos_shared`.

**Rationale**: sem dependência nova, roda via `uv run` como qualquer outro script do repo.

**Alternatives considered**: `awslocal` CLI — rejeitado, exige instalação adicional.

## 2. Fonte única de nomes de recurso

**Decision**: `.env.example` na raiz do repo, usando as variáveis nativas que o Ministack já
reconhece (`AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` —
docs/01-dominio-e-contratos.md §8) mais uma variável por tabela/bucket/fila. Bootstrap e
`pedidos_shared.Settings` leem exatamente as mesmas variáveis.

**Rationale**: resolve FR-007 sem duplicar nomes; `AWS_*` (em vez de `MINISTACK_*`, decisão da
versão anterior desta spec) porque é o que o próprio Ministack e o boto3 já esperam nativamente —
menos tradução, menos chance de erro.

**Alternatives considered**: prefixo `MINISTACK_` custom (decisão anterior) — descartado, o
Ministack não usa esse prefixo; manter teria exigido uma camada de tradução sem propósito.

## 3. Idempotência de criação de recurso

**Decision**: função "criar ou verificar" por tipo de recurso, captura exceção boto3 de "já
existe" e trata como sucesso; drift de configuração vira log de aviso estruturado, não falha.

**Rationale**: FR-006; constitution I.5 "falha é dado".

**Alternatives considered**: apagar e recriar a cada execução — rejeitado, destrutivo.

## 4. Ordem de subida e disparo automático

**Decision**: bootstrap como serviço one-shot do `docker-compose.yml`
(`depends_on: ministack: condition: service_healthy`) + retry curto no próprio script como defesa
extra.

**Rationale**: `depends_on` nativo do Compose; retry cobre o caso raro de healthcheck reportar
saudável um instante antes da API aceitar conexões de fato.

**Alternatives considered**: bootstrap manual separado — revertido na clarificação da spec
(SC-001 exige comando único).

## 5. Notificação de evento do bucket S3 (novo — pós docs/01-dominio-e-contratos.md)

**Decision**: configurar a notificação (`put_bucket_notification_configuration`) como parte da
função "criar ou verificar" do bucket, comparando a configuração existente com a esperada
(prefixo `uploads/`, sufixo `.txt`, destino `s3_notifications_queue`) antes de escrever; se já
existir configuração igual, não reescreve (evita reset de outras regras); se existir configuração
divergente, loga aviso e não sobrescreve automaticamente (mesma política de drift da decisão #3).

**Rationale**: FR-005/FR-006; `put_bucket_notification_configuration` do S3 é uma operação PUT
completa (substitui toda a config de notificação do bucket) — reescrever incondicionalmente a cada
bootstrap arriscaria apagar outras regras que alguém tenha adicionado manualmente; comparar antes
de escrever preserva a idempotência sem esse risco.

**Alternatives considered**: sempre sobrescrever a notificação a cada bootstrap — rejeitado, viola
a mesma cautela de drift já adotada pra filas/tabelas (decisão #3); reescrever sem checar poderia
mascarar uma mudança manual investigável.

## 6. Duas tabelas DynamoDB (`orders` com GSIs, `processed_messages` com TTL)

**Decision**: duas funções de criação separadas — `create_or_verify_orders_table` (PK/SK + GSI1 +
GSI2, todos como parte da definição inicial da tabela, já que GSIs do DynamoDB não podem ser
adicionados via update no Ministack de forma simples) e `create_or_verify_processed_messages_table`
(PK simples + `TimeToLiveSpecification` habilitada em `ttl`).

**Rationale**: refletem exatamente §3; funções separadas porque são schemas completamente
diferentes (uma tem 2 GSIs, a outra é PK simples com TTL) — uma função genérica "criar tabela"
teria que aceitar uma configuração tão flexível que perderia a clareza de ter uma função por
responsabilidade (constitution VIII).

**Alternatives considered**: uma função `create_or_verify_table(name, schema)` genérica — rejeitado
aqui; só há 2 tabelas no domínio inteiro, generalizar agora é complexidade sem uso (YAGNI).
