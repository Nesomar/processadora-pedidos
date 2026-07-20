# Data Model: Order Validator

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## Entidades reaproveitadas (não redefinidas nesta feature)

`MessageEnvelope`, `Settings`, `is_message_processed`, `mark_message_processed` — todos de
`pedidos_shared` (feature `001-fundacao-compartilhada`). Este serviço **não** usa `Order`,
`OrderItem` nem `OrderStatus`/`is_valid_transition` — não escreve na tabela `orders` e não
participa da máquina de estados (FR-015).

## Entidades próprias desta feature

### `Produto` (dataclass, saída de `adapters/catalogo_produtos.py`)

Espelha os campos usados do catálogo externo (`docs/01-dominio-e-contratos.md` §2.1) — nunca
persistido, só mantido em cache TTL em memória.

| Campo | Tipo | Origem |
|---|---|---|
| `id` | `int` | `id` do dummyjson |
| `title` | `str` | `title` |
| `price` | `Decimal` | `price` (convertido de `float`) |
| `stock` | `int` | `stock` |
| `minimum_order_quantity` | `int` | `minimumOrderQuantity` |
| `availability_status` | `str` | `availabilityStatus` |
| `sku` | `str` | `sku` |
| `discount_percentage` | `Decimal` | `discountPercentage` (convertido de `float`) |

### `ItemValidacao` (dataclass, entrada — um por item do payload de `validar_pedido_queue`)

| Campo | Tipo |
|---|---|
| `product_id` | `int` |
| `quantity` | `int` |

### `ErroValidacao` (dataclass, saída — um por regra violada)

| Campo | Tipo | Nota |
|---|---|---|
| `code` | `str` | `PRODUCT_NOT_FOUND` \| `BELOW_MINIMUM_ORDER_QUANTITY` \| `INSUFFICIENT_STOCK` \| `INVALID_DOCUMENT` \| `ORDER_TOTAL_EXCEEDS_LIMIT` |
| `product_id` | `int \| None` | `None` para `INVALID_DOCUMENT`/`ORDER_TOTAL_EXCEEDS_LIMIT` (erro do pedido, não de um item) |
| `message` | `str` | descrição legível, inclui o valor relevante (ex.: mínimo exigido) |

### `ItemEnriquecido` (dataclass, saída — um por item, só quando aprovado)

| Campo | Tipo |
|---|---|
| `product_id` | `int` |
| `quantity` | `int` |
| `unit_price` | `Decimal` |
| `discount_percentage` | `Decimal` |
| `line_total` | `Decimal` |
| `product_title` | `str` |
| `product_sku` | `str` |

## Mapeamento fila consumida → regras aplicadas → fila publicada

| Fila consumida | Regras aplicadas (em ordem) | Fila publicada |
|---|---|---|
| `validar_pedido_queue` | (1) `documento.validar_documento`; (2) por item: existência (adapter) → `estoque.validar_estoque` + `quantidade_minima.validar_quantidade_minima`; (3) se nenhum erro em (1)/(2): `calculo.calcular_totais` → `limite_total.validar_limite_total` | `validar_pedido_response_queue` |

Payloads exatos: `contracts/order-validator-messages.md` (espelha
`docs/01-dominio-e-contratos.md` §5, com os 2 códigos de erro novos documentados como extensão —
ver spec.md Assumptions).

## `domain/` — contrato (funções puras, sem I/O, research.md #3/#4)

| Função | Papel |
|---|---|
| `documento.validar_documento(document: str) -> bool` | CPF/CNPJ com dígito verificador (módulo 11); `False` → gera `ErroValidacao(code="INVALID_DOCUMENT", product_id=None, ...)` no handler |
| `estoque.validar_estoque(quantity: int, produto: Produto) -> ErroValidacao \| None` | `None` se `quantity <= produto.stock` e `produto.availability_status != "Out of Stock"`; senão `INSUFFICIENT_STOCK` |
| `quantidade_minima.validar_quantidade_minima(quantity: int, produto: Produto) -> ErroValidacao \| None` | `None` se `quantity >= produto.minimum_order_quantity`; senão `BELOW_MINIMUM_ORDER_QUANTITY` |
| `limite_total.validar_limite_total(total: Decimal) -> ErroValidacao \| None` | `None` se `total <= Decimal("100000.00")`; senão `ORDER_TOTAL_EXCEEDS_LIMIT` (sem `product_id`) |
| `calculo.calcular_item(item: ItemValidacao, produto: Produto) -> ItemEnriquecido` | `line_total = quantity * unit_price * (1 - discount_percentage/100)` |
| `calculo.calcular_totais(itens: list[ItemEnriquecido]) -> tuple[Decimal, Decimal, Decimal]` | `(subtotal, discount_total, total)` — `subtotal = Σ quantity*unit_price`, `total = Σ line_total`, `discount_total = subtotal - total` |
| `mensagens.montar_resposta_aprovada(itens: list[ItemEnriquecido], subtotal, discount_total, total) -> dict` | payload `approved=true` (contrato §5) |
| `mensagens.montar_resposta_reprovada(erros: list[ErroValidacao]) -> dict` | payload `approved=false`, totais/itens nulos |

## `adapters/catalogo_produtos.py` — contrato

| Função/Classe | Papel |
|---|---|
| `class ProdutoNaoEncontradoError(Exception)` | levantada quando a API externa responde 404 — erro de negócio, tratado no handler como `PRODUCT_NOT_FOUND` |
| `buscar_produto(client: httpx.Client, cache: CatalogoCache, product_id: int) -> Produto` | consulta cache (TTL 5min); se expirado/ausente, chama a API real com timeout+retry curto (research.md #1); `404` → `ProdutoNaoEncontradoError`; timeout/5xx após retries → propaga a exceção original (tratada como falha técnica pelo `worker_loop`) |
| `class CatalogoCache` | dict interno `{product_id: (Produto, expires_at)}`, TTL 5min (research.md #2) |

## `adapters/worker_loop.py` — contrato

Idêntico ao padrão corrigido em `004-order-processor` (research.md #5): `is_message_processed`
antes do handler; `mark_message_processed` só depois de sucesso ou reprovação de negócio; falha
técnica não marca nem confirma.
