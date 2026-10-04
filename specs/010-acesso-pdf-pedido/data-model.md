# Data Model: Acesso ao PDF da Nota Fiscal

Nenhuma tabela, fila ou mensagem nova. Nenhuma escrita em `orders`.

## Entidades existentes usadas

- **Order** (`pedidos_shared.models`): lê `status` e `invoice_s3_key`. Campo mantido
  internamente; só deixa de ser exposto na API.
- **Objeto S3** `invoices/YYYY/MM/DD/{order_id}.pdf` no bucket `Settings.pedidos_bucket_name`:
  lido por `S3Client.get_object`.

## Mudanças de modelo

| Onde | Mudança |
|---|---|
| `pedidos_shared.clients.s3` | nova exceção `ObjectNotFoundError`; `get_object` a levanta em `NoSuchKey` |
| `api_gateway.schemas.PedidoResponse` | remove `invoice_s3_key`; adiciona `invoice_available: bool` |
| `api_gateway.domain.nota_fiscal` | `NotaFiscalEmAndamentoError`, `NotaFiscalIndisponivelError`; `chave_da_nota_fiscal(order) -> str` |

## Regras (função pura `chave_da_nota_fiscal`)

1. `COMPLETED` e `invoice_s3_key` presente → devolve a chave.
2. `COMPLETED` sem chave → `NotaFiscalAusenteError` (→ 404, detalhe de armazenamento).
3. `REJECTED`/`FAILED`/`CANCELLED` → `NotaFiscalIndisponivelError` (→ 410).
4. Demais estados → `NotaFiscalEmAndamentoError` (→ 409).

`invoice_available` em `PedidoResponse` = regra 1.
