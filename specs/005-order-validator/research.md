# Research: Order Validator

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## 1. Cliente HTTP externo (dummyjson.com)

**Decision**: `httpx.Client` (síncrono — mesma escolha de `threading` sobre `asyncio` já feita em
`004-order-processor`, sem motivo pra introduzir I/O assíncrono aqui), com `timeout=5.0` segundos
e retry manual curto (2 tentativas extras, backoff fixo de 0.5s) só para erros de conexão/timeout
— não para `404` (que é decisão de negócio, não falha técnica) nem para `5xx` (falha técnica real,
que deve propagar pra fora do adapter e deixar o `worker_loop` NÃO confirmar a mensagem,
permitindo o redrive nativo do SQS cuidar do reprocessamento em nível de mensagem).

**Rationale**: constitution II exige "HTTP client externo: httpx (com timeout explícito e
retry)". O retry do cliente HTTP e o redrive do SQS resolvem problemas diferentes: o primeiro
absorve uma falha de rede momentânea (ex.: um pacote perdido) sem gastar uma das 3 tentativas de
redrive da mensagem inteira; o segundo lida com indisponibilidade mais persistente da API
externa. Sem o retry do cliente, uma instabilidade de rede de meio segundo já forçaria uma
redelivery completa da mensagem.

**Alternatives considered**: sem retry no cliente (deixar 100% para o SQS) — rejeitado, gastaria
tentativas de redrive por falhas de rede triviais; biblioteca de retry externa (`tenacity`) —
rejeitada, 2 tentativas com backoff fixo não justificam uma dependência nova (constitution II
não lista `tenacity` na stack obrigatória).

## 2. Cache de catálogo com TTL

**Decision**: classe própria `CatalogoCache` (dict interno `{product_id: (produto, expires_at)}`,
usando `time.monotonic()`), TTL de 5 minutos por entrada (Clarifications). Sem biblioteca externa.

**Rationale**: `functools.lru_cache` não expira por tempo, só por tamanho — não atende ao
requisito de TTL (FR-014, decisão de Clarifications). O volume e a simplicidade do caso (um
dict com timestamp de expiração, checado na leitura) não justificam uma dependência nova como
`cachetools` — resolvido com stdlib.

**Alternatives considered**: `cachetools.TTLCache` — rejeitada, dependência nova pra um problema
de ~15 linhas de código; `functools.lru_cache` sem TTL — rejeitada, não atende à decisão de
Clarifications sobre expiração de 5min.

## 3. Validação de CPF/CNPJ (dígito verificador)

**Decision**: função pura `validar_documento(document: str) -> bool` em `domain/documento.py`,
implementando o algoritmo oficial de dígito verificador módulo 11 — primeiro pra CPF (11
dígitos), depois pra CNPJ (14 dígitos) conforme o tamanho da string. Rejeita sequências com todos
os dígitos iguais (regra padrão do algoritmo, cobre o edge case de "11111111111").

**Rationale**: FR-002, decisão de Clarifications ("dígito verificador completo"). Implementação
pura, sem dependência externa — o algoritmo é bem conhecido e cabe em poucas linhas por
documento.

**Alternatives considered**: biblioteca `validate-docbr` (ou similar) — rejeitada, dependência
nova pra um algoritmo simples de implementar diretamente; validação só de formato (11/14 dígitos)
— rejeitada pela decisão explícita de Clarifications.

## 4. Agregação de erros por pedido

**Decision**: `handlers/validar_pedido.py` monta uma lista de erros acumulando, nesta ordem: (1)
erro de documento (`domain/documento.py`), se houver; (2) para cada item, erros de
existência/estoque/quantidade mínima (um item pode gerar mais de um erro simultâneo, FR-007); (3)
só se (1) e (2) não geraram nenhum erro, calcula os totais (`domain/calculo.py`) e checa o limite
de valor (`domain/limite_total.py`) — se excedido, um único erro de pedido substitui a resposta de
aprovação. A checagem de limite de total NUNCA roda se já há erro de documento ou de item (US4
AC3) — não haveria um total válido pra comparar.

**Rationale**: FR-007/FR-009/FR-010, US2 AC3, US4 AC3. Mantém cada regra em sua própria função
pura testável isoladamente, com o handler apenas orquestrando a ordem e agregando o resultado —
consistente com constitution VIII (regra de negócio por módulo, sem I/O).

**Alternatives considered**: parar na primeira falha (documento OU primeiro item OU limite) —
rejeitado pela decisão de Clarifications ("todos os motivos do item"), que se estende
naturalmente a "todos os motivos do pedido" pela mesma lógica de dar ao cliente o quadro completo
numa única resposta.

## 5. Idempotência (reaproveitando a correção de 004-order-processor)

**Decision**: mesma estrutura de `adapters/worker_loop.py` já corrigida em
`004-order-processor`: `is_message_processed` (só leitura) checado ANTES do handler rodar;
`mark_message_processed` chamado só DEPOIS do handler concluir — com sucesso (resposta
publicada) ou com reprovação de negócio (resposta de erro publicada). Falha técnica (exceção do
`catalogo_produtos` por timeout/5xx) não marca nem confirma a mensagem.

**Rationale**: FR-013, constitution I.3. Esta feature começa já com o padrão correto — a versão
anterior (`mark_message_processed` chamado antes do handler) foi um bug real encontrado em code
review na feature `004-order-processor` (queimava mensagens em falha técnica, anulando o redrive
nativo do SQS). Não faz sentido reintroduzir o mesmo bug aqui.

**Alternatives considered**: nenhuma — a alternativa incorreta já foi tentada e corrigida em
004; não há razão pra reavaliar.

## 6. Estratégia de testes

**Decision**: testes unitários com `adapters.catalogo_produtos` mockado (via `monkeypatch`),
cobrindo cada regra de domínio isoladamente e o handler orquestrando os casos de aprovação/
reprovação/erro técnico. Um teste de integração real contra Ministack cobre o fluxo de fila
completo (publicar em `validar_pedido_queue`, consumir, publicar em
`validar_pedido_response_queue`), com o catálogo externo ainda mockado (evita flakiness/rate
limit de bater na internet real durante `pytest`). Validação manual ao vivo contra a API real do
dummyjson.com, documentada em `quickstart.md`, roda uma vez durante a implementação (mesmo padrão
de validação real usado em 003/004) — não faz parte da suíte automatizada.

**Rationale**: constitution IX exige "ao menos um teste de integração rodando contra o
Ministack" — que é sobre SQS/DynamoDB, não sobre a API pública de terceiros. Testar contra a
internet real em CI introduziria flakiness e dependência de conectividade fora do controle do
projeto (contrário ao espírito "local-first" da constitution I.6, mesmo com a exceção pontual de
chamar essa API em produção).

**Alternatives considered**: testes de integração batendo na API real do dummyjson.com —
rejeitado, flaky e lento pra rodar em toda execução de `pytest`; mockar tudo e nunca validar
contra a API real — rejeitado, a validação manual ao vivo é o que garante que o contrato
assumido (`title`/`price`/`stock`/`minimumOrderQuantity`/`availabilityStatus`/`sku`/
`discountPercentage`) realmente bate com a resposta real da API.
