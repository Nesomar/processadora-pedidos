# Domínio, Contratos e Infraestrutura Compartilhada

> Este documento é a **fonte da verdade** referenciada por todas as features.
> Recomendo salvá-lo no repositório em `docs/dominio-e-contratos.md` e referenciá-lo
> em cada `/specify`.

---

## 1. Visão geral do sistema

Sistema de processamento assíncrono de pedidos, com duas portas de entrada:

- **Entrada online:** cliente HTTP → API Gateway
- **Entrada batch:** upload de arquivo posicional `.txt` no S3 → cada linha vira uma chamada
  ao mesmo API Gateway

Ambas convergem para o mesmo pipeline event-driven de processamento, validação e emissão de
nota fiscal em PDF.

### Fluxo completo

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

O **Order Processor** é o orquestrador central: recebe comandos, dispara validação, dispara
geração de PDF e conclui o pedido. Ele nunca bloqueia — cada resposta chega por fila e retoma
a máquina de estados.

---

## 2. Entidades

### 2.1 Produto (externo, somente leitura)

Origem: `https://dummyjson.com/products/{id}` — API externa de catálogo. **Não persistimos
produtos**, apenas consultamos e fazemos cache em memória.

Campos utilizados pelo sistema:

| Campo | Tipo | Uso |
|---|---|---|
| `id` | int | identificador do produto no pedido |
| `title` | str | descrição na nota fiscal |
| `price` | float | preço unitário oficial |
| `stock` | int | validação de disponibilidade |
| `minimumOrderQuantity` | int | validação de quantidade mínima |
| `availabilityStatus` | str | `In Stock` / `Low Stock` / `Out of Stock` |
| `sku` | str | exibido na nota fiscal |
| `discountPercentage` | float | desconto aplicado ao item |
| `category` | str | agrupamento na nota fiscal |

Endpoints usados:
- `GET /products/{id}` — validação de item individual
- `GET /products?limit=194` — carga inicial de cache (opcional)

Comportamento em erro: `404` ⇒ produto inexistente (erro de negócio). Timeout ou `5xx` ⇒ erro
técnico, mensagem volta para a fila (retry), após 3 tentativas vai para DLQ.

### 2.2 Pedido (entidade própria, persistida)

```python
class OrderItem(BaseModel):
    product_id: int
    quantity: int                # > 0
    unit_price: Decimal | None   # preenchido pelo Validator com o preço oficial
    discount_percentage: Decimal | None
    line_total: Decimal | None   # quantity * unit_price * (1 - discount/100)
    product_title: str | None    # snapshot para a nota fiscal
    product_sku: str | None

class Order(BaseModel):
    order_id: str                # UUID v4, gerado pelo API Gateway
    customer_id: str             # até 20 chars, alfanumérico
    customer_name: str
    customer_document: str        # CPF/CNPJ, somente dígitos
    channel: Literal["HTTP", "BATCH"]
    items: list[OrderItem]        # 1..50 itens
    subtotal: Decimal | None
    discount_total: Decimal | None
    total: Decimal | None
    status: OrderStatus
    status_reason: str | None     # motivo em caso de rejeição/falha
    invoice_s3_key: str | None    # chave do PDF da nota fiscal
    correlation_id: str           # rastreio ponta a ponta
    source_file: str | None       # nome do arquivo, quando channel == BATCH
    source_line: int | None       # número da linha, quando channel == BATCH
    created_at: datetime          # ISO 8601 UTC
    updated_at: datetime
    version: int                  # controle de concorrência otimista
```

### 2.3 Máquina de estados

```python
class OrderStatus(str, Enum):
    RECEIVED    = "RECEIVED"     # aceito pelo API Gateway, na fila
    PROCESSING  = "PROCESSING"   # Order Processor assumiu
    VALIDATING  = "VALIDATING"   # aguardando resposta do Validator
    VALIDATED   = "VALIDATED"    # regras OK, totais calculados
    REJECTED    = "REJECTED"     # falhou validação de negócio (terminal)
    INVOICING   = "INVOICING"    # aguardando PDF Generator
    COMPLETED   = "COMPLETED"    # nota fiscal emitida (terminal)
    CANCELLED   = "CANCELLED"    # cancelado pelo cliente (terminal)
    FAILED      = "FAILED"       # erro técnico irrecuperável (terminal)
```

**Transições permitidas** (qualquer outra transição é rejeitada e logada como erro):

| De | Para | Gatilho |
|---|---|---|
| — | `RECEIVED` | API Gateway aceita a requisição |
| `RECEIVED` | `PROCESSING` | Order Processor consome `solicitar_pedido_queue` |
| `PROCESSING` | `VALIDATING` | Order Processor publica em `validar_pedido_queue` |
| `VALIDATING` | `VALIDATED` | resposta `approved=true` |
| `VALIDATING` | `REJECTED` | resposta `approved=false` |
| `VALIDATED` | `INVOICING` | Order Processor publica em `pdf_request_queue` |
| `INVOICING` | `COMPLETED` | resposta `success=true` do PDF Generator |
| `INVOICING` | `FAILED` | resposta `success=false` do PDF Generator |
| `RECEIVED`, `PROCESSING`, `VALIDATING`, `VALIDATED` | `CANCELLED` | comando de cancelamento |
| `RECEIVED`, `VALIDATED`, `REJECTED` | `PROCESSING` | comando de edição (reinicia o ciclo) |
| qualquer não-terminal | `FAILED` | erro técnico após esgotar retries |

