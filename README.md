# Sistema de Processamento de Pedidos

Sistema de processamento assíncrono e orientado a eventos, com duas portas de entrada — um
cliente HTTP e upload em lote de arquivo posicional `.txt` — que convergem no mesmo pipeline de
processamento, validação e emissão de nota fiscal em PDF. Roda 100% local via
[Ministack](https://ministack.org) (emulador AWS), sem depender de nenhum recurso AWS real.

## Arquitetura

```
[cliente HTTP] ──────────────┐
                             ▼
[arquivo .txt] → S3 → s3_notifications_queue → File Consumer
                                                    │
                                          pedido_lines_queue
                                                    │
                                            Lambda Line Processor
                                                    │
                                                    ▼
                                            ╔═══════════════╗
                                            ║  API Gateway  ║
                                            ╚═══════════════╝
                                                    │
              ┌─────────────────┬───────────────────┤
              ▼                 ▼                   ▼
    solicitar_pedido_q   editar_pedido_q    cancelar_pedido_q
              └─────────────────┴───────────────────┘
                                │
                                ▼
                    ╔═══════════════════════╗
                    ║   Order Processor     ║◄──── validar_pedido_response_queue
                    ║   (orquestrador)      ║◄──── pdf_response_queue
                    ╚═══════════════════════╝
                          │              │
              validar_pedido_q     pdf_request_queue
                          │              │
                          ▼              ▼
                    Validator      PDF Generator → S3 (nota fiscal)
```

O **Order Processor** é o único serviço que escreve na tabela `orders` e o único dono da máquina
de estados do pedido; os demais serviços validam, renderizam ou repassam mensagens e nunca se
chamam diretamente por HTTP, com duas exceções documentadas: o Order Validator consultando o
catálogo externo `dummyjson.com`, e o Lambda Line Processor chamando o API Gateway (a porta de
entrada HTTP única do sistema, tanto pro fluxo online quanto pro batch).

Contrato de domínio completo (entidades, máquina de estados, payloads de fila, layout do arquivo
posicional, schema DynamoDB): [`docs/01-dominio-e-contratos.md`](docs/01-dominio-e-contratos.md).
Convenções de arquitetura, stack e fluxo de desenvolvimento: [`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## Serviços

| Serviço | Papel | Porta |
|---|---|---|
| `api-gateway` | Entrada HTTP síncrona; publica comandos nas filas | `8000` |
| `order-processor` | Orquestrador central da máquina de estados do pedido | `8080` |
| `order-validator` | Valida documento, estoque, quantidade mínima e limite de total | `8081` |
| `pdf-generator` | Gera e armazena a nota fiscal em PDF | `8082` |
| `file-consumer` | Consome upload de arquivo posicional e publica linha a linha | `8083` |
| `lambda-line-processor` | Transforma cada linha do arquivo numa chamada ao API Gateway | `8084` |

Cada serviço expõe `GET /health`. Contratos de fila consumida/publicada e variáveis de ambiente
de cada um estão no `README.md` do respectivo diretório em `services/`.

## Stack

Python 3.12, `uv` (um `pyproject.toml` por serviço em workspace), FastAPI (API Gateway),
Pydantic v2 (contratos de mensagem), boto3 (SQS/DynamoDB/S3 via Ministack), ReportLab (PDF), httpx
(única chamada HTTP externa permitida), pytest, ruff, Docker/docker-compose.

## Rodando localmente

Pré-requisitos: Docker, `uv`, `make`. Os exemplos de linha de comando abaixo assumem um shell
POSIX (Git Bash, WSL, Linux, macOS); no PowerShell use `curl.exe` no lugar de `curl`, senão o
alias do `Invoke-WebRequest` é chamado e as opções não batem.

```bash
cp .env.example .env    # ajuste se necessário
make up                 # sobe Ministack + bootstrap (filas/tabelas/bucket) + todos os serviços
```

O `make up` é a única coisa necessária: o container `bootstrap` roda uma vez, cria as 9 filas
(com DLQ), as 2 tabelas, o bucket e a notificação `s3:ObjectCreated` do prefixo `uploads/`, e sai.
Os 6 serviços sobem em seguida. Para conferir que tudo respondeu:

```bash
for p in 8000 8080 8081 8082 8083 8084; do curl -s http://localhost:$p/health; echo; done
# {"status":"ok"} seis vezes
```

```bash
make down        # derruba o ambiente
```

## Testando localmente

Todos os comandos desta seção rodam com o ambiente no ar (`make up`) e usam os arquivos prontos de
[`examples/`](examples/):

| Arquivo | Serve para |
|---|---|
| `pedido-valido.json` | `POST /pedidos` — caminho feliz, termina em `COMPLETED` com nota fiscal |
| `pedido-documento-invalido.json` | `POST /pedidos` — CPF com dígitos repetidos, termina em `REJECTED` |
| `pedido-editado.json` | `PUT /pedidos/{order_id}` — corrige o documento e muda a quantidade |
| `cancelamento.json` | `POST /pedidos/{order_id}/cancelamento` |
| `arquivo-valido.txt` | Upload batch — 1 pedido válido, termina em `COMPLETED` |
| `arquivo-com-erros.txt` | Upload batch — 1 pedido válido + 1 com `item_count` divergente (só o segundo é descartado) |
| `arquivo-invalido.txt` | Upload batch — contadores do trailer divergentes, **arquivo inteiro** rejeitado |

### Fluxo online (HTTP)

**1. Criar um pedido.** A API é assíncrona: ela valida o payload, publica o comando em
`solicitar_pedido_queue` e devolve `202` — o registro ainda não existe neste instante.

```bash
curl -s -X POST http://localhost:8000/pedidos \
  -H "Content-Type: application/json" -d @examples/pedido-valido.json
# {"order_id":"90e305d4-...","correlation_id":"2992a10f-..."}
```

**2. Consultar até o estado final.** Todo o pipeline (validação no catálogo externo, cálculo de
totais, geração do PDF) leva alguns segundos; até o Order Processor consumir a fila, o `GET`
responde `404`.

```bash
curl -s http://localhost:8000/pedidos/<order_id>
```

```json
{
  "status": "COMPLETED",
  "customer_document": "*******4725",
  "items": [{ "product_id": 1, "quantity": 50, "unit_price": "9.99",
              "line_total": "447.15", "product_title": "Essence Mascara Lash Princess" }],
  "subtotal": "499.50", "discount_total": "52.35", "total": "447.15",
  "invoice_available": true,
  "version": 2
}
```

Preço, desconto, título e SKU vêm do catálogo externo (`dummyjson.com`) preenchidos pelo Order
Validator; `customer_document` sempre sai mascarado. Use `GET /pedidos?customerId=<id>` para
listar por cliente.

Com `invoice_available: true`, baixe a nota fiscal direto pelo gateway (o S3 não é exposto):

```bash
curl -o nota.pdf http://localhost:8000/pedidos/<order_id>/nota-fiscal
```

Sem PDF: `404` (pedido inexistente ou PDF ausente), `409` (ainda em processamento, tente de novo),
`410` (`REJECTED`/`FAILED`/`CANCELLED` — nenhum PDF será gerado).

**3. Rejeição de negócio.** Com `pedido-documento-invalido.json` o pedido chega a `REJECTED` com o
motivo preenchido — e a mensagem é confirmada na fila, porque reprocessar nunca mudaria o
resultado:

```bash
curl -s -X POST http://localhost:8000/pedidos \
  -H "Content-Type: application/json" -d @examples/pedido-documento-invalido.json
# depois, no GET:
# "status": "REJECTED"
# "status_reason": "customer_document '*******1111' nao e um CPF/CNPJ valido"
```

Outras rejeições possíveis: `INSUFFICIENT_STOCK`, `BELOW_MINIMUM_ORDER_QUANTITY`,
`PRODUCT_NOT_FOUND` e `ORDER_TOTAL_EXCEEDS_LIMIT` (total acima de `100000.00`).

**4. Editar.** Só é aceito se o status atual permitir voltar a `PROCESSING` (`RECEIVED`,
`VALIDATED` ou `REJECTED`); caso contrário, `409`. A edição reinicia o ciclo de validação:

```bash
curl -s -X PUT http://localhost:8000/pedidos/<order_id> \
  -H "Content-Type: application/json" -d @examples/pedido-editado.json
# 202 — e o GET seguinte mostra "status":"COMPLETED" com o `version` maior que o anterior
```

Ao acompanhar uma edição, repare no `version`, não só no status: o status terminal do ciclo
anterior (`REJECTED`, por exemplo) continua lá até o novo ciclo terminar.

**5. Cancelar.** Vale enquanto o pedido não entrou em `INVOICING` — depois disso, `409`. Como o
caminho feliz completa em poucos segundos, mande o cancelamento assim que o registro existir:

```bash
OID=$(curl -s -X POST http://localhost:8000/pedidos \
        -H "Content-Type: application/json" -d @examples/pedido-valido.json \
      | python -c "import sys,json;print(json.load(sys.stdin)['order_id'])")

until curl -sf -o /dev/null http://localhost:8000/pedidos/$OID; do sleep 0.2; done

curl -s -X POST http://localhost:8000/pedidos/$OID/cancelamento \
  -H "Content-Type: application/json" -d @examples/cancelamento.json
# 202 — e o GET seguinte mostra "status":"CANCELLED"
```

O `status_reason` do pedido cancelado costuma registrar a resposta de validação que chegou depois
do cancelamento e foi descartada (`CANCELLED não pode ir para VALIDATED`) — comportamento
esperado, não erro.

**6. Payload inválido.** `customer_id` não alfanumérico ou com mais de 20 caracteres,
`customer_document` com qualquer caractere não numérico, lista de itens vazia/acima de 50 itens ou
`quantity` menor ou igual a zero são barrados **antes** de qualquer fila, com `400` e a mensagem no
campo `detail`.

### Fluxo batch (arquivo posicional)

`make upload` envia um arquivo local para `uploads/` no bucket, com um sufixo aleatório na chave —
reenviar o mesmo exemplo várias vezes sempre gera um novo evento, sem esbarrar na idempotência.

```bash
make upload FILE=examples/arquivo-valido.txt
# seed-file: enviado s3://pedidos-bucket/uploads/arquivo-valido-7bfdd213.txt

curl -s "http://localhost:8000/pedidos?customerId=CUSTBATCH01"
# "channel":"BATCH", "source_file":"uploads/arquivo-valido-...txt", "source_line":2,
# "status":"COMPLETED"
```

`make seed-file` continua existindo e gera um arquivo válido do zero, sem precisar de `examples/`.

Os dois níveis de erro do parser (`docs/01-dominio-e-contratos.md` §6) dão para ver na prática:

```bash
make upload FILE=examples/arquivo-com-erros.txt
curl -s "http://localhost:8000/pedidos?customerId=CUSTBATCHOK"   # criado
curl -s "http://localhost:8000/pedidos?customerId=CUSTBATCHNOK"  # {"pedidos":[]} — descartado

make upload FILE=examples/arquivo-invalido.txt
curl -s "http://localhost:8000/pedidos?customerId=CUSTBATCHXX"   # {"pedidos":[]} — nada foi enviado
```

O motivo aparece no log do File Consumer (`registro rejeitado` para o pedido isolado,
`arquivo rejeitado` para o arquivo inteiro):

```bash
docker compose -f infra/docker-compose.yml logs -f file-consumer
```

Para exercitar `EDITAR`/`CANCELAR` via arquivo, copie uma linha tipo `1` de um dos exemplos, troque
a operação nas posições 2–11 (`EDITAR    ` / `CANCELAR  `, com padding até 10 caracteres) e escreva
o `order_id` de um pedido existente nas posições 12–47. Toda linha tem exatamente 200 caracteres —
o layout completo está em `docs/01-dominio-e-contratos.md` §6.

### Observando e reprocessando DLQs

Mensagens que falham tecnicamente 3 vezes vão para a DLQ da fila (`{fila}_dlq`) e o pedido fica
parado num estado não terminal. O gateway expõe três rotas operacionais (**sem autenticação** —
uso local, não exponha a clientes finais). `{fila}` é a fila de origem, ex. `validar_pedido_queue`:

```bash
curl -s http://localhost:8000/dlqs                                  # contagem das 9 DLQs
curl -s "http://localhost:8000/dlqs/{fila}/mensagens?limit=10"      # espia (não consome): order_id, correlation_id, corpo
curl -s -X POST http://localhost:8000/dlqs/{fila}/reprocessamento   # devolve a DLQ inteira à fila de origem
curl -s -X POST http://localhost:8000/dlqs/{fila}/reprocessamento     -H 'Content-Type: application/json' -d '{"message_id":"<id da listagem>"}'   # só uma mensagem
```

Corrija a causa da falha antes de reprocessar. O `customer_document` sai sempre mascarado; a
mensagem só deixa a DLQ depois de reenviada à fila de origem. Para ver o pedido parado, use o
`order_id` da listagem em `GET /pedidos/<order_id>`. Contrato:
`specs/011-observabilidade-dlq/contracts/dlq-endpoints.md`.

### Baixando a nota fiscal (PDF)

O PDF só é acessível pelo API Gateway — o S3 não é exposto. Com o pedido em `COMPLETED`
(`invoice_available: true` no `GET /pedidos/<order_id>`):

```bash
curl -o nota.pdf http://localhost:8000/pedidos/<order_id>/nota-fiscal
```

| Status | Quando |
|---|---|
| `200` | Pedido `COMPLETED`; corpo é o PDF (`application/pdf`) |
| `404` | Pedido inexistente, ou PDF ausente no armazenamento |
| `409` | Pedido ainda em processamento (inclusive reprocessamento após edição) — tente de novo |
| `410` | Pedido `REJECTED`, `FAILED` ou `CANCELLED` — nenhum PDF será gerado |

Vale também para pedidos criados pelo fluxo batch. Contrato:
`specs/010-acesso-pdf-pedido/contracts/nota-fiscal-endpoint.md`.

### Conferindo as notas fiscais geradas no S3

```bash
set -a && . ./.env && set +a       # exporta as credenciais do Ministack no shell
uv run --package infra-bootstrap python -c "
from resources.aws_clients import build_client
s3 = build_client('s3')
for obj in s3.list_objects_v2(Bucket='pedidos-bucket', Prefix='invoices/').get('Contents', []):
    print(obj['Key'], obj['Size'], 'bytes')
"
```

### Suítes automatizadas

```bash
make test   # unitários + integração de todos os pacotes — exige Ministack no ar
make e2e    # tests/e2e — exige o ambiente COMPLETO no ar (nenhum mock)
```

As duas suítes têm exigências opostas de ambiente, e trocá-las gera falha:

- **`make test`** precisa do Ministack, mas com os **serviços parados**. Vários testes de
  integração publicam numa fila real e leem a mensagem de volta; com os workers no ar, eles
  consomem a mensagem primeiro e os testes falham por "fila vazia".

  ```bash
  docker compose -f infra/docker-compose.yml up -d ministack bootstrap   # só a infra
  make test                                                              # 371 passed, 1 skipped
  ```

- **`make e2e`** precisa de tudo no ar (`make up`); ele checa os 6 `/health` antes de começar e
  aborta em segundos com a lista de serviços inacessíveis se algum estiver fora. Logo após um
  `make up`, dê alguns segundos aos serviços antes de rodar — o `docker compose` retorna assim que
  os containers iniciam, não quando o `/health` já responde.

Rodando um pacote isolado:

```bash
uv run --package order-processor pytest services/order-processor/tests -v
uv run --package order-processor ruff check services/order-processor
uv sync --all-packages   # restaura o venv completo depois de um sync com --package
```

### Problemas comuns

| Sintoma | Causa |
|---|---|
| `GET /pedidos/{id}` responde `404` logo após o `POST` | Normal: o `202` só significa "comando publicado". Consulte de novo em alguns segundos. |
| `409` em `GET /pedidos/{id}/nota-fiscal` | Pedido ainda não chegou a `COMPLETED`. Aguarde e repita. |
| `410` em `GET /pedidos/{id}/nota-fiscal` | Pedido `REJECTED`/`FAILED`/`CANCELLED`: não há PDF. |
| `GET /dlqs/{fila}/...` responde `404` | `{fila}` precisa ser o nome da fila de origem (uma das 9 de `docs/01-dominio-e-contratos.md` §4), não o da `_dlq`. |
| `409` ao cancelar | O pedido já passou de `INVOICING`. Cancele logo após a criação (veja a receita acima). |
| `409` ao editar | Status atual não permite voltar a `PROCESSING` (`COMPLETED`, `CANCELLED`, `INVOICING`...). |
| `KeyError: 'AWS_ENDPOINT_URL'` em `make upload`/`make seed-file` | Falta o `.env` na raiz — `cp .env.example .env`. |
| `make test` falha só nos testes `test_idempotencia` | Os serviços estão no ar consumindo as filas; pare-os e rode com o Ministack sozinho. |
| `make e2e` aborta com "ambiente incompleto" | Algum serviço não subiu — cheque `docker compose -f infra/docker-compose.yml ps`. |
| Pedido batch com CPF cai em `REJECTED` | O campo `customer_document` do layout tem 14 posições preenchidas com zeros à esquerda, e o validador lê 14 dígitos como CNPJ. Por isso os exemplos batch usam um CNPJ; um CPF de 11 dígitos zero-preenchido é reprovado. |

## Estrutura do monorepo

```
services/            # um diretório por serviço (handlers/domain/adapters/config.py/main.py)
shared/pedidos_shared/  # contratos de mensagem, máquina de estados, clientes de infra, parser de arquivo
infra/                # bootstrap idempotente (filas/tabelas/bucket) + docker-compose.yml
examples/             # payloads JSON e arquivos posicionais prontos para testar o sistema à mão
tests/e2e/            # testes de sistema contra o ambiente completo real (make e2e)
specs/                # specs, planos e tasks gerados via Spec Kit (/speckit-*), um dir por feature
docs/                 # contrato de domínio — fonte da verdade referenciada por toda spec
```

## Fluxo de desenvolvimento

Cada feature nasce de `/speckit-specify` (spec → clarify → plan → tasks → implement), numa branch
`feature/NNN-nome-da-feature` a partir de `main`, com PR ao final. Detalhes completos do fluxo,
convenções de código e definição de pronto: [`.specify/memory/constitution.md`](.specify/memory/constitution.md).
