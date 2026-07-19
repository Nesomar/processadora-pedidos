# Research: Fundação Compartilhada (pedidos_shared)

**Feature**: [spec.md](./spec.md) | **Date**: 2026-07-18 (revisado)

Nenhum `NEEDS CLARIFICATION` restou. As decisões abaixo cobrem escolhas de implementação não
fixadas nem pela constitution nem por `docs/01-dominio-e-contratos.md`.

## 1. Logging estruturado JSON

**Decision**: `logging` da stdlib + `Formatter` custom que serializa pra JSON, injetando
`orderId`/`correlationId` via `extra=`.

**Rationale**: stack obrigatória não lista lib de log estruturado; stdlib resolve FR-009 sem
dependência nova.

**Alternatives considered**: `structlog` — rejeitado, fora da stack, resolve problema que a stdlib
já resolve.

## 2. Instalação local via workspace `uv`

**Decision**: workspace `uv` na raiz (`members = ["services/*", "shared/pedidos_shared"]`).

**Rationale**: resolve FR-013 sem symlink manual, lockfile único evita deriva de versão entre
serviços.

**Alternatives considered**: path dependency direta sem workspace — perde lock compartilhado,
rejeitada.

## 3. Clientes SQS/DynamoDB/S3

**Decision**: wrappers finos e síncronos sobre `boto3.client(...)` — `SqsClient`, `DynamoDbClient`,
`S3Client` — recebendo `Settings` no construtor.

**Rationale**: constitution VIII, "async só onde há I/O concorrente real"; workers consomem uma
mensagem por vez.

**Alternatives considered**: `aioboto3` — rejeitado, sem ganho no padrão de consumo atual.

## 4. Idempotência — `mark_message_processed`

**Decision**: `mark_message_processed(message_id, consumer) -> bool` grava em
`processed_messages` com `ConditionExpression=attribute_not_exists(PK)`; se a condição falhar
(`ConditionalCheckFailedException`), retorna `True` ("já processado"); se gravar com sucesso,
retorna `False` ("processar agora"). TTL de 7 dias no atributo `ttl` (epoch), nativo do DynamoDB —
nenhuma limpeza própria.

**Rationale**: implementa exatamente §3 de `docs/01-dominio-e-contratos.md` com uma única operação
atômica (write condicional), sem race condition entre "checar" e "marcar".

**Alternatives considered**: `get_item` seguido de `put_item` (check-then-act) — rejeitado, tem
race condition entre as duas chamadas; o `ConditionExpression` resolve isso numa única chamada.

## 5. Transições válidas de `OrderStatus`

**Decision**: `is_valid_transition(current, next) -> bool` codifica a tabela de §2.3 como um
dicionário `{estado_atual: {estados_destino_válidos}}`, incluindo a regra "qualquer não-terminal →
FAILED" e as regras de cancelamento/edição que saem de múltiplos estados de origem.

**Rationale**: fonte única de verdade sobre transição, testável exaustivamente contra a tabela do
documento de domínio.

**Alternatives considered**: cada serviço decidir localmente — rejeitado, viola constitution I.2.

## 6. Mascaramento de documento

**Decision**: `mask_document(document: str) -> str` preserva os últimos 4 caracteres, mascara o
resto; documentos com ≤4 caracteres são mascarados integralmente.

**Rationale**: FR-011; comportamento determinístico e testável no caso extremo.

**Alternatives considered**: máscara posicional por tipo de documento (CPF vs CNPJ) — rejeitado,
acopla a função genérica a um formato específico; formatação de exibição é responsabilidade do
serviço chamador.

## 7. Parser do layout posicional

**Decision**: parser dedicado ao layout de §6 (não um motor genérico) — dispatch por
`record_type` (`0`=header, `1`=detalhe-pedido, `2`=detalhe-item, `9`=trailer), com as 5 regras de
"Regras de parsing" implementadas como validações explícitas e erros de domínio próprios
(`ArquivoInvalidoError` pro arquivo inteiro, `LinhaInvalidaError` por linha, `PedidoInvalidoError`
por pedido com `item_count` divergente).

**Rationale**: o layout já é conhecido e fixo (não mais um placeholder a definir por spec futura)
— um parser dedicado ao layout real é mais simples e direto que um motor genérico configurável que
ninguém mais vai configurar diferente.

**Alternatives considered**: motor `parse_fixed_width(line, layout)` genérico (decisão da versão
anterior desta spec) — descartado; o layout do domínio já existe e é único, generalizar antes de
precisar é complexidade sem uso.
