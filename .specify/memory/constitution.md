<!--
Sync Impact Report
Version change: 1.0.0 → 1.0.1 (patch — correção não semântica)
Modified principles: nenhum princípio novo; seção V (Fluxo de trabalho com Git) e seção IX
  (Definição de pronto) e Governance corrigidas: `dev` → `develop`, pra bater com o nome real da
  branch de integração do repositório (o repo nunca teve uma branch `dev`). Seção V também passa a
  admitir explicitamente o commit inicial de bootstrap do repo (constitution, config do spec-kit,
  specs) direto em `develop`, por não existir ainda nenhuma branch de feature nesse momento.
Added sections: nenhuma
Removed sections: nenhuma
Templates requiring updates:
  - ✅ .specify/templates/plan-template.md — sem referência a nome de branch, sem edição necessária.
  - ✅ .specify/templates/spec-template.md — idem.
  - ✅ .specify/templates/tasks-template.md — idem.
Follow-up TODOs: nenhum.

Sync Impact Report (histórico)
Version change: TEMPLATE → 1.0.0 (initial ratification)
Modified principles: n/a (first concrete version)
Added sections:
  - I. Princípios inegociáveis (6 sub-principles: event-driven, máquina de estados, idempotência,
    DLQ obrigatória, falha é dado, local-first)
  - II. Stack obrigatória
  - III. Estrutura do monorepo
  - IV. Convenções de código
  - V. Fluxo de trabalho com Git
  - VI. Skills obrigatórias durante o desenvolvimento
  - VII. Code review obrigatório
  - VIII. Design de código Python
  - IX. Definição de pronto
  - Governance
Removed sections: generic template placeholders ([PRINCIPLE_1_NAME]..[PRINCIPLE_5_NAME], [SECTION_2],
  [SECTION_3])
Follow-up TODOs: none — RATIFICATION_DATE set to today since this is the first ratified version.
-->

# Sistema de Processamento de Pedidos Constitution

## I. Princípios inegociáveis

1. **Event-driven, nunca síncrono entre serviços.** Nenhum microserviço chama outro por HTTP.
   Toda comunicação entre componentes internos acontece por SQS. A única chamada HTTP de saída
   permitida é para a API externa de catálogo (dummyjson.com).
2. **Máquina de estados explícita.** O ciclo de vida do pedido é uma máquina de estados
   persistida no DynamoDB. Nenhum componente bloqueia esperando resposta de outro; cada
   transição é disparada por consumo de mensagem.
3. **Idempotência obrigatória.** Todo consumidor SQS deve ser idempotente. Reprocessar a mesma
   mensagem não pode duplicar pedidos, PDFs ou transições de estado. Usa-se `messageId` +
   condição de estado atual no DynamoDB (`ConditionExpression`).
4. **Toda fila tem DLQ.** `maxReceiveCount = 3`. Nenhuma fila é criada sem redrive policy.
5. **Falha é dado, não exceção silenciosa.** Toda falha de negócio grava `statusReason` no
   registro do pedido. Toda falha técnica gera log estruturado JSON e vai para DLQ.
