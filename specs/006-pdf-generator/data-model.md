# Data Model: PDF Generator

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

## Entidades reaproveitadas (não redefinidas nesta feature)

`MessageEnvelope`, `Settings`, `S3Client`, `is_message_processed`, `mark_message_processed` —
todos de `pedidos_shared` (feature `001-fundacao-compartilhada`), exceto `S3Client.put_object`, que
ganha um parâmetro opcional `content_type` (research.md #2). Este serviço **não** usa `Order`,
`OrderItem` nem `OrderStatus`/`is_valid_transition` — não escreve na tabela `orders` e não
participa da máquina de estados (FR-008); só publica a resposta que o Order Processor consome.

## Entidades próprias desta feature

### `DadosNotaFiscal` (dataclass, entrada de `domain/renderizador.py` — parseada do payload de
`pdf_request_queue`)

| Campo | Tipo | Origem |
|---|---|---|
| `customer_name` | `str` | payload `customer_name` |
| `customer_document` | `str` | payload `customer_document` |
| `items` | `list[ItemNotaFiscal]` | payload `items` |
| `subtotal` | `Decimal` | payload `subtotal` (string → `Decimal`) |
| `discount_total` | `Decimal` | payload `discount_total` (string → `Decimal`) |
| `total` | `Decimal` | payload `total` (string → `Decimal`) |

### `ItemNotaFiscal` (dataclass, um por item de `DadosNotaFiscal.items`)

| Campo | Tipo | Nota |
|---|---|---|
| `product_title` | `str` | `"—"` se ausente na mensagem (Edge Cases) |
| `product_sku` | `str` | `"—"` se ausente na mensagem (Edge Cases) |
| `quantity` | `int` | obrigatório — ausente conta como dado incompleto (US2/FR-005, Clarifications) |
| `unit_price` | `Decimal` | obrigatório — ausente conta como dado incompleto (US2/FR-005, Clarifications) |
| `discount_percentage` | `Decimal` | obrigatório — ausente conta como dado incompleto (US2/FR-005, Clarifications) |
| `line_total` | `Decimal` | obrigatório — ausente conta como dado incompleto (US2/FR-005, Clarifications) |

## Mapeamento fila consumida → processamento → fila publicada

| Fila consumida | Processamento (em ordem) | Fila publicada |
|---|---|---|
| `pdf_request_queue` | (1) `validacao.validar_solicitacao` — se retornar mensagem de erro, publica `success=false` (US2); (2) parse do payload em `DadosNotaFiscal`; (3) `chave_s3.montar_chave_invoice(order_id, datetime.now(UTC))`; (4) `renderizador.renderizar_nota_fiscal` → bytes; (5) `S3Client.put_object` (bucket, chave, bytes, `content_type="application/pdf"`) — exceção aqui é falha técnica (FR-006, sem resposta); (6) publica `success=true` com a chave | `pdf_response_queue` |

Payloads exatos: `contracts/pdf-generator-messages.md` (espelha `docs/01-dominio-e-contratos.md`
§5).

## `domain/` — contrato (funções puras, sem I/O, research.md #1/#3/#4)

| Função | Papel |
|---|---|
| `validacao.validar_solicitacao(payload: dict) -> str \| None` | `None` se `customer_name`, `customer_document` e ao menos 1 item presentes; senão mensagem de erro descrevendo o campo ausente (US2) |
| `chave_s3.montar_chave_invoice(order_id: str, momento: datetime) -> str` | `invoices/{ano:04d}/{mes:02d}/{dia:02d}/{order_id}.pdf` (FR-003) |
| `renderizador.renderizar_nota_fiscal(dados: DadosNotaFiscal) -> bytes` | monta o PDF via ReportLab `platypus` com cliente, documento, tabela de itens e totais (FR-002); não recalcula nenhum valor monetário |
| `mensagens.montar_resposta_sucesso(s3_key: str) -> dict` | payload `success=true` (contrato §5) |
| `mensagens.montar_resposta_falha(mensagem: str) -> dict` | payload `success=false`, `s3_key` nulo (contrato §5) |

## `adapters/` — contrato

| Função/Classe | Papel |
|---|---|
| `armazenamento.salvar_pdf(s3: S3Client, bucket: str, key: str, conteudo: bytes) -> None` | fino wrapper sobre `S3Client.put_object(..., content_type="application/pdf")`; propaga qualquer exceção do cliente S3 como falha técnica (FR-006) |
| `worker_loop` | idêntico ao padrão de `004-order-processor`/`005-order-validator` (research.md #5): `is_message_processed` antes do handler; `mark_message_processed` só depois de sucesso ou reprovação de negócio; falha técnica não marca nem confirma |
