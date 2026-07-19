# Research: Fundação Compartilhada (pedidos_shared)

**Feature**: [spec.md](./spec.md) | **Date**: 2026-07-18

Nenhum `NEEDS CLARIFICATION` restou no Technical Context (stack fixada pela constitution seção II).
As decisões abaixo cobrem as escolhas de implementação não fixadas pela constitution nem pela spec.

## 1. Logging estruturado JSON

**Decision**: Usar `logging` da stdlib com um `logging.Formatter` customizado que serializa o
record para JSON, injetando `orderId`/`correlationId` via `logging.LoggerAdapter` ou `extra=`.

**Rationale**: A stack obrigatória (constitution seção II) não lista uma lib de logging estruturado
(ex: `structlog`). A stdlib cobre o requisito (FR-007) sem dependência nova — YAGNI. `extra=` é o
mecanismo padrão do `logging` pra campos customizados por chamada.

**Alternatives considered**: `structlog` — rejeitado por não constar na stack obrigatória e por
resolver um problema que a stdlib já resolve em ~30 linhas.

## 2. Instalação do pacote como dependência local entre serviços

**Decision**: Workspace `uv` na raiz do monorepo (`[tool.uv.workspace] members = ["services/*",
"shared/pedidos_shared"]`), com cada serviço declarando `pedidos_shared` como dependência de
workspace (`pedidos-shared = { workspace = true }` no `pyproject.toml` do serviço).

**Rationale**: `uv` suporta workspaces nativamente, resolvendo FR-009 (instalável localmente sem
índice externo) sem symlink manual nem path relativo frágil. Um único lockfile de workspace mantém
versões de dependências transitivas consistentes entre serviços.

**Alternatives considered**: Path dependency direta (`pedidos-shared = { path = "../../shared/
pedidos_shared" }`) sem workspace — funciona, mas perde o lock compartilhado e exige repetir a
resolução de dependências transitivas em cada serviço; rejeitado por adicionar deriva de versão
entre serviços sem ganho.

## 3. Clientes SQS/DynamoDB/S3

**Decision**: Wrappers finos e síncronos sobre `boto3.client(...)`, um por serviço AWS
(`SqsClient`, `DynamoDbClient`, `S3Client`), todos recebendo `Settings` no construtor e usando
`Settings.ministack_endpoint_url` como `endpoint_url`.

**Rationale**: Constitution seção VIII: "async apenas onde há I/O concorrente real". Os workers
(order-processor, order-validator, pdf-generator, file-consumer) consomem uma mensagem SQS por vez
— não há concorrência real a explorar aqui. `boto3` síncrono é a opção mais simples que atende
FR-006.

**Alternatives considered**: `aioboto3` — rejeitado, adiciona dependência e complexidade async sem
ganho de throughput no padrão de consumo atual (um a um).

## 4. Mascaramento de documento

**Decision**: Função pura `mask_document(document: str) -> str` que preserva os últimos 4
caracteres e substitui todos os anteriores por `*`, mantendo o comprimento original. Para
documentos com 4 caracteres ou menos, mascara integralmente (nenhum dígito real exposto).

**Rationale**: Resolve a clarificação da spec ("últimos 4 dígitos visíveis") de forma determinística
e cobre o caso extremo (documento muito curto) sem expor 100% de um documento pequeno.

**Alternatives considered**: Mascaramento fixo por tipo de documento (CPF vs CNPJ) com máscara
posicional (`***.***.***-XX`) — rejeitado nesta feature por acoplar a função genérica de
mascaramento a um formato de documento específico; a formatação posicional por tipo, se necessária,
é responsabilidade do serviço chamador, não do pacote compartilhado.

## 5. Transições válidas do enum StatusPedido

**Decision**: Grafo de transição único, validado por uma função pura `is_valid_transition(current:
StatusPedido, next: StatusPedido) -> bool`:

```
RECEBIDO      → VALIDANDO
VALIDANDO     → VALIDADO | REJEITADO
VALIDADO      → GERANDO_PDF
GERANDO_PDF   → CONCLUIDO
{qualquer}    → ERRO
```

**Rationale**: FR-002/FR-003 exigem um único enum e um único lugar de verdade; a função de
transição válida evita que cada serviço reimplemente sua própria lógica de "quais transições fazem
sentido", fechando a lacuna do FR-010 (teste das transições válidas).

**Alternatives considered**: Deixar cada serviço decidir localmente quais transições aceita —
rejeitado, viola constitution I.2 (máquina de estados explícita e única).

## 6. Parser de arquivo posicional

**Decision**: Função `parse_fixed_width(line: str, layout: list[FieldSpec]) -> dict[str, str]`
genérica e sem estado, onde `FieldSpec` (start, end, nome) é fornecido pelo chamador — o pacote não
fixa um layout específico de arquivo de pedido.

**Rationale**: A spec (Assumptions) explicitamente deixa o layout concreto do arquivo de pedidos
para a spec do fluxo de arquivo (file-consumer/lambda-line-processor). O pacote compartilhado só
precisa fornecer o motor de parsing reutilizável (FR-008), não o layout.

**Alternatives considered**: Fixar já um layout de pedido no pacote — rejeitado, pois o layout real
ainda não foi especificado (spec futura), e fixá-lo aqui criaria acoplamento prematuro.
