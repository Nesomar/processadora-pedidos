# Feature Specification: Order Validator

**Feature Branch**: `005-order-validator`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "order-validator: serviço worker Python que consome validar_pedido_queue (payload: customer_document, items com product_id/quantity), consulta a API externa de produtos dummyjson.com (GET /products/{id}) pra cada item, valida disponibilidade (stock/availabilityStatus) e quantidade mínima (minimumOrderQuantity), calcula preço unitário oficial/desconto/line_total por item e subtotal/discount_total/total do pedido, e publica o resultado em validar_pedido_response_queue (approved=true com enriched_items+totais, ou approved=false com errors[] e totais nulos). Erro de negócio (produto inexistente, HTTP 404, ou regra de validação reprovada) gera approved=false com errors[]; erro técnico (timeout/5xx da API externa) NÃO responde a fila — mensagem fica disponível pro redrive nativo do SQS, até 3 tentativas antes de DLQ. Cache em memória do catálogo de produtos. Idempotente via mark_message_processed. Nunca escreve na tabela orders."

## Clarifications

### Session 2026-07-20

- Q: Cache de produtos em memória: TTL fixo ou sem expiração (até reiniciar o processo)? → A: TTL
  curto, 5 minutos — equilibra performance com risco de dado desatualizado.
- Q: Item reprovado por mais de um motivo ao mesmo tempo — reportar só o primeiro ou todos os
  motivos daquele item? → A: Todos os motivos do item (lista completa de erros por item).
- Q: Constitution VIII cita módulos `documento.py` e `limite_total.py` sem regra especificada em
  `docs/01-dominio-e-contratos.md` — são exemplo ilustrativo de organização de código ou regras
  de negócio reais faltando na spec? → A: São regras reais faltando; adicionadas como US2 e US4
  abaixo.
- Q: Validação de `customer_document` (CPF/CNPJ) — só formato (11/14 dígitos) ou dígito
  verificador completo? → A: Dígito verificador completo (algoritmo oficial módulo 11 de
  CPF/CNPJ).
- Q: Limite máximo de valor total do pedido — qual valor e comportamento ao exceder? → A: R$
  100.000,00; pedido é reprovado (erro `ORDER_TOTAL_EXCEEDS_LIMIT`), não apenas sinalizado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Aprovar pedido com itens disponíveis (Priority: P1)

Um pedido chega para validação com itens cujos produtos existem, têm estoque suficiente e
respeitam a quantidade mínima de compra. O serviço consulta o catálogo, confirma que tudo está
correto, calcula o preço oficial e o desconto de cada item, soma os totais do pedido, e informa
que o pedido foi aprovado com os dados enriquecidos.

**Why this priority**: É o caminho principal — sem aprovação, nenhum pedido chega à emissão de
nota fiscal. Sem isso não há MVP.

**Independent Test**: Publicar uma mensagem de validação com itens válidos (produto existente,
estoque e quantidade mínima respeitados, documento válido, total dentro do limite) e confirmar
que a resposta tem `approved=true`, os itens enriquecidos com preço/desconto/total e os totais do
pedido calculados corretamente.

**Acceptance Scenarios**:

1. **Given** um pedido com um item cujo produto existe, tem estoque suficiente e quantidade acima
   do mínimo, **When** o serviço processa a validação, **Then** a resposta tem `approved=true`,
   o item enriquecido com `unit_price`, `discount_percentage`, `line_total`, `product_title` e
   `product_sku`, e o pedido com `subtotal`, `discount_total` e `total` calculados.
2. **Given** um pedido com múltiplos itens, todos válidos, **When** o serviço processa a
   validação, **Then** `subtotal` é a soma de `quantity * unit_price` de todos os itens,
   `total` é a soma de todos os `line_total`, e `discount_total` é a diferença entre os dois.

---

### User Story 2 - Reprovar pedido com documento do cliente inválido (Priority: P1)

Um pedido chega com `customer_document` que não é um CPF ou CNPJ válido (formato incorreto ou
dígito verificador inválido). O serviço reprova o pedido antes mesmo de consultar o catálogo de
produtos.

**Why this priority**: É uma regra de negócio fundamental e barata de checar (não depende da API
externa) — sem ela, pedidos com documento inválido seguiriam para emissão de nota fiscal.

**Independent Test**: Publicar uma mensagem de validação com `customer_document` estruturalmente
inválido (tamanho errado) ou com dígito verificador incorreto, e confirmar que a resposta tem
`approved=false` com erro de código `INVALID_DOCUMENT`, sem itens calculados.

