# Research: Infraestrutura Local (Ministack)

**Feature**: [spec.md](./spec.md) | **Date**: 2026-07-18

Nenhum `NEEDS CLARIFICATION` restou no Technical Context. As decisões abaixo cobrem as escolhas
de implementação que a constitution deixa em aberto (seção II lista "boto3 ou awslocal CLI").

## 1. boto3 vs awslocal CLI para os scripts de bootstrap

**Decision**: `boto3` puro em scripts Python, mesma lib já usada em `pedidos_shared` (feature 001).

**Rationale**: Evita depender de um binário externo (`awslocal`) instalado separadamente na
máquina do desenvolvedor; `boto3` já é dependência obrigatória da stack (constitution II) e roda
via `uv run` igual a qualquer outro script Python do repo, sem ferramenta nova.

**Alternatives considered**: `awslocal` CLI (wrapper de shell sobre `aws` CLI) — rejeitado, exige
instalação adicional (CLI da AWS + awslocal) fora do que `uv sync` já resolve; sem ganho sobre
boto3 para o volume de recursos desta feature (poucas filas, uma tabela, um bucket).

## 2. Fonte única de verdade pros nomes de recursos (evitar deriva)

**Decision**: Um arquivo `.env.example` na raiz do repo lista todos os nomes de fila/tabela/bucket
e o endpoint do Ministack. O bootstrap lê essas variáveis de ambiente (já carregadas pelo
`docker-compose` via `env_file` ou exportadas pelo desenvolvedor a partir de uma cópia local
`.env`) e cria os recursos com exatamente esses nomes; cada serviço (via `Settings` de
`pedidos_shared`) lê as mesmas variáveis.

**Rationale**: Resolve FR-006/FR-007 (nomes do bootstrap MUST bater com o que os serviços esperam)
sem duplicar a lista de nomes em dois lugares do código — um único arquivo é a fonte de verdade,
lido tanto pelo bootstrap quanto por cada serviço.

**Alternatives considered**: Hardcodar os nomes dentro do próprio script de bootstrap e replicar os
mesmos valores manualmente na documentação de cada serviço — rejeitado, é exatamente a deriva que
FR-006 existe para evitar; viola constitution IV (nenhum valor de infraestrutura hardcoded).

## 3. Idempotência de criação de recurso (SQS/DynamoDB/S3)

**Decision**: Uma função "criar ou verificar" por tipo de recurso, que captura a exceção boto3 de
"já existe" (`QueueNameExists`, `ResourceInUseException`, `BucketAlreadyOwnedByYou`) e trata como
sucesso; se o recurso existente não tiver a configuração esperada (ex: fila sem redrive policy),
loga um aviso estruturado em vez de falhar silenciosamente ou de tentar recriar.

**Rationale**: Atende FR-005 (idempotência) e ao princípio "falha é dado, não exceção silenciosa"
(constitution I.5) — drift de configuração vira log visível, não um erro que trava o bootstrap nem
um estado inconsistente ignorado.

**Alternatives considered**: Apagar e recriar o recurso a cada execução do bootstrap — rejeitado,
destrutivo (perderia dados de teste do desenvolvedor entre execuções) e desnecessário pra atingir
idempotência.

## 4. Ordem de subida (Ministack pronto antes do bootstrap) e disparo automático

**Decision**: O bootstrap roda como um serviço one-shot do próprio `docker-compose.yml`
(`depends_on: ministack: condition: service_healthy`), disparado automaticamente por
`docker-compose up` (ver Clarifications em spec.md). Como defesa extra além do `depends_on`, o
script de bootstrap também faz um retry curto (poucas tentativas, backoff simples) ao conectar.

**Rationale**: `depends_on` com `condition: service_healthy` é o mecanismo nativo do Docker Compose
pra isso — nenhum orquestrador externo necessário. O retry no próprio script cobre o caso raro de
o healthcheck reportar saudável um instante antes da API do Ministack aceitar conexões de fato.
Resolve tanto o edge case de corrida na subida quanto a exigência de FR-001/FR-007 de um único
comando sem passo manual.

**Alternatives considered**: Bootstrap como comando manual separado — era a decisão original desta
pesquisa, revertida após a clarificação da spec (SC-001 exige um único comando); manter como estava
teria deixado research.md e spec.md inconsistentes.
