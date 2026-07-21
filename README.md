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
                                            Lambda Line Processor (ainda não implementado)
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
chamam diretamente por HTTP (a única exceção é o Order Validator consultando o catálogo externo
`dummyjson.com`).

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
| `lambda-line-processor` | Transforma cada linha do arquivo numa chamada ao API Gateway | *ainda não implementado* |

Cada serviço expõe `GET /health`. Contratos de fila consumida/publicada e variáveis de ambiente
de cada um estão no `README.md` do respectivo diretório em `services/`.

## Stack

Python 3.12, `uv` (um `pyproject.toml` por serviço em workspace), FastAPI (API Gateway),
Pydantic v2 (contratos de mensagem), boto3 (SQS/DynamoDB/S3 via Ministack), ReportLab (PDF), httpx
(única chamada HTTP externa permitida), pytest, ruff, Docker/docker-compose.

## Rodando localmente

Pré-requisitos: Docker, `uv`.

```bash
cp .env.example .env   # ajuste se necessário
make up                 # sobe Ministack + bootstrap (filas/tabelas/bucket) + todos os serviços
```

```bash
curl http://localhost:8000/health   # api-gateway
curl http://localhost:8080/health   # order-processor
curl http://localhost:8081/health   # order-validator
curl http://localhost:8082/health   # pdf-generator
curl http://localhost:8083/health   # file-consumer
```

```bash
make seed-file   # gera e envia um arquivo posicional de exemplo para uploads/
make test        # roda a suíte de testes de todos os pacotes do workspace
make down        # derruba o ambiente
```

## Estrutura do monorepo

```
services/            # um diretório por serviço (handlers/domain/adapters/config.py/main.py)
shared/pedidos_shared/  # contratos de mensagem, máquina de estados, clientes de infra, parser de arquivo
infra/                # bootstrap idempotente (filas/tabelas/bucket) + docker-compose.yml
specs/                # specs, planos e tasks gerados via Spec Kit (/speckit-*), um dir por feature
docs/                 # contrato de domínio — fonte da verdade referenciada por toda spec
```

## Fluxo de desenvolvimento

Cada feature nasce de `/speckit-specify` (spec → clarify → plan → tasks → implement), numa branch
`feature/NNN-nome-da-feature` a partir de `main`, com PR ao final. Detalhes completos do fluxo,
convenções de código e definição de pronto: [`.specify/memory/constitution.md`](.specify/memory/constitution.md).