Estados terminais: `COMPLETED`, `CANCELLED`, `REJECTED`, `FAILED`. Comandos de edição ou
cancelamento sobre `COMPLETED`, `CANCELLED` ou `FAILED` retornam `409 Conflict`.
Edição sobre `REJECTED` é permitida (correção de pedido recusado).

---

## 3. Persistência — DynamoDB

### Tabela `orders`

| Atributo | Papel |
|---|---|
| `PK` = `ORDER#{order_id}` | partition key |
| `SK` = `METADATA` | sort key |
| demais atributos | campos de `Order` |

**GSI1 — consulta por cliente:**
- `GSI1PK` = `CUSTOMER#{customer_id}`
- `GSI1SK` = `{created_at}#{order_id}`
- Uso: `GET /pedidos?customerId=X` com ordenação decrescente por data.

**GSI2 — consulta por status:**
- `GSI2PK` = `STATUS#{status}`
- `GSI2SK` = `{created_at}#{order_id}`
- Uso: monitoramento e reprocessamento.

**Concorrência:** toda escrita usa `ConditionExpression` sobre `version`
(`attribute_not_exists(PK) OR version = :expected_version`) e incrementa `version`.
Falha de condição ⇒ recarrega o item e reavalia a transição (até 3 tentativas).

### Tabela `processed_messages` (idempotência)

| Atributo | Papel |
|---|---|
| `PK` = `MSG#{message_id}` | partition key |
| `consumer` | nome do serviço consumidor |
| `processed_at` | timestamp |
| `ttl` | expiração em 7 dias (TTL nativo) |

Todo consumidor grava condicionalmente antes de processar; se a gravação falhar por já existir,
a mensagem é descartada silenciosamente (log em nível `info`).

---

## 4. Filas SQS

Todas standard queues, `visibility_timeout = 60s`, `message_retention = 4 dias`,
redrive para `{nome}_dlq` com `maxReceiveCount = 3`.

| Fila | Produtor | Consumidor |
|---|---|---|
| `solicitar_pedido_queue` | API Gateway | Order Processor |
| `editar_pedido_queue` | API Gateway | Order Processor |
| `cancelar_pedido_queue` | API Gateway | Order Processor |
| `validar_pedido_queue` | Order Processor | Order Validator |
| `validar_pedido_response_queue` | Order Validator | Order Processor |
| `pdf_request_queue` | Order Processor | PDF Generator |
| `pdf_response_queue` | PDF Generator | Order Processor |
| `s3_notifications_queue` | S3 (event notification) | File Consumer |
| `pedido_lines_queue` | File Consumer | Lambda Line Processor |

Cada fila acima tem sua DLQ correspondente com sufixo `_dlq`.

---

## 5. Contratos de mensagem

Envelope comum a todas as mensagens internas:

```python
class MessageEnvelope(BaseModel):
    message_id: str        # UUID v4, gerado pelo produtor
    correlation_id: str    # propagado sem alteração por todo o fluxo
    order_id: str
    occurred_at: datetime  # ISO 8601 UTC
    payload: dict          # específico por tipo de mensagem
```

### `solicitar_pedido_queue` / `editar_pedido_queue` — payload

```json
{
  "customer_id": "CUST00001",
  "customer_name": "Maria Silva",
  "customer_document": "12345678901",
  "channel": "HTTP",
  "items": [
    { "product_id": 1, "quantity": 50 },
    { "product_id": 16, "quantity": 10 }
  ],
  "source_file": null,
  "source_line": null
}
```

### `cancelar_pedido_queue` — payload

```json
{ "reason": "Cliente desistiu da compra" }
```

### `validar_pedido_queue` — payload

```json
{
  "customer_document": "12345678901",
  "items": [{ "product_id": 1, "quantity": 50 }]
}
```

### `validar_pedido_response_queue` — payload

```json
{
  "approved": false,
  "errors": [
    { "code": "BELOW_MINIMUM_ORDER_QUANTITY", "product_id": 1,
      "message": "Quantidade 10 abaixo do mínimo 48" }
  ],
  "enriched_items": [
    { "product_id": 1, "quantity": 50, "unit_price": "9.99",
      "discount_percentage": "10.48", "line_total": "447.05",
      "product_title": "Essence Mascara Lash Princess", "product_sku": "BEA-ESS-ESS-001" }
  ],
  "subtotal": "499.50",
  "discount_total": "52.45",
  "total": "447.05"
}
```

Quando `approved = false`, `enriched_items` e os totais vêm nulos.

### `pdf_request_queue` — payload