**Acceptance Scenarios**:

1. **Given** um pedido cujo `customer_document` não tem 11 (CPF) nem 14 (CNPJ) dígitos, **When**
   o serviço processa a validação, **Then** a resposta tem `approved=false` com erro de código
   `INVALID_DOCUMENT` (sem `product_id` associado, é um erro do pedido como um todo).
2. **Given** um pedido cujo `customer_document` tem o tamanho certo (11 ou 14 dígitos) mas o
   dígito verificador não confere com o algoritmo oficial de CPF/CNPJ (módulo 11), **When** o
   serviço processa a validação, **Then** a resposta tem `approved=false` com erro de código
   `INVALID_DOCUMENT`.
3. **Given** um pedido com documento inválido E pelo menos um item também reprovado, **When** o
   serviço processa a validação, **Then** a resposta contém o erro `INVALID_DOCUMENT` junto com
   os erros dos itens reprovados, na mesma lista (agregação de todos os motivos, ver US3 AC4).

---

### User Story 3 - Reprovar pedido com item indisponível ou abaixo do mínimo (Priority: P1)

Um pedido chega com um item cujo produto não tem estoque suficiente para a quantidade pedida, ou
cuja quantidade pedida é menor que a quantidade mínima de compra exigida pelo produto. O serviço
reprova o pedido, explicando o motivo de forma específica por item.

**Why this priority**: É a regra de negócio central do serviço — sem ela, pedidos inválidos
seguiriam para emissão de nota fiscal.

**Independent Test**: Publicar uma mensagem de validação com um item cuja quantidade é menor que
o mínimo exigido (ou maior que o estoque disponível) e confirmar que a resposta tem
`approved=false`, com um erro específico identificando o produto e o motivo, e nenhum total
calculado.

**Acceptance Scenarios**:

1. **Given** um pedido com um item cuja quantidade é menor que `minimumOrderQuantity` do produto,
   **When** o serviço processa a validação, **Then** a resposta tem `approved=false`, com um erro
   de código `BELOW_MINIMUM_ORDER_QUANTITY` referenciando o `product_id` e a mensagem indicando o
   mínimo exigido, e `enriched_items`/`subtotal`/`discount_total`/`total` nulos.
2. **Given** um pedido com um item cuja quantidade excede o estoque disponível (`stock`) ou cujo
   produto está `Out of Stock`, **When** o serviço processa a validação, **Then** a resposta tem
   `approved=false`, com um erro de código `INSUFFICIENT_STOCK` referenciando o `product_id`.
3. **Given** um pedido com múltiplos itens reprovados por motivos diferentes, **When** o serviço
   processa a validação, **Then** a resposta contém um erro para cada item reprovado (não só o
   primeiro encontrado).
4. **Given** um item que viola mais de uma regra simultaneamente (ex.: quantidade abaixo do
   mínimo E acima do estoque disponível), **When** o serviço processa a validação, **Then** a
   resposta contém um erro para cada regra violada por aquele item (não só o primeiro
   encontrado) — exceto quando o produto não existe, caso em que só o erro `PRODUCT_NOT_FOUND`
   se aplica (as demais regras dependem de dados do produto que não existem).

---

### User Story 4 - Reprovar pedido que excede o limite de valor total (Priority: P1)

Um pedido com todos os itens e documento válidos tem, ainda assim, um valor total (`total`) acima
do limite máximo permitido. O serviço reprova o pedido mesmo que cada item individualmente esteja
correto.

**Why this priority**: Regra de negócio de proteção contra erro grosseiro ou fraude em pedidos de
valor muito alto — junto com estoque/quantidade mínima, compõe o conjunto de regras que decidem
se um pedido pode seguir para emissão de nota fiscal.

**Independent Test**: Publicar uma mensagem de validação cujos itens, uma vez precificados,
resultam em `total` acima de R$ 100.000,00, e confirmar que a resposta é `approved=false` com
erro de código `ORDER_TOTAL_EXCEEDS_LIMIT`, mesmo com todos os itens e o documento válidos.

**Acceptance Scenarios**:

1. **Given** um pedido cujo documento é válido e todos os itens são individualmente aprováveis,
   mas a soma dos `line_total` (`total`) ultrapassa R$ 100.000,00, **When** o serviço processa a
   validação, **Then** a resposta tem `approved=false` com erro de código
   `ORDER_TOTAL_EXCEEDS_LIMIT` (sem `product_id` associado, é um erro do pedido como um todo), e
   `enriched_items`/`subtotal`/`discount_total`/`total` nulos.
