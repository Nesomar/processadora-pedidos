# Data Model: Suite de Testes End-to-End

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

Esta feature não introduz entidades de domínio novas — consome as já existentes (`Order`,
`OrderStatus`, catálogo externo) só pelos pontos de entrada reais (HTTP do API Gateway, upload de
arquivo no armazenamento). As "entidades" aqui são utilitários de teste.

## `tests/e2e/_poll.py`

| Função | Papel |
|---|---|
| `poll_until(fn, timeout=30.0, interval=0.5, description="") -> Any` | chama `fn()` até valor truthy ou timeout; `AssertionError` no timeout com `description` + último valor (research.md #2) |

## `tests/e2e/_file_builder.py`

| Função | Papel |
|---|---|
| `montar_arquivo_valido(customer_id: str, product_id: int, quantity: int) -> bytes` | gera um arquivo posicional válido (header + 1 pedido `SOLICITAR` + 1 item + trailer) com `customer_id` parametrizável (research.md #4) |

## `tests/e2e/conftest.py`

| Fixture | Papel |
|---|---|
| `_ambiente_no_ar` (session, autouse) | `GET /health` nos 6 serviços; `pytest.exit` se algum falhar (research.md #3) |
| `api_gateway` | `httpx.Client(base_url=API_GATEWAY_BASE_URL)` |
| `s3_client` | `pedidos_shared.S3Client` (só para o upload do cenário batch, FR-007) |
| `settings` | `pedidos_shared.Settings` lido do ambiente (bucket, endpoint Ministack) |

## Mapeamento cenário → pontos de entrada reais usados

| Cenário (user story) | Entrada real | Saída observada |
|---|---|---|
| US1 — online feliz | `POST /pedidos` | `GET /pedidos/{order_id}` até `status=COMPLETED` |
| US2 — rejeição de negócio | `POST /pedidos` (documento inválido) | `GET /pedidos/{order_id}` até `status=REJECTED` |
| US3 — batch feliz | `S3Client.put_object` em `uploads/` | `GET /pedidos?customerId=...` até 1 resultado |
| US4 — editar | `POST /pedidos` + `PUT /pedidos/{order_id}` | `GET /pedidos/{order_id}` reflete os novos itens |
| US5 — cancelar | `POST /pedidos` + `POST /pedidos/{order_id}/cancelamento` | `GET /pedidos/{order_id}` até `status=CANCELLED` |
