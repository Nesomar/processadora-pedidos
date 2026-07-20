# Research: API Gateway

**Feature**: [spec.md](./spec.md) | **Date**: 2026-07-19

Nenhum `NEEDS CLARIFICATION` restou no Technical Context. As decisões abaixo cobrem escolhas de
implementação não fixadas pela constitution nem pelo domínio.

## 1. Framework HTTP

**Decision**: FastAPI + Uvicorn.

**Rationale**: constitution II fixa essa stack como obrigatória pra "API HTTP" — não há escolha a
fazer aqui, só confirmar.

**Alternatives considered**: nenhuma — stack obrigatória.

## 2. Elegibilidade de edição/cancelamento via `is_valid_transition`

**Decision**: `domain/elegibilidade_transicao.py` decide se um pedido pode ser editado chamando
`is_valid_transition(status_atual, OrderStatus.PROCESSING)`, e se pode ser cancelado chamando
`is_valid_transition(status_atual, OrderStatus.CANCELLED)` — ambos de `pedidos_shared`. Nenhuma
tabela de estados própria.

**Rationale**: a tabela de transições de `data-model.md` (feature 001) já cobre exatamente essas
duas famílias de transição (`RECEIVED`/`VALIDATED`/`REJECTED` → `PROCESSING` reabre o ciclo;
`RECEIVED`/`PROCESSING`/`VALIDATING`/`VALIDATED` → `CANCELLED`); contrato regra 3 de
`pedidos_shared-api.md` — "`is_valid_transition` é a única função autorizada a decidir se uma
transição de status é permitida" — proíbe qualquer reimplementação local.

**Alternatives considered**: checar um conjunto de estados permitidos hardcoded no handler —
rejeitado, duplicaria a tabela de transições já centralizada e violaria o contrato regra 3.

## 3. `orders_repository.py` — só leitura

**Decision**: o adapter de `orders` expõe só `get_by_id(order_id)` e
`query_by_customer(customer_id)`, nenhum método de escrita.

**Rationale**: FR-004 e o contrato regra 3 de `pedidos_shared-api.md` — "nenhuma escrita em
`orders` acontece fora do Order Processor". Não expor `put`/`update` no adapter torna essa regra
verificável estruturalmente (não dá pra violar por acidente).

**Alternatives considered**: um repository genérico com CRUD completo — rejeitado, exporia
métodos de escrita que a spec proíbe explicitamente de usar.

## 4. Rotas HTTP

**Decision**:

| Método | Rota | Handler | User Story |
|---|---|---|---|
| `POST` | `/pedidos` | `solicitar_pedido` | US1 + US2 (`channel` no payload distingue HTTP/BATCH) |
| `PUT` | `/pedidos/{order_id}` | `editar_pedido` | US3 |
| `POST` | `/pedidos/{order_id}/cancelamento` | `cancelar_pedido` | US4 |
| `GET` | `/pedidos/{order_id}` | `consultar_pedido` | US5 |
| `GET` | `/pedidos?customerId=X` | `listar_pedidos` | US6 |
| `GET` | `/health` | — | constitution IV |

**Rationale**: convenção REST para a maioria das rotas; `GET /pedidos?customerId=X` usa o nome
literal do endpoint já especificado em `docs/01-dominio-e-contratos.md` §3.

**Alternatives considered**: `DELETE /pedidos/{order_id}` pra cancelamento — rejeitado, `DELETE`
com corpo (`reason` obrigatório por FR-007) é convenção fraca/inconsistente entre clientes HTTP;
`POST` num sub-recurso de cancelamento é mais explícito.

## 5. Mascaramento na consulta/listagem

**Decision**: `consultar_pedido` e `listar_pedidos` aplicam `mask_document` (de `pedidos_shared`)
em `customer_document` antes de serializar a resposta.

**Rationale**: spec.md Clarifications (sessão 2026-07-19) — decisão explícita do usuário; FR-008.

**Alternatives considered**: retornar documento completo — rejeitado na clarificação, dado que a
feature não define autenticação/autorização.

## 6. `GET /health`

**Decision**: rota `/health` na mesma aplicação FastAPI, sem thread HTTP separada.

**Rationale**: constitution IV exige `/health` "mesmo os workers, via thread HTTP simples na
porta 8080" — essa exigência de thread separada é pra workers que não são serviços HTTP; o API
Gateway já é HTTP nativo, então `/health` é só mais uma rota da mesma app.

**Alternatives considered**: nenhuma — caso trivial.

## 7. Estratégia de testes

**Decision**: testes unitários com `starlette.testclient`/`httpx`, injetando `SqsClient`/
`DynamoDbClient` fake via dependency override do FastAPI (sem rede); testes de integração
separados contra Ministack real (mesmo padrão de `test_sqs.py` em 001 e dos testes de
`infra/bootstrap` em 002) que pulam automaticamente se o Ministack não estiver acessível.

**Rationale**: consistência com a estratégia já validada nas duas features anteriores; testes
unitários rápidos pra lógica de validação/roteamento, testes de integração pra confirmar que a
mensagem realmente chega na fila.

**Alternatives considered**: só testes de integração — rejeitado, tornaria a suíte lenta e
dependente do Ministack pra toda execução, incluindo casos que são puramente lógica de validação.

## 8. Consulta em ambiente de teste sem o Order Processor

**Decision**: o `quickstart.md` e os testes de integração de `consultar_pedido`/`listar_pedidos`
semeiam um registro de teste diretamente na tabela `orders` via `pedidos_shared.DynamoDbClient`
(não via a API), já que o Order Processor (que normalmente persiste o registro) ainda não existe
como feature implementada.

**Rationale**: a regra "API Gateway nunca escreve em `orders`" é sobre o *código de produção*
deste serviço, não sobre a arrumação de dados de um teste — semear um fixture direto no banco é
prática padrão de "arrange" em teste de integração, sem violar a regra de negócio.

**Alternatives considered**: esperar a feature do Order Processor existir antes de testar consulta
— rejeitado, bloquearia a validação completa desta feature por uma dependência externa evitável.
