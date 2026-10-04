# Quickstart: validar o acesso ao PDF

## Pré-requisitos

```bash
make up    # stack completa (Ministack + bootstrap + serviços)
```

## Cenário 1 — baixar o PDF (US1)

```bash
curl -s -X POST http://localhost:8000/pedidos -H 'Content-Type: application/json' \
  -d @examples/pedido-valido.json          # anota o order_id retornado
curl -s http://localhost:8000/pedidos/<order_id> | grep -E '"status"|invoice_available'
curl -s -o nota.pdf -D - http://localhost:8000/pedidos/<order_id>/nota-fiscal
head -c 4 nota.pdf                          # %PDF
```

Esperado: `200`, `Content-Type: application/pdf`, arquivo abre em um leitor de PDF,
`invoice_available: true`, e nenhum campo `invoice_s3_key` na consulta.

## Cenário 2 — respostas sem PDF (US2)

```bash
curl -i http://localhost:8000/pedidos/<order_id_recem_criado>/nota-fiscal   # 409 (se ainda em andamento)
curl -i http://localhost:8000/pedidos/<order_id_rejeitado>/nota-fiscal      # 410
curl -i http://localhost:8000/pedidos/inexistente/nota-fiscal               # 404
```

## Cenário 3 — armazenamento fechado (US3)

Conferir que nenhuma das respostas acima contém `invoices/`, bucket ou endpoint do S3.

## Testes automatizados

```bash
uv run --package api-gateway pytest services/api-gateway/tests/test_nota_fiscal.py -v
make e2e
```

Contratos: [nota-fiscal-endpoint.md](./contracts/nota-fiscal-endpoint.md).