```json
{
  "customer_name": "Maria Silva",
  "customer_document": "12345678901",
  "items": [ /* enriched_items */ ],
  "subtotal": "499.50",
  "discount_total": "52.45",
  "total": "447.05"
}
```

### `pdf_response_queue` — payload

```json
{
  "success": true,
  "s3_key": "invoices/2026/07/18/{order_id}.pdf",
  "error_message": null
}
```

### `pedido_lines_queue` — payload

```json
{
  "source_file": "pedidos_20260718.txt",
  "line_number": 42,
  "operation": "SOLICITAR",
  "raw_line": "...",
  "parsed": { /* mesmo formato do payload de solicitar_pedido */ }
}
```

---

## 6. Layout do arquivo posicional

Codificação **UTF-8**, quebra de linha `\n`, campos de texto alinhados à esquerda com padding
de espaços, campos numéricos alinhados à direita com padding de zeros. Sem separadores.

### Header (1 registro, obrigatório, primeira linha)

| Pos | Tam | Campo | Formato / Regra |
|---|---|---|---|
| 1–1 | 1 | `record_type` | fixo `0` |
| 2–9 | 8 | `file_date` | `YYYYMMDD` |
| 10–39 | 30 | `origin_system` | texto |
| 40–45 | 6 | `sequence` | numérico, sequencial do arquivo |
| 46–200 | 155 | `filler` | espaços |

### Detalhe — pedido (registro tipo `1`)

| Pos | Tam | Campo | Formato / Regra |
|---|---|---|---|
| 1–1 | 1 | `record_type` | fixo `1` |
| 2–11 | 10 | `operation` | `SOLICITAR `, `EDITAR    `, `CANCELAR  ` |
| 12–47 | 36 | `order_id` | UUID; espaços quando `SOLICITAR` |
| 48–67 | 20 | `customer_id` | texto |
| 68–127 | 60 | `customer_name` | texto |
| 128–141 | 14 | `customer_document` | numérico, zeros à esquerda |
| 142–143 | 2 | `item_count` | numérico, 01–50 |
| 144–200 | 57 | `filler` | espaços |

### Detalhe — item (registro tipo `2`, sempre após seu pedido)

| Pos | Tam | Campo | Formato / Regra |
|---|---|---|---|
| 1–1 | 1 | `record_type` | fixo `2` |
| 2–9 | 8 | `product_id` | numérico, zeros à esquerda |
| 10–17 | 8 | `quantity` | numérico, zeros à esquerda |
| 18–200 | 183 | `filler` | espaços |

### Trailer (1 registro, obrigatório, última linha)

| Pos | Tam | Campo | Formato / Regra |
|---|---|---|---|
| 1–1 | 1 | `record_type` | fixo `9` |
| 2–9 | 8 | `total_orders` | numérico — quantidade de registros tipo `1` |
| 10–17 | 8 | `total_items` | numérico — quantidade de registros tipo `2` |
| 18–200 | 183 | `filler` | espaços |

**Todas as linhas têm exatamente 200 caracteres.**

### Regras de parsing

- Linha com tamanho diferente de 200 ⇒ linha rejeitada, registrada no relatório de erros,
  processamento continua.
- Header ausente/inválido ou trailer ausente ⇒ **arquivo inteiro rejeitado**, nada é enviado
  para a fila.
- Contadores do trailer divergentes do contado ⇒ **arquivo inteiro rejeitado**.
- Registro tipo `2` sem tipo `1` antecedente ⇒ linha rejeitada.
- `item_count` divergente da quantidade de registros tipo `2` do pedido ⇒ pedido rejeitado
  (o pedido, não o arquivo).

### Exemplo (linhas truncadas visualmente)

```
020260718SISTEMA_LEGADO_VENDAS         000001<espaços até 200>
1SOLICITAR <36 espaços>CUST00001           MARIA SILVA<pad>0001234567890102<espaços>
200000001000000050<espaços até 200>
200000016000000010<espaços até 200>
90000000100000002<espaços até 200>
```

---

## 7. S3

Bucket único `pedidos-bucket`, com dois prefixos:

- `uploads/` — arquivos posicionais enviados. Evento `s3:ObjectCreated:*` com filtro de
  prefixo `uploads/` e sufixo `.txt` → `s3_notifications_queue`.
- `invoices/YYYY/MM/DD/{order_id}.pdf` — notas fiscais geradas.

---

## 8. Ambiente local — Ministack

Todos os serviços AWS (SQS, DynamoDB, S3) são providos pelo Ministack. Configuração:

```
AWS_ENDPOINT_URL=http://ministack:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_REGION=us-east-1
```

O `docker-compose.yml` sobe: `ministack`, os 5 serviços Python, o runner da Lambda, e um
container `bootstrap` que roda uma única vez criando filas, DLQs, tabelas, bucket e a
configuração de notificação do S3 — de forma idempotente.

Alvos de `Makefile` esperados: `make up`, `make down`, `make bootstrap`, `make test`,
`make e2e`, `make seed-file` (gera um arquivo posicional de exemplo e faz upload).