6. **Local-first.** Todo o sistema roda 100% localmente via Ministack (https://ministack.org).
   Nenhum recurso AWS real é necessário para desenvolver ou testar.

## II. Stack obrigatória

- **Linguagem:** Python 3.12
- **Gerência de pacotes:** `uv` (um `pyproject.toml` por serviço)
- **API HTTP:** FastAPI + Uvicorn
- **Validação/serialização:** Pydantic v2 (todos os contratos de mensagem são modelos Pydantic)
- **AWS SDK:** boto3, sempre com `endpoint_url` lido de variável de ambiente
- **PDF:** ReportLab
- **HTTP client externo:** httpx (com timeout explícito e retry)
- **Testes:** pytest, pytest-asyncio, moto ou Ministack para integração
- **Lint/format:** ruff
- **Containers:** Docker + docker-compose para orquestração local
- **IaC local:** scripts de bootstrap idempotentes em `infra/bootstrap/` (boto3 ou awslocal CLI)
  que criam filas, tabelas e bucket contra o Ministack

## III. Estrutura do monorepo

```
/
├── services/
│   ├── api-gateway/          # FastAPI — entrada HTTP
│   ├── order-processor/      # ECS Processor A
│   ├── order-validator/      # ECS Validator
│   ├── pdf-generator/        # ECS PDF Generator
│   ├── file-consumer/        # ECS File Consumer
│   └── lambda-line-processor/# Lambda Processor
├── shared/
│   └── pedidos_shared/       # pacote Python: modelos Pydantic, enums de status,
│                             # clientes SQS/DynamoDB/S3, logger, parser posicional
├── infra/
│   ├── bootstrap/            # criação de filas, tabela, bucket
│   └── docker-compose.yml
├── tests/
│   └── e2e/
└── specs/                    # gerado pelo spec-kit
```

**Regra:** contratos de mensagem e o enum de status vivem SOMENTE em `shared/pedidos_shared`.
Nenhum serviço redefine um contrato localmente.

## IV. Convenções de código

- Nenhum valor de infraestrutura hardcoded: URLs de fila, nome de tabela, bucket e endpoint do
  Ministack vêm de variáveis de ambiente, carregadas por um `Settings` Pydantic em `shared`.
- Logs sempre estruturados em JSON, com `orderId` e `correlationId` em todo log de fluxo.
- Type hints obrigatórios em todas as funções públicas. `ruff` sem warnings.
- Cada serviço expõe `GET /health` (mesmo os workers, via thread HTTP simples na porta 8080).

## V. Fluxo de trabalho com Git

**Antes de escrever qualquer linha de código de uma feature**, criar uma branch nova a partir
de `develop`:

```bash
git checkout develop
git pull origin develop
git checkout -b feature/{nome-da-spec}
```

- O nome da branch é **exatamente** o nome da spec correspondente em `specs/`.
  Exemplo: a spec `001-fundacao-compartilhada` gera a branch `feature/001-fundacao-compartilhada`.
- `develop` é a branch base de integração. Nunca commitar direto em `develop` nem em `main`, exceto
  o commit inicial de bootstrap do repositório (constitution, config do spec-kit, specs — antes de
  existir qualquer branch de feature).
- Ao concluir a feature, abrir Pull Request de `feature/{nome}` para `develop`.
- O merge só acontece depois do code review descrito na seção VII.

## VI. Skills obrigatórias durante o desenvolvimento

**Implementação:** usar a skill **`fullstack-dev-skills`** correspondente à stack de cada
componente. A escolha da variante segue o tipo de serviço:

| Componente | Stack | Variante da skill |
|---|---|---|
| `api-gateway` | FastAPI + Pydantic | backend / API Python |
| `order-processor`, `order-validator`, `pdf-generator`, `file-consumer` | Python worker + boto3 | backend Python |
| `lambda-line-processor` | Python serverless | backend Python / serverless |
| `shared/pedidos_shared` | biblioteca Python | backend Python |
| `infra/` | Docker, docker-compose, boto3 | infraestrutura / DevOps |

A skill deve ser invocada **no início** da implementação de cada feature, não no final. Se a
skill não estiver disponível no ambiente, registrar isso no PR e seguir as convenções desta
constitution.

## VII. Code review obrigatório

Ao final da implementação de cada feature, **antes de abrir o PR**, executar uma revisão de
código usando a skill de code review disponível no ambiente — preferencialmente
**`code-review`** ou, se não existir, o comando `/review` do Claude Code.

O review deve cobrir, no mínimo:

1. **Aderência à constitution** — nenhuma chamada HTTP entre serviços internos, nenhum valor de
   infraestrutura hardcoded, `Decimal` em todo cálculo monetário, todo consumidor idempotente.
2. **Correção das transições de estado** — nenhuma escrita em `orders` fora do Order Processor.
3. **Tratamento de erros** — distinção clara entre erro de negócio (marca o pedido) e erro
   técnico (deixa a mensagem voltar para a fila).
4. **Design de código** — conforme a seção VIII.
5. **Cobertura de testes** — regras de negócio e caminhos de erro testados.
6. **Segurança** — sem credenciais em código, sem log de dados sensíveis do cliente
   (documento completo não vai para log; usar máscara).

Os apontamentos do review devem ser corrigidos **antes** do PR. Se algum for deliberadamente
não corrigido, justificar na descrição do PR.

## VIII. Design de código Python

**Princípio central:** cada arquivo tem uma responsabilidade. Cada classe tem uma razão para
mudar. Classes que fazem muitas coisas são o principal antipadrão a evitar neste projeto.

### Organização por funcionalidade

Separar arquivos por **o que fazem**, não por camada técnica genérica. Dentro de cada serviço:

```
services/{servico}/
├── src/{servico}/
│   ├── handlers/       # um arquivo por tipo de mensagem/endpoint
│   ├── domain/         # regras de negócio puras, sem I/O
│   ├── adapters/       # integrações externas (HTTP, S3, SQS específicos do serviço)
│   ├── config.py       # Settings do serviço
│   └── main.py         # composition root: monta as dependências e inicia
└── tests/
```

**Regras concretas:**

- Um arquivo por handler. `handlers/solicitar_pedido.py` trata apenas `solicitar_pedido_queue`.
  Não existe um `handlers.py` com cinco funções não relacionadas.
- Uma regra de negócio por módulo em `domain/`. No Validator, cada regra
  (`estoque.py`, `quantidade_minima.py`, `documento.py`, `limite_total.py`) é um módulo com uma
  função pura que recebe dados e retorna erros — sem I/O, sem boto3, sem httpx.
- `domain/` **não importa** boto3, httpx, FastAPI nem nada de infraestrutura. Regra de negócio
  é testável sem mock de rede.
- Nenhuma classe "God": se uma classe tem mais de uma responsabilidade no nome
  (`OrderManager`, `PedidoService`, `Helper`, `Utils`), é sinal de que deve ser dividida.
  Nomes como `OrderRepository`, `StockValidator`, `InvoiceRenderer` descrevem uma coisa só.
- Prefira **funções puras a classes**. Classe só quando há estado real a manter (cliente HTTP
  com pool de conexão, cache com TTL, repositório com sessão).
- Injeção de dependência explícita por construtor ou parâmetro. Nada de singleton global nem
  import com efeito colateral. O `main.py` é o único lugar que instancia clientes reais.
- Limites práticos: arquivo até ~300 linhas, função até ~50 linhas, no máximo 4 parâmetros
  posicionais (acima disso, use um dataclass ou modelo Pydantic).
- Modelos Pydantic para dados que cruzam fronteiras (mensagens, requisições, respostas);
  `dataclass` para estruturas internas.
- Exceções específicas de domínio (`InvalidTransitionError`, `ProductNotFoundError`) em vez de
  `Exception` genérica. Nunca `except Exception: pass`.
- `async` apenas onde há I/O concorrente real (FastAPI, chamadas HTTP em paralelo). Não
  transformar código síncrono em async sem ganho.

## IX. Definição de pronto

Uma feature só está pronta quando:
- Foi desenvolvida na branch `feature/{nome-da-spec}`, criada a partir de `develop`
- Testes unitários das regras de negócio passam
- Existe ao menos um teste de integração rodando contra o Ministack
- O serviço sobe via `docker-compose up` sem configuração manual adicional
- `ruff check` e `ruff format --check` passam sem apontamentos
- O code review da seção VII foi executado e os apontamentos, corrigidos
- O README do serviço documenta as variáveis de ambiente e o contrato de mensagem consumido/produzido
- O PR para `develop` foi aberto

## Governance

Esta constitution tem precedência sobre qualquer outra convenção, preferência individual ou
prática ad hoc adotada durante o desenvolvimento. Em caso de conflito entre esta constitution e
qualquer outro documento do repositório (README, comentário, template), a constitution prevalece.

**Procedimento de emenda:** qualquer alteração de princípio, seção ou regra concreta é feita
reexecutando `/speckit-constitution` com o texto atualizado. Toda emenda deve:
1. Atualizar o `Sync Impact Report` no topo deste arquivo.
2. Incrementar `CONSTITUTION_VERSION` segundo versionamento semântico:
   - **MAJOR**: remoção ou redefinição incompatível de um princípio ou seção de governance.
   - **MINOR**: adição de novo princípio/seção ou expansão material de orientação existente.
   - **PATCH**: esclarecimentos, correções de texto, refinamentos não semânticos.
3. Verificar se `.specify/templates/plan-template.md`, `spec-template.md` e `tasks-template.md`
   continuam consistentes com os princípios revisados.

**Revisão de conformidade:** todo PR passa pelo checklist da seção VII antes do merge para `develop`.
Qualquer violação de um princípio da seção I (event-driven, máquina de estados, idempotência, DLQ,
falha como dado, local-first) bloqueia o merge, salvo justificativa explícita registrada na
descrição do PR e aprovada em review.

**Complexidade:** qualquer desvio da estrutura descrita nas seções III e VIII (nova camada, novo
serviço, nova dependência fora da stack da seção II) deve ser justificado no PR — a alternativa
mais simples rejeitada e o motivo.

**Version**: 1.0.1 | **Ratified**: 2026-07-18 | **Last Amended**: 2026-07-18
