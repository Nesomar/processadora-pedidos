# Research: Lambda Line Processor

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## 1. Chamada HTTP ao API Gateway (exceção documentada em constitution I.1)

**Decision**: `httpx.Client(base_url=settings.api_gateway_base_url, timeout=5.0)`, com retry
manual curto (2 tentativas extras, backoff fixo de 0.5s) só para `httpx.ConnectError`/
`httpx.TimeoutException` — mesmo padrão já usado pelo Order Validator para o catálogo externo
(`005-order-validator` research.md #1), agora reaproveitado para a segunda exceção de HTTP síncrono
documentada em I.1 (constitution v1.0.2). Um `5xx` do API Gateway **não** é retryado pelo cliente —
propaga como falha técnica pro `worker_loop` decidir não confirmar a mensagem (redrive nativo do
SQS resolve isso em nível de mensagem, não de chamada HTTP individual).

**Rationale**: mesma lógica de `005-order-validator`: o retry do cliente HTTP absorve instabilidade
de rede momentânea sem gastar uma das 3 tentativas de redrive da mensagem inteira; o redrive do SQS
lida com indisponibilidade mais persistente do API Gateway.

**Alternatives considered**: sem retry no cliente (100% no SQS) — rejeitado, mesma razão de
`005-order-validator`; biblioteca de retry externa (`tenacity`) — rejeitada, não está na stack
obrigatória (constitution II) e 2 tentativas com backoff fixo não justificam a dependência nova.

## 2. `api_gateway_base_url` como Settings específico do serviço

**Decision**: `LambdaLineProcessorSettings(Settings)` com `api_gateway_base_url: str` (sem
default — obrigatório, aponta pro serviço `api-gateway` real, não uma API externa) em
`services/lambda-line-processor/src/lambda_line_processor/config.py`. Não é adicionado a
`pedidos_shared.Settings`.

**Rationale**: mesmo padrão de `catalog_products_base_url` em `005-order-validator/config.py` — um
campo que só um serviço usa vive na subclasse local de `Settings`, não no shared (constitution III:
contratos compartilhados por todos os serviços vivem em `pedidos_shared`; configuração específica
de um único serviço, não). `.env.example` ganha `API_GATEWAY_BASE_URL` e o `docker-compose.yml`
aponta pro nome do serviço na rede do compose (`http://api-gateway:8000`), igual ao padrão já usado
para `AWS_ENDPOINT_URL` (research.md do `002-infraestrutura-local`).

**Alternatives considered**: adicionar a `pedidos_shared.Settings` — rejeitado, nenhum outro
serviço precisa desse campo, mesma razão que manteve `catalog_products_base_url` fora do shared.

## 3. Mapeamento operação → chamada HTTP e decisão por status code

**Decision**: função pura `montar_chamada(body: dict) -> tuple[str, str, dict]` (método, path,
corpo) em `domain/chamada_api.py`:
- `SOLICITAR` → `POST /pedidos`, corpo = `parsed`
- `EDITAR` → `PUT /pedidos/{order_id}`, corpo = `parsed` (levanta `ComandoInvalidoError` se
  `order_id` ausente)
- `CANCELAR` → `POST /pedidos/{order_id}/cancelamento`, corpo = `parsed` (levanta
  `ComandoInvalidoError` se `order_id` ausente)
- qualquer outra `operation` → levanta `ComandoInvalidoError`

Depois da chamada, o handler decide pelo `status_code` da resposta: `< 300` → sucesso (confirma);
`400`/`404`/`409` → rejeição de negócio permanente (loga, confirma, sem levantar); qualquer outro
código (`5xx`, ou qualquer coisa fora do esperado) → levanta exceção técnica (não confirma).
`ComandoInvalidoError` (FR-007, Edge Cases) é tratado exatamente como uma rejeição de negócio
permanente — loga e confirma, sem chamar o API Gateway.

**Rationale**: FR-002 a FR-007. Função pura e testável sem mock de rede, consistente com
constitution VIII; decisão de ack/no-ack fica isolada no handler, mesmo padrão de separação já
usado nos demais workers.

**Alternatives considered**: deixar a decisão de retry/permanente dentro do próprio cliente HTTP —
rejeitado, misturaria a política de negócio (quais status são permanentes) com o transporte,
dificultando testar cada uma isoladamente.

## 4. Idempotência (reaproveitando `007-file-consumer`)

**Decision**: mesmo `adapters/worker_loop.py` raw (sem `MessageEnvelope`) de
`007-file-consumer`, usando `SqsClient.receive_raw_with_receipt`/`is_message_processed`/
`mark_message_processed` chaveados pelo `MessageId` nativo do SQS — sem nenhuma mudança em
`pedidos_shared` desta vez, já que `receive_raw_with_receipt` já existe.

**Rationale**: FR-009, mesma justificativa de `007-file-consumer` research.md #2/#3 —
`pedido_lines_queue` não usa `MessageEnvelope` (não há `order_id` disponível para `SOLICITAR`).

**Alternatives considered**: nenhuma — infraestrutura já construída na feature anterior.

## 5. Estratégia de testes

**Decision**: testes unitários com `httpx` mockado cobrindo `domain/chamada_api.py` e o handler
(sucesso, recusa de negócio, comando inválido, falha técnica). Um teste de integração real contra
Ministack **e** um `api-gateway` real (ambos já fazem parte do mesmo `docker-compose.yml`) cobre o
fluxo completo: publica uma linha real em `pedido_lines_queue`, processa, chama o `api-gateway`
real via HTTP, e confirma que o pedido realmente aparece em `orders` (DynamoDB real) — diferente de
`005-order-validator`, aqui o alvo HTTP é um serviço do próprio monorepo (determinístico, sem
flakiness de rede externa), então vale testar a chamada real, não só mockada.

**Rationale**: constitution IX exige ao menos um teste de integração contra o Ministack; como o
`api-gateway` é parte do mesmo ambiente local (não uma API de terceiros como o dummyjson.com), não
há o mesmo motivo de `005-order-validator` para evitar bater nele durante `pytest` — o teste ganha
cobertura real ponta a ponta sem introduzir flakiness.

**Alternatives considered**: mockar o `api-gateway` também no teste de integração — rejeitado,
perderia a chance de validar a integração real entre dois serviços do próprio sistema sem custo de
flakiness adicional.
