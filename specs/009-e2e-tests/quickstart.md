# Quickstart: tests/e2e

**Feature**: [spec.md](./spec.md) | **Data model**: [data-model.md](./data-model.md)

## Pré-requisitos

- Docker, `uv`
- Ambiente completo no ar (`make up`) — os 6 serviços + Ministack + bootstrap já concluído
- `pytest`/`httpx` sincronizados no ambiente compartilhado (`uv sync --package pedidos-shared
  --extra dev` uma vez, se ainda não tiver feito nesta sessão de desenvolvimento — mesma
  pré-condição que `make test` já assume hoje)

## Rodar a suíte

```bash
make e2e
```

Equivalente direto: `uv run --all-packages pytest tests/e2e -v`.

## Validar US1 — fluxo online feliz (SC-001)

**Esperado**: `test_online_happy_path.py` cria um pedido válido via `POST /pedidos` e passa quando
`GET /pedidos/{order_id}` mostra `status=COMPLETED` com `invoice_s3_key` preenchido, dentro de 30s.

## Validar US2 — rejeição de negócio (SC-001)

**Esperado**: `test_business_rejection.py` cria um pedido com CPF inválido e passa quando o pedido
chega a `status=REJECTED` com `status_reason` não vazio.

## Validar US3 — batch feliz (SC-001)

**Esperado**: `test_batch_happy_path.py` faz upload de um arquivo posicional válido (com
`customer_id` único gerado na hora) e passa quando `GET /pedidos?customerId=...` mostra 1 pedido
com `channel=BATCH`.

## Validar US4/US5 — editar e cancelar (SC-001)

**Esperado**: `test_editar_pedido.py` e `test_cancelar_pedido.py` criam um pedido, aplicam a
operação e passam quando o estado final refletir a mudança (`CANCELLED`, ou itens atualizados).

## Validar SC-004 — ambiente fora do ar falha rápido

```bash
docker compose -f infra/docker-compose.yml stop api-gateway
make e2e
docker compose -f infra/docker-compose.yml start api-gateway
```

**Esperado**: a suíte para em poucos segundos (não minutos), indicando que `api-gateway` está
inacessível — nenhum cenário chega a rodar até o próprio timeout de 30s.
