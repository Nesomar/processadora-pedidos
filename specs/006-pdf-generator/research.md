# Research: PDF Generator

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## 1. Geração do PDF

**Decision**: ReportLab `platypus` (`SimpleDocTemplate` + `Table`/`Paragraph`), renderizando em
memória (`io.BytesIO`) — sem gravar arquivo temporário em disco. Função pura
`renderizar_nota_fiscal(dados: DadosNotaFiscal) -> bytes` em `domain/renderizador.py`.

**Rationale**: constitution II fixa `ReportLab` como biblioteca de PDF obrigatória. `platypus` é a
camada de alto nível da própria biblioteca, feita pra documentos com tabelas de tamanho variável
(número de itens do pedido) — evita posicionamento manual de coordenadas X/Y que o `canvas` de
baixo nível exigiria. Como a função não abre socket, não lê variável de ambiente e não grava em
disco, cabe em `domain/` (constitution VIII: "sem I/O" refere-se a rede/banco/arquivo — manipular
bytes em memória é computação pura).

**Alternatives considered**: `reportlab.pdfgen.canvas` direto — rejeitado, exigiria calcular
manualmente a posição de cada linha da tabela de itens (1 a 50 itens, FR-002), reimplementando o
que `platypus.Table` já resolve; outra biblioteca de PDF (`fpdf2`, `weasyprint`) — rejeitada,
constitution II já fixa ReportLab, não há motivo pra divergir.

## 2. Armazenamento no S3

**Decision**: reaproveitar `pedidos_shared.S3Client.put_object`, estendendo sua assinatura com um
parâmetro opcional `content_type: str | None = None` (default preserva o comportamento atual —
nenhum outro serviço usa `S3Client` ainda, então a extensão é estritamente aditiva). O worker
chama `put_object(bucket, key, pdf_bytes, content_type="application/pdf")`.

**Rationale**: constitution III ("contratos... vivem SOMENTE em `shared/pedidos_shared`") e o
princípio de não duplicar clientes de infraestrutura por serviço — `S3Client` já existe e cobre
exatamente o `put_object` necessário; falta só o `Content-Type` correto para o objeto ser
reconhecido como PDF por quem baixar depois (fora do escopo desta feature, mas de graça).

**Alternatives considered**: `boto3.client("s3")` direto dentro do serviço, ignorando
`S3Client` — rejeitado, duplicaria o wrapper já existente e violaria a regra de reaproveitar
clientes de `pedidos_shared`; gravar sem `Content-Type` — rejeitado, custo de adicionar o
parâmetro é mínimo (uma linha) e evita um problema futuro conhecido.

## 3. Chave do objeto no S3

**Decision**: função pura `montar_chave_invoice(order_id: str, momento: datetime) -> str` em
`domain/chave_s3.py`, retornando `invoices/{ano:04d}/{mes:02d}/{dia:02d}/{order_id}.pdf` a partir
de um `datetime` recebido por parâmetro (nunca `datetime.now()` interno) — o `handler` passa
`datetime.now(UTC)` no momento do processamento (FR-003).

**Rationale**: receber o momento como parâmetro em vez de a função capturá-lo internamente torna a
função 100% determinística e testável sem mockar relógio (constitution VIII, funções puras).

**Alternatives considered**: capturar `datetime.now(UTC)` dentro da própria função — rejeitado,
exigiria `monkeypatch`/`freezegun` nos testes; usar `order_id` como único componente da chave (sem
data) — rejeitado, o contrato já documentado (`docs/01-dominio-e-contratos.md` §"Armazenamento de
arquivos", spec.md FR-003) exige o prefixo `invoices/YYYY/MM/DD/`.

## 4. Validação de dados incompletos (US2)

**Decision**: função pura `validar_solicitacao(payload: dict) -> str | None` em
`domain/validacao.py`, retornando `None` quando a mensagem tem `customer_name`,
`customer_document` e ao menos 1 item; caso contrário retorna uma mensagem de erro legível
identificando o campo ausente. Não reexecuta validação de CPF/CNPJ nem de estoque — isso já foi
feito pelo Order Validator (`005-order-validator`) antes do pedido chegar a `INVOICING`.

**Rationale**: FR-005/US2. Este serviço confia nos dados já validados rio acima; só precisa se
proteger contra o caso degenerado de uma mensagem malformada chegar à fila, não reimplementar
validação de negócio que não é sua responsabilidade.

**Alternatives considered**: não validar nada e deixar o `renderizador` estourar exceção em dado
faltante — rejeitado, geraria falha técnica (sem ack) para um problema que nunca se resolve
sozinho, entrando em loop de redrive até a DLQ sem necessidade (FR-005 exige resposta de negócio
imediata nesse caso).

## 5. Idempotência e falha técnica (reaproveitando o padrão de 004/005)

**Decision**: mesmo `adapters/worker_loop.py` já usado em `004-order-processor` e
`005-order-validator`: `is_message_processed` (só leitura) checado ANTES do handler;
`mark_message_processed` chamado só DEPOIS do handler concluir sem levantar exceção — o que cobre
tanto sucesso (`success=true` publicado) quanto falha de negócio (`success=false` publicado,
FR-005). Falha técnica de armazenamento (`S3Client.put_object` levanta exceção) propaga para fora
do handler, sem publicar resposta nem marcar/confirmar a mensagem (FR-006).

**Rationale**: FR-006/FR-007, constitution I.3. Reaproveita uma estrutura já corrigida e testada
duas vezes no monorepo — não há razão pra reavaliar alternativas aqui.

**Alternatives considered**: nenhuma — mesma justificativa de `005-order-validator` research.md #5.

## 6. Estratégia de testes

**Decision**: testes unitários cobrindo `domain/validacao.py`, `domain/chave_s3.py` e
`domain/renderizador.py` isoladamente (o renderizador é testado verificando que o PDF gerado
começa com o cabeçalho `%PDF-` e não está vazio — não se testa o layout visual pixel a pixel). Um
teste de integração real contra Ministack cobre o fluxo completo: publicar em
`pdf_request_queue`, consumir, gravar objeto real no S3 (Ministack), publicar em
`pdf_response_queue`, e ler o objeto de volta do S3 pra confirmar que é um PDF não vazio.

**Rationale**: constitution IX exige ao menos um teste de integração contra o Ministack. Como este
serviço não tem nenhuma chamada HTTP externa (diferente do `005-order-validator`), não há
necessidade de uma seção de "validação manual contra API real" no `quickstart.md` — toda a
superfície de integração (SQS + S3) já roda 100% local via Ministack.

**Alternatives considered**: comparar o PDF gerado byte a byte contra um fixture fixo — rejeitado,
frágil a qualquer mudança de biblioteca/versão do ReportLab que não afete o conteúdo relevante.