2. **Given** um pedido cujo `total` calculado é igual ou menor que R$ 100.000,00, **When** o
   serviço processa a validação, **Then** essa regra não impede a aprovação (o limite é
   exclusivo, `> 100000.00` reprova, `<= 100000.00` não).
3. **Given** um pedido com pelo menos um item já reprovado por outro motivo (estoque, quantidade
   mínima, produto inexistente), **When** o serviço processa a validação, **Then** a checagem de
   limite de total não se aplica (não há um `total` válido pra comparar) — só os erros dos itens
   e/ou documento aparecem na resposta.

---

### User Story 5 - Reprovar pedido com produto inexistente (Priority: P2)

Um pedido chega com um item referenciando um `product_id` que não existe no catálogo externo. O
serviço trata isso como reprovação de negócio, não como falha técnica.

**Why this priority**: Já é coberto pela mesma resposta de reprovação da US3, mas precisa de
tratamento explícito porque a origem do erro (API externa retorna 404) é diferente das outras
reprovações e não pode ser confundida com uma falha técnica.

**Independent Test**: Publicar uma mensagem de validação referenciando um `product_id`
inexistente e confirmar que a resposta é `approved=false` com erro de código `PRODUCT_NOT_FOUND`,
sem a mensagem ser reencaminhada para nova tentativa.

**Acceptance Scenarios**:

1. **Given** um pedido com um item cujo `product_id` não existe no catálogo (a consulta externa
   responde "não encontrado"), **When** o serviço processa a validação, **Then** a resposta tem
   `approved=false` com erro de código `PRODUCT_NOT_FOUND` referenciando o `product_id`, e a
   mensagem original é confirmada (não fica disponível para nova tentativa).

---

### User Story 6 - Preservar disponibilidade diante de falha técnica da API externa (Priority: P2)

A consulta ao catálogo externo falha por timeout ou erro do servidor (não por o produto não
existir). O serviço não deve responder com uma decisão de negócio errada — deve permitir que a
mensagem seja reprocessada mais tarde.

**Why this priority**: Sem essa distinção, uma instabilidade temporária da API externa reprovaria
pedidos válidos permanentemente, ou pior, aprovaria pedidos sem validação real.

**Independent Test**: Simular uma falha técnica (timeout ou erro 5xx) na consulta ao catálogo e
confirmar que nenhuma resposta de validação é publicada, e que a mensagem original permanece
disponível para nova tentativa.

**Acceptance Scenarios**:

1. **Given** a consulta ao catálogo externo falha por timeout ou erro 5xx, **When** o serviço
   tenta processar a validação, **Then** nenhuma mensagem é publicada em
   `validar_pedido_response_queue`, e a mensagem original não é confirmada — ficando disponível
   para nova tentativa pelo mecanismo nativo de reentrega.
2. **Given** a mesma falha técnica persiste por 3 tentativas consecutivas, **When** o limite de
   tentativas é esgotado, **Then** a mensagem original é encaminhada para a fila de mensagens
   mortas, sem gerar uma resposta de validação incorreta.

---

### User Story 7 - Reduzir consultas repetidas ao catálogo externo (Priority: P3)

O mesmo produto aparece em vários itens de um pedido, ou em pedidos diferentes processados em
sequência. O serviço evita consultar a API externa mais de uma vez para o mesmo produto dentro
de uma janela razoável de tempo.

**Why this priority**: Otimização de desempenho e redução de carga na API externa — não afeta a
corretude do resultado, só a eficiência.

**Independent Test**: Publicar duas mensagens de validação referenciando o mesmo `product_id` e
confirmar (via contagem de chamadas à API externa, observável em teste) que a segunda consulta
não gera uma nova chamada externa.

**Acceptance Scenarios**:

1. **Given** um produto já consultado recentemente, **When** um novo pedido referencia o mesmo
   `product_id`, **Then** o serviço usa o dado em cache em vez de consultar a API externa de
   novo.

---

### User Story 8 - Reprocessar a mesma mensagem sem duplicar resposta (Priority: P3)

A mesma mensagem de validação é entregue mais de uma vez (reentrega natural de fila). O serviço
não deve consultar o catálogo nem publicar uma segunda resposta.

