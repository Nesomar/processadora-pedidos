# Research: Order Processor

**Feature**: [spec.md](./spec.md) | **Date**: 2026-07-20

Nenhum `NEEDS CLARIFICATION` restou. As decisões abaixo cobrem escolhas de implementação não
fixadas pela constitution nem pelo domínio.

## 1. Consumo concorrente de 5 filas — `threading` da stdlib

**Decision**: um thread por fila consumida (5 threads), cada um rodando um loop de
`SqsClient.receive` (curto-polling, com pequeno `sleep` entre chamadas vazias) + dispatch pro
handler correspondente. Sem `asyncio`/`aioboto3`.

**Rationale**: constitution VIII permite `async` "só onde há I/O concorrente real" — 5 filas
esperando mensagem ao mesmo tempo é exatamente esse caso, mas introduzir `aioboto3` contradiria a
decisão já tomada em `001-fundacao-compartilhada` (research.md #3: "workers consomem uma mensagem
por vez", sem ganho de `aioboto3`). `threading` é stdlib (não é dependência nova) e dá
concorrência real o suficiente para 5 loops de I/O bloqueante sem reescrever `pedidos_shared`.

**Alternatives considered**: um loop único fazendo round-robin nas 5 filas — rejeitado, atraso
desnecessário entre filas com tráfego desigual; `aioboto3`/`asyncio` — rejeitado, contradiz
decisão já tomada em 001.

## 2. Idempotência por mensagem

**Decision**: toda mensagem recebida chama `is_message_processed(message_id, "order-processor",
settings)` (checagem só-leitura) **antes** de qualquer efeito colateral. Se `True` (já
processada): a mensagem é confirmada (removida da fila) e descartada silenciosamente, com log em
nível `info` (`docs/01-dominio-e-contratos.md` §3). Se `False`: o handler executa; só depois de
concluir — com sucesso ou rejeição de negócio (`TransicaoInvalidaError`) — `mark_message_processed`
é chamado (agora sim gravando) e a mensagem é confirmada. Em falha técnica, nem `mark_message_processed`
nem a confirmação acontecem — o redrive do SQS reentrega e o handler roda de verdade de novo.

**Rationale**: FR-010, constitution I.3; mesmo mecanismo já usado por `pedidos_shared` (feature
001), sem reimplementação.

**Alternatives considered**: checar duplicidade só ao gravar em `orders` (via
`ConditionExpression`) — rejeitado; não cobre o caso de reentrega depois de já ter publicado a
mensagem downstream (a escrita em `orders` teria sucesso de novo se a versão ainda batesse, mas a
publicação duplicada em `validar_pedido_queue`/`pdf_request_queue` não seria evitada).

## 3. Concorrência otimista em `orders` — até 3 tentativas

**Decision**: toda escrita em `orders` usa `ConditionExpression = attribute_not_exists(PK) OR
version = :expected_version` e incrementa `version`. Se a condição falhar
(`ConditionalCheckFailedException`), o handler recarrega o item atual e reavalia a transição
contra o estado real, até 3 tentativas *dentro do mesmo processamento de mensagem*. Esgotadas as
3 tentativas, o handler trata como falha técnica e não confirma a mensagem — o redrive nativo do
SQS (já configurado em `002-infraestrutura-local`, `maxReceiveCount=3`) cuida das reentregas
subsequentes.

**Rationale**: `docs/01-dominio-e-contratos.md` §3, FR-011. As 3 tentativas de recarregar+reavaliar
são um mecanismo *diferente e mais fino* do que o `maxReceiveCount=3` da fila — evita reentrega
completa da mensagem só por causa de uma corrida de escrita passageira.

**Alternatives considered**: deixar todo conflito virar reentrega da mensagem via SQS (sem retry
local) — rejeitado; mais lento (espera o `visibility_timeout` inteiro) pra um conflito que
tipicamente se resolve em milissegundos.

## 4. `adapters/worker_loop.py` — esqueleto de consumo reaproveitado

**Decision**: uma função `run_consumer(queue_url, handler, settings)` genérica encapsula: receber
mensagem, decodificar `MessageEnvelope`, checar idempotência (#2), invocar `handler(envelope,
settings)`, confirmar (ou não) a mensagem. Os 5 handlers implementam só a lógica de negócio
específica (assinatura `handler(envelope, settings) -> None`, levanta exceção em erro técnico).

**Rationale**: constitution VIII, "um arquivo por handler" — sem esse esqueleto compartilhado, os
5 handlers duplicariam o mesmo bloco de idempotência/ack, violando DRY sem necessidade.

**Alternatives considered**: cada handler implementar seu próprio loop de consumo — rejeitado,
duplicação direta do mesmo padrão 5 vezes.

## 5. Transições reaproveitam `is_valid_transition` — sem tabela própria

**Decision**: `domain/transicoes.py` expõe funções finas por operação (ex.:
`aplicar_solicitacao`, `aplicar_aprovacao`, `aplicar_rejeicao`, `aplicar_conclusao_pdf`,
`aplicar_falha_pdf`, `pode_editar`, `pode_cancelar`), cada uma só chamando
`is_valid_transition(atual, alvo)` e retornando o novo status (ou `None`/erro se inválido).
Nenhuma tabela de estados redefinida.

**Rationale**: contrato regra 3 de `pedidos_shared-api.md` — `is_valid_transition` é a única fonte
de verdade sobre transição permitida; mesma abordagem já usada em `003-api-gateway`
(`elegibilidade_transicao.py`).

**Alternatives considered**: um único `if/elif` gigante decidindo a transição por tipo de
mensagem — rejeitado, constitution VIII prefere uma função pura por regra de negócio a uma
classe/função "God".

## 6. `/health` do worker — thread HTTP simples, stdlib

**Decision**: `http.server.HTTPServer` (stdlib) numa thread separada, porta 8080, respondendo
`GET /health` com `200 {"status":"ok"}`.

**Rationale**: constitution IV exige `/health` "mesmo os workers, via thread HTTP simples na
porta 8080" — literal.

**Alternatives considered**: subir uma app FastAPI só pra isso — rejeitado, dependência
desnecessária pra um endpoint trivial num processo que não é HTTP-nativo (diferente do
`003-api-gateway`, que já é FastAPI de qualquer forma).

## 7. Testes contra Ministack real

**Decision**: testes unitários dos handlers com `SqsClient`/`DynamoDbClient` mockados via
injeção de dependência simples (parâmetro, não DI framework); testes de integração publicando
mensagens reais nas filas e verificando o estado real em `orders`, contra Ministack local — mesmo
padrão de 001/002/003, pulando automaticamente se o Ministack não estiver acessível.

**Rationale**: consistência com a estratégia já validada nas três features anteriores.

**Alternatives considered**: nenhuma — padrão já estabelecido.
