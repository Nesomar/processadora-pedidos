# Research: Acesso ao PDF da Nota Fiscal

## 1. Entrega: conteúdo direto vs. URL pré-assinada

- **Decision**: resposta `200 application/pdf` com o conteúdo, via `GET` no API Gateway.
- **Rationale**: decisão do usuário; mantém o S3 fechado, o gateway como ingresso único e dispensa
  expiração de links. PDF de nota fiscal é pequeno (KBs).
- **Alternatives**: URL pré-assinada (expõe endpoint do S3, que no Ministack local é
  `localhost:4566` e difícil de alcançar de dentro de containers); streaming em chunks (complexidade
  sem ganho para arquivos pequenos).

## 2. Rota

- **Decision**: `GET /pedidos/{order_id}/nota-fiscal`.
- **Rationale**: sub-recurso do pedido, coerente com `/pedidos/{id}/cancelamento`; não colide com
  `GET /pedidos/{order_id}`.
- **Alternatives**: `.../pdf`, `Accept: application/pdf` no recurso existente (negociação de
  conteúdo complica o contrato e os testes).

## 3. Mapeamento de estados → HTTP

| Situação | HTTP | Observação |
|---|---|---|
| Pedido inexistente | 404 | `Pedido não encontrado` |
| `RECEIVED`/`PROCESSING`/`VALIDATING`/`VALIDATED`/`INVOICING` | 409 | "ainda em processamento, tente novamente" |
| `REJECTED`/`FAILED`/`CANCELLED` | 410 | "nenhum PDF será gerado" |
| `COMPLETED` sem chave, ou objeto ausente no S3 | 404 | detalhe distinto: `PDF não encontrado no armazenamento` |
| `COMPLETED` com objeto | 200 | `application/pdf` |
| Falha técnica do S3 (≠ `NoSuchKey`) | 500 | propaga, sem mascarar |

- **Rationale**: 409 é transitório (vale repetir), 410 é permanente; coerente com o uso de 404/409
  já existente no gateway. Status do pedido decide, não a existência da chave: durante reprocessamento
  de pedido editado a `invoice_s3_key` antiga ainda existe, mas o status volta a `PROCESSING` → 409
  (nunca serve PDF desatualizado).

## 4. Não vazar a chave (FR-004 / US3)

- **Decision**: `PedidoResponse` troca `invoice_s3_key` por `invoice_available: bool`
  (`status == COMPLETED and invoice_s3_key is not None`).
- **Rationale**: spec exige não expor chave interna. É mudança incompatível no contrato de
  `GET /pedidos`; consumidores internos são só `tests/e2e` e README (2 asserts + 1 exemplo).
- **Alternatives**: manter a chave (viola FR-004); campo `invoice_url` apontando ao novo endpoint
  (redundante: a URL é determinística a partir do `order_id`).

## 5. Objeto ausente no S3

- **Decision**: `S3Client.get_object` levanta `ObjectNotFoundError` (em `pedidos_shared`) quando o
  código do `ClientError` é `NoSuchKey`; outros erros propagam.
- **Rationale**: o handler não deve importar `botocore`; único consumidor atual (`file-consumer`)
  não depende de `ClientError` específico.
  → verificar na implementação que `file-consumer` continua tratando a falha como técnica.

## 6. Cabeçalhos

- **Decision**: `Content-Type: application/pdf`, `Content-Disposition: inline; filename="nota-fiscal-{order_id}.pdf"`.
- **Rationale**: abre no navegador e baixa com nome útil via `curl -OJ`.

## 7. Autenticação

- **Decision**: fora de escopo (Assumptions). O `order_id` é UUID não adivinhável.
