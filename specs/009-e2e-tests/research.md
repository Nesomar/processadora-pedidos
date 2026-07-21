# Research: Suite de Testes End-to-End

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## 1. Localização e empacotamento da suíte

**Decision**: `tests/e2e/` na raiz do repo, **sem** `pyproject.toml` próprio — não é um membro do
workspace uv (`pyproject.toml` raiz já lista `members = ["services/*", "shared/pedidos_shared",
"infra/bootstrap"]`). A suíte importa `pedidos_shared` diretamente (já uma dependência de todo o
workspace) e usa `httpx` (já declarado como dependência principal, não dev, em
`order-validator`/`lambda-line-processor` — presente no ambiente compartilhado depois de qualquer
`uv sync --all-packages`). `pytest` precisa estar sincronizado no ambiente compartilhado (mesma
pré-condição que `make test` já assume hoje — não é um requisito novo desta feature).

**Rationale**: `make e2e` já roda `uv run --all-packages pytest tests/e2e` (Makefile existente,
`002-infraestrutura-local`) — a estrutura assume que `tests/e2e` é um diretório de testes solto,
não um pacote. Criar um `pyproject.toml` próprio duplicaria dependências (`httpx`, `pytest`) já
resolvidas em outros membros do workspace, sem necessidade.

**Alternatives considered**: `tests/e2e` como membro do workspace com seu próprio
`pyproject.toml` — rejeitado, o `Makefile` já não espera isso (`uv run --all-packages`, não
`uv run --package e2e-tests`), e duplicaria `httpx`/`pytest` sem ganho.

## 2. Espera por processamento assíncrono

**Decision**: helper `poll_until(fn, timeout=30.0, interval=0.5, description="") -> T` em
`tests/e2e/_poll.py` — chama `fn()` repetidamente até devolver um valor não-`None`/verdadeiro ou
estourar o tempo limite; no timeout, levanta `AssertionError` incluindo `description` e o último
valor observado (FR-006). Tempo limite default de 30s, abaixo do teto de 60s por cenário (SC-002).

**Rationale**: FR-003/FR-006. Mesmo padrão de poll curto já usado manualmente nas validações desta
sessão (`sleep`/retry entre features) — só formalizado como helper reutilizável, com mensagem de
erro que identifica o que estava sendo esperado.

**Alternatives considered**: biblioteca de retry externa (`tenacity`) — rejeitada, mesma razão de
`005-order-validator`/`008-lambda-line-processor`: não está na stack obrigatória e o caso de uso
(poll com intervalo fixo) não justifica a dependência.

## 3. Checagem rápida de ambiente fora do ar

**Decision**: fixture `session`-scoped e `autouse` em `tests/e2e/conftest.py` que faz `GET /health`
(timeout curto, ~2s) nos 6 serviços antes de qualquer teste rodar; se algum falhar, a suíte inteira
para imediatamente (`pytest.exit`) com uma mensagem nomeando o serviço inacessível — não deixa cada
cenário individual estourar seu próprio tempo limite de 30s à toa (SC-004).

**Rationale**: FR-006/SC-004 — falhar em segundos, não em minutos, quando o ambiente não está no
ar. As portas dos 6 serviços já são fixas e documentadas (`README.md`/`CLAUDE.md`): `8000`
api-gateway, `8080` order-processor, `8081` order-validator, `8082` pdf-generator, `8083`
file-consumer, `8084` lambda-line-processor.

**Alternatives considered**: deixar cada cenário falhar no seu próprio tempo limite sem checagem
prévia — rejeitado, violaria SC-004 diretamente (falharia em até 30s por cenário, não em segundos
no total).

## 4. Upload de arquivo posicional parametrizável

**Decision**: pequeno builder local `tests/e2e/_file_builder.py` (mesma lógica de
`_record`/`_order_record`/`_item_record` já usada nos testes de `007-file-consumer`/
`shared/pedidos_shared/tests/test_file_layout.py`), permitindo gerar um arquivo válido com um
`customer_id` único por execução — diferente de `infra/bootstrap/seed_file.py`, que gera sempre o
mesmo `CUST00001` fixo (adequado para `make seed-file` manual, não para um teste que precisa de
unicidade por execução, FR-004).

**Rationale**: FR-004 exige identificadores únicos por cenário para não colidir entre execuções.
Reaproveitar `seed_file.py` diretamente geraria sempre o mesmo `customer_id`, quebrando SC-003.

**Alternatives considered**: reaproveitar `seed_file.py` como está — rejeitado, não parametriza
`customer_id`; modificar `seed_file.py` para aceitar parâmetros — rejeitado, misturaria a
responsabilidade de `make seed-file` (gerar UM exemplo fixo pra demonstração manual) com a de gerar
dados únicos por teste automatizado.

## 5. Dados de exemplo (produto, CPF válido/inválido)

**Decision**: reaproveita os mesmos dados já validados contra o catálogo real (`dummyjson.com`) e
o algoritmo de CPF nas features anteriores: `product_id=1` (`"Essence Mascara Lash Princess"`),
quantidade `50` (acima do `minimumOrderQuantity=48` real, confirmado em `005-order-validator`);
CPF válido `52998224725` (já usado em validações manuais de `005`/`006`/`007`/`008`); CPF inválido
`11111111111` (dígitos repetidos, já usado nos testes de `order-validator`).

**Rationale**: evita redescobrir por tentativa e erro quais valores passam pela validação real do
catálogo externo — já são conhecidos e estáveis desde `005-order-validator`.

**Alternatives considered**: nenhuma — reaproveitamento direto de valores já validados.

## 6. Sem `contracts/` nesta feature

**Decision**: esta feature não gera `contracts/*.md` — ela consome contratos já existentes e
documentados (`docs/01-dominio-e-contratos.md`, `api_gateway/schemas.py`), sem introduzir nenhuma
interface nova.

**Rationale**: o próprio template do plano permite pular `contracts/` quando não há interface nova
exposta pelo projeto; a suíte é consumidora, não produtora, de contrato.