**Why this priority**: Garantia de sistema (idempotência), não um comportamento que o negócio
percebe diretamente no dia a dia — mas necessária para não gerar respostas duplicadas rio abaixo.

**Independent Test**: Publicar a mesma mensagem de validação duas vezes (mesmo `message_id`) e
confirmar que apenas uma resposta é publicada em `validar_pedido_response_queue`.

**Acceptance Scenarios**:

1. **Given** uma mensagem de validação já processada com sucesso, **When** a mesma mensagem
   (mesmo `message_id`) é entregue de novo, **Then** nenhuma nova consulta ao catálogo externo
   ocorre e nenhuma nova resposta é publicada — a mensagem é apenas confirmada.

---

### Edge Cases

- Pedido sem itens: não se espera (o Order Processor garante 1..50 itens antes de publicar),
  mas se ocorrer é tratado como falha técnica (payload malformado), não como reprovação.
- Item com `product_id` repetido dentro do mesmo pedido: cada ocorrência é validada e calculada
  independentemente (não há deduplicação de itens).
- API externa retorna dado parcial ou campo essencial ausente (ex.: `minimumOrderQuantity`
  ausente): tratado como falha técnica, mensagem não confirmada.
- Produto com `availabilityStatus = "Low Stock"` mas `stock` suficiente para a quantidade pedida:
  aprovado normalmente — `availabilityStatus` só bloqueia quando é `"Out of Stock"`.
- `customer_document` com todos os dígitos iguais (ex.: "11111111111"): estruturalmente do
  tamanho certo mas reprovado pelo dígito verificador (regra padrão do algoritmo oficial de
  CPF, que rejeita sequências repetidas).
- Pedido com total exatamente igual a R$ 100.000,00: aprovado (o limite é `>`, não `>=`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE consumir mensagens de `validar_pedido_queue` contendo
  `customer_document` e uma lista de itens (`product_id`, `quantity`).
- **FR-002**: O sistema DEVE validar que `customer_document` é um CPF (11 dígitos) ou CNPJ (14
  dígitos) com dígito verificador válido segundo o algoritmo oficial (módulo 11); caso contrário,
  reprova o pedido com erro de código `INVALID_DOCUMENT` (sem `product_id` associado).
- **FR-003**: Para cada item do pedido, o sistema DEVE consultar o catálogo externo de produtos
  pelo `product_id` para obter `title`, `price`, `stock`, `minimumOrderQuantity`,
  `availabilityStatus`, `sku` e `discountPercentage`.
- **FR-004**: O sistema DEVE reprovar o pedido (item específico) quando o produto referenciado
  não existir no catálogo externo, com erro de código `PRODUCT_NOT_FOUND`.
- **FR-005**: O sistema DEVE reprovar o pedido (item específico) quando a quantidade pedida for
  menor que a `minimumOrderQuantity` do produto, com erro de código
  `BELOW_MINIMUM_ORDER_QUANTITY`.
- **FR-006**: O sistema DEVE reprovar o pedido (item específico) quando a quantidade pedida
  exceder o `stock` disponível ou quando o produto estiver com `availabilityStatus = "Out of
  Stock"`, com erro de código `INSUFFICIENT_STOCK`.
- **FR-007**: Quando o documento for inválido e/ou um ou mais itens forem reprovados, o sistema
  DEVE publicar uma resposta com `approved=false`, contendo um erro (`code`, `product_id`,
  `message`) para CADA regra violada — um item pode gerar mais de um erro se violar mais de uma
  regra simultaneamente (exceto `PRODUCT_NOT_FOUND`, que exclui as demais checagens daquele item
  por falta de dado) — e `enriched_items`/`subtotal`/`discount_total`/`total` nulos.
- **FR-008**: Quando o documento for válido e todos os itens forem aprovados, o sistema DEVE
  calcular por item: `unit_price` (preço oficial do catálogo), `discount_percentage` (do
  catálogo), `line_total` (`quantity * unit_price * (1 - discount_percentage/100)`),
  `product_title` e `product_sku`; e para o pedido: `subtotal` (soma de `quantity * unit_price`
  de todos os itens), `total` (soma de todos os `line_total`) e `discount_total`
  (`subtotal - total`).
- **FR-009**: Depois de calculado o `total` (FR-008), o sistema DEVE reprovar o pedido inteiro
  quando `total > 100000.00`, com erro de código `ORDER_TOTAL_EXCEEDS_LIMIT` (sem `product_id`
  associado) e `enriched_items`/`subtotal`/`discount_total`/`total` nulos na resposta.
- **FR-010**: Quando o documento for válido, todos os itens forem aprovados e o `total` não
  exceder o limite (FR-009), o sistema DEVE publicar uma resposta com `approved=true` e os dados
  calculados de FR-008.
- **FR-011**: O sistema DEVE publicar a resposta em `validar_pedido_response_queue`, preservando
  `order_id` e `correlation_id` da mensagem original.
- **FR-012**: Quando a consulta ao catálogo externo falhar por erro técnico (timeout ou erro
  5xx) — não por produto inexistente —, o sistema NÃO DEVE publicar resposta de validação nem
  confirmar a mensagem original, permitindo reentrega pelo mecanismo nativo de fila.
- **FR-013**: O sistema DEVE ser idempotente: reprocessar a mesma mensagem (mesmo `message_id`)
  não deve gerar uma nova consulta ao catálogo nem uma nova resposta publicada.
- **FR-014**: O sistema DEVE manter em memória um cache do catálogo consultado, evitando
  consultas repetidas ao mesmo `product_id`, com expiração de 5 minutos por entrada — equilíbrio
  entre reduzir chamadas externas e não servir preço/estoque desatualizado por muito tempo.
- **FR-015**: O sistema NÃO DEVE escrever na tabela de pedidos — sua única saída é a resposta de
  validação publicada em fila.
- **FR-016**: O sistema DEVE expor um endpoint de verificação de saúde, mesmo não expondo uma
  API de negócio.

### Key Entities

- **Item de pedido (entrada)**: `product_id`, `quantity` — dados mínimos recebidos para
  validação.
- **Item de pedido (enriquecido, saída)**: item de entrada mais `unit_price`,
  `discount_percentage`, `line_total`, `product_title`, `product_sku` — presente só quando o
  pedido é aprovado.
- **Erro de validação**: `code` (categoria do motivo de reprovação), `product_id` (item
  relacionado, nulo para erros do pedido como um todo — `INVALID_DOCUMENT`,
  `ORDER_TOTAL_EXCEEDS_LIMIT`), `message` (descrição legível do motivo).
- **Produto (catálogo externo, referência)**: `id`, `title`, `price`, `stock`,
  `minimumOrderQuantity`, `availabilityStatus`, `sku`, `discountPercentage` — consultado, nunca
  persistido pelo sistema.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos pedidos com documento válido e todos os itens disponíveis, dentro da
  quantidade mínima e do limite de total são aprovados com totais corretamente calculados.
- **SC-002**: 100% dos pedidos com documento inválido, item indisponível, abaixo do mínimo,
  inexistente, ou total acima do limite são reprovados com um erro específico e compreensível
  por motivo de reprovação.
- **SC-003**: Nenhuma instabilidade temporária da API externa de catálogo (timeout, erro 5xx)
  resulta em uma decisão de validação incorreta — a mensagem é sempre reprocessada até estabilizar
  ou esgotar as tentativas.
- **SC-004**: Reprocessar a mesma mensagem de validação nunca gera mais de uma resposta
  publicada.
- **SC-005**: Consultas repetidas ao mesmo produto, durante o processamento corrente, não geram
  chamadas adicionais à API externa.

## Assumptions

- A API externa de catálogo (`https://dummyjson.com`) é tratada como estável o suficiente para
  uso em ambiente local/teste; em produção, a URL viria de configuração (assumido, sem
  necessidade de mudança de código).
- Cache em memória é por processo (não compartilhado entre réplicas), com TTL de 5 minutos por
  entrada (ver Clarifications).
- O payload de `validar_pedido_queue` já vem validado estruturalmente pelo Order Processor
  (contrato existente); este serviço não precisa validar formato de payload, só regras de
  negócio sobre o conteúdo.
- Os códigos de erro `PRODUCT_NOT_FOUND`, `INSUFFICIENT_STOCK`, `INVALID_DOCUMENT` e
  `ORDER_TOTAL_EXCEEDS_LIMIT` são definidos por este serviço como extensão razoável do único
  código já documentado (`BELOW_MINIMUM_ORDER_QUANTITY`), já que o domínio não especifica os
  demais códigos explicitamente.
- O limite de R$ 100.000,00 (FR-009) é fixo no código desta versão (não configurável por
  variável de ambiente) — decisão registrada em Clarifications; se precisar variar por ambiente,
  é uma mudança futura de escopo.
