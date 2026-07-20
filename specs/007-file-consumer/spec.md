# Feature Specification: File Consumer

**Feature Branch**: `007-file-consumer`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "Worker que consome s3_notifications_queue (evento de criacao de objeto no prefixo uploads/*.txt do bucket pedidos-bucket), baixa o arquivo posicional do S3, faz o parse usando pedidos_shared.file_layout.parse_file (ja implementado), e publica uma mensagem em pedido_lines_queue por pedido valido do arquivo (formato documentado em docs/01-dominio-e-contratos.md paragrafo 5, secao pedido_lines_queue). Arquivo inteiro invalido (header/trailer ausente ou contadores divergentes) e rejeitado sem nada ser enviado a fila. Linha invalida ou pedido com item_count divergente e rejeitado individualmente, registrado como erro, processamento do arquivo continua. Nao escreve em orders nem chama a API Gateway diretamente -- isso e responsabilidade do Lambda Line Processor (fora do escopo desta feature)."

## Clarifications

### Session 2026-07-20

- Q: O "relatório de erros" citado em docs/01-dominio-e-contratos.md §6 deve ser um artefato durável (ex.: arquivo no S3) ou log estruturado JSON basta? → A: Log estruturado JSON, mesmo padrão de falha-é-dado das demais features — sem artefato de relatório separado.
- Q: Qual valor usar no `reason` da mensagem `pedido_lines_queue` para pedidos `CANCELAR` vindos de arquivo, já que o layout não tem campo `reason`? → A: Texto fixo `"Cancelamento via arquivo batch"`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Processar arquivo batch valido linha a linha (Priority: P1) MVP

Quando um arquivo posicional de pedidos é enviado ao armazenamento de arquivos, o sistema precisa
ler esse arquivo, entender cada pedido descrito nele e entregar cada pedido, um de cada vez, para
quem vai transformá-lo numa chamada real ao sistema (o Lambda Line Processor, fora do escopo desta
feature).

**Why this priority**: É o caminho principal da entrada em lote — sem ele, nenhum pedido enviado
por arquivo chega a ser processado. É o motivo de existir deste serviço.

**Independent Test**: Fazer upload de um arquivo posicional válido com header, 1+ pedidos (com
seus itens) e trailer consistente; verificar que uma mensagem aparece em `pedido_lines_queue` para
cada pedido do arquivo, com `source_file`, `line_number`, `operation` e `parsed` corretos.

**Acceptance Scenarios**:

1. **Given** um arquivo válido com 2 pedidos `SOLICITAR`, cada um com 1+ itens, **When** o worker
   processa a notificação do arquivo, **Then** 2 mensagens aparecem em `pedido_lines_queue`, cada
   uma com `operation="SOLICITAR"`, `source_file` igual ao nome do objeto no S3, `line_number`
   apontando para a linha do registro tipo `1` correspondente, e `parsed` no mesmo formato do
   payload de `solicitar_pedido_queue` (`customer_id`, `customer_name`, `customer_document`,
   `channel="BATCH"`, `items`, `source_file`, `source_line`).
2. **Given** um arquivo válido com um pedido `EDITAR` referenciando um `order_id` existente,
   **When** processado, **Then** a mensagem publicada tem `operation="EDITAR"` e `parsed` no mesmo
   formato do payload de `editar_pedido_queue`, incluindo o `order_id` do registro.
3. **Given** um arquivo válido com múltiplos pedidos de operações diferentes, **When** processado,
   **Then** uma mensagem é publicada por pedido, na ordem em que aparecem no arquivo.

---

### User Story 2 - Rejeitar arquivo inteiro estruturalmente invalido (Priority: P1)

Quando o arquivo recebido não segue a estrutura mínima esperada (falta cabeçalho ou rodapé, ou os
totais informados no rodapé não batem com o que foi realmente encontrado), nenhum pedido daquele
arquivo deve ser processado — o arquivo inteiro é tratado como inválido.

**Why this priority**: Processar parcialmente um arquivo estruturalmente corrompido arriscaria
interpretar dados errados como pedidos válidos. Tão crítico quanto o caminho feliz para a
integridade dos dados.

**Independent Test**: Fazer upload de um arquivo sem registro de cabeçalho, sem registro de
rodapé, ou com contadores de rodapé divergentes da contagem real; verificar que nenhuma mensagem
aparece em `pedido_lines_queue` e que o motivo da rejeição fica disponível para consulta.

**Acceptance Scenarios**:

1. **Given** um arquivo sem o registro de cabeçalho (primeira linha não é tipo `0`), **When** o
   worker processa a notificação, **Then** nenhuma mensagem é publicada em `pedido_lines_queue` e
   o motivo da rejeição fica registrado.
2. **Given** um arquivo cujo rodapé informa uma quantidade de pedidos ou itens diferente da
   quantidade real de registros encontrados, **When** processado, **Then** nenhuma mensagem é
   publicada e o motivo fica registrado.

---

### User Story 3 - Rejeitar pedido ou linha individualmente sem interromper o arquivo (Priority: P1)

Quando apenas uma linha ou um pedido específico do arquivo está malformado (por exemplo, uma linha
com tamanho errado, ou um pedido cuja contagem de itens declarada não bate com os itens
encontrados), apenas aquele pedido é descartado — os demais pedidos válidos do mesmo arquivo devem
ser processados normalmente.

**Why this priority**: Um único registro malformado não deveria bloquear centenas de outros
pedidos válidos no mesmo arquivo. Essencial para a robustez do processamento em lote.

**Independent Test**: Fazer upload de um arquivo válido estruturalmente, mas com um pedido cuja
contagem de itens declarada não bate com a quantidade real de itens encontrados; verificar que os
demais pedidos do arquivo geram mensagens em `pedido_lines_queue` normalmente e que o pedido
malformado é registrado como erro, sem gerar mensagem.

**Acceptance Scenarios**:

1. **Given** um arquivo com 3 pedidos válidos e 1 pedido cujo `item_count` diverge da quantidade
   real de itens, **When** processado, **Then** 3 mensagens são publicadas em `pedido_lines_queue`
   (uma por pedido válido) e o pedido divergente é registrado como erro, sem mensagem publicada
   para ele.
2. **Given** um arquivo com um registro de item (tipo `2`) sem nenhum pedido (tipo `1`) antes dele,
   **When** processado, **Then** essa linha é registrada como erro e os demais pedidos válidos do
   arquivo continuam sendo processados normalmente.

---

### User Story 4 - Preservar disponibilidade diante de falha técnica de armazenamento (Priority: P2)

Se o armazenamento de arquivos estiver temporariamente indisponível ao tentar buscar o conteúdo do
arquivo notificado, o sistema não deve descartar a notificação nem decidir que o arquivo é
inválido — deve preservar a notificação para nova tentativa mais tarde, como já acontece nos demais
workers do sistema.

**Why this priority**: Tratar uma instabilidade passageira do armazenamento como "arquivo
inválido" perderia pedidos legítimos que nunca chegaram a ser lidos.

**Independent Test**: Simular indisponibilidade do armazenamento ao buscar o conteúdo do arquivo
notificado; verificar que nenhuma mensagem de erro definitivo é registrada e que a notificação
original não é confirmada nem marcada como processada.

**Acceptance Scenarios**:

1. **Given** o armazenamento de arquivos está indisponível ou retorna erro técnico ao buscar o
   conteúdo do arquivo, **When** o worker tenta processar a notificação, **Then** nenhuma mensagem
   é publicada em `pedido_lines_queue`, a notificação original permanece disponível para nova
   tentativa, e o erro é registrado em log.

---

### User Story 5 - Reprocessar a mesma notificação sem duplicar pedidos (Priority: P3)

Como qualquer fila pode entregar a mesma notificação de arquivo mais de uma vez, processar o mesmo
arquivo duas vezes duplicaria as mensagens de pedido enviadas adiante.

**Why this priority**: Reforça a garantia de idempotência já adotada pelos outros workers do
sistema; prioridade menor porque a duplicidade de notificação é rara, mas precisa ser coberta antes
de produção.

**Independent Test**: Processar ou entregar a mesma notificação de arquivo duas vezes; verificar
que os pedidos daquele arquivo geram mensagens em `pedido_lines_queue` apenas uma vez.

**Acceptance Scenarios**:

1. **Given** uma notificação de arquivo já processada com sucesso, **When** ela chega novamente ao
   worker, **Then** nenhuma nova mensagem é publicada em `pedido_lines_queue` para os pedidos
   daquele arquivo, e a duplicidade é registrada em log de nível informativo.

---

### Edge Cases

- Arquivo vazio (nem cabeçalho nem rodapé): tratado como arquivo inteiro inválido (US2).
- Arquivo com cabeçalho e rodapé, mas zero pedidos entre eles: nenhuma mensagem publicada; não é
  erro, apenas um arquivo sem pedidos.
- Notificação do armazenamento referenciando um objeto que não existe mais (removido antes do
  processamento): tratado como falha técnica (US4), não como arquivo inválido.
- Nome do arquivo ou conteúdo com caracteres não-UTF-8: linha(s) afetada(s) tratada(s) como linha
  inválida (US3) se isolada, ou arquivo inválido (US2) se compromete o cabeçalho/rodapé.
- Notificação de teste automática do armazenamento (enviada uma vez ao configurar a notificação de
  evento do bucket, sem referenciar nenhum arquivo real): identificada e descartada sem tentar
  processá-la como arquivo, sem gerar erro.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE consumir notificações de criação de objeto no prefixo `uploads/` do
  armazenamento de arquivos e buscar o conteúdo do arquivo notificado.
- **FR-002**: O sistema DEVE interpretar o conteúdo do arquivo segundo o layout posicional fixo
  documentado (`docs/01-dominio-e-contratos.md` §6), identificando cabeçalho, pedidos, itens e
  rodapé.
- **FR-003**: O sistema DEVE rejeitar o arquivo inteiro, sem publicar nenhuma mensagem, quando o
  cabeçalho estiver ausente/inválido, o rodapé estiver ausente, ou os contadores do rodapé
  divergirem da quantidade real de pedidos ou itens encontrados.
- **FR-004**: O sistema DEVE rejeitar individualmente uma linha com tamanho diferente do esperado
  ou um registro de item sem pedido antecedente, sem interromper o processamento das demais linhas
  do arquivo.
- **FR-005**: O sistema DEVE rejeitar individualmente um pedido cuja contagem de itens declarada
  divirja da quantidade real de itens encontrados para aquele pedido, sem interromper o
  processamento dos demais pedidos do arquivo.
- **FR-006**: O sistema DEVE publicar em `pedido_lines_queue` uma mensagem por pedido válido do
  arquivo, contendo `source_file`, `line_number`, `operation` e `parsed` no mesmo formato do
  payload correspondente à operação (`SOLICITAR`/`EDITAR` seguem o formato de
  `solicitar_pedido_queue`/`editar_pedido_queue`, com `channel="BATCH"`).
- **FR-007**: O sistema NÃO DEVE publicar nenhuma mensagem nem confirmar a notificação original
  quando uma falha técnica de armazenamento (indisponibilidade, timeout, erro 5xx) impedir a
  leitura do conteúdo do arquivo — a notificação deve permanecer disponível para nova tentativa.
- **FR-008**: O sistema DEVE preservar a idempotência: reprocessar a mesma notificação de arquivo
  não deve gerar mensagens duplicadas em `pedido_lines_queue`.
- **FR-009**: O sistema NUNCA DEVE escrever diretamente na tabela `orders` nem chamar a API Gateway
  — a única saída de negócio deste serviço é a mensagem publicada em `pedido_lines_queue`.
- **FR-010**: O sistema DEVE expor um endpoint de verificação de saúde (`health check`) para
  orquestração local, seguindo o mesmo padrão dos demais workers do sistema.
- **FR-011**: O sistema DEVE evitar registrar em log o `customer_document` sem mascaramento.
- **FR-012**: O sistema DEVE registrar em log estruturado JSON o motivo de toda rejeição — de
  arquivo inteiro (US2), de linha (US3) ou de pedido (US3) — incluindo `source_file` e, quando
  aplicável, `line_number` (Clarifications: log estruturado é suficiente, sem artefato de relatório
  separado no armazenamento de arquivos).
- **FR-013**: Para pedidos com `operation="CANCELAR"`, o sistema DEVE publicar em
  `pedido_lines_queue` uma mensagem com `parsed` no mesmo formato do payload de
  `cancelar_pedido_queue`, usando o texto fixo `"Cancelamento via arquivo batch"` como `reason`
  (Clarifications).

### Key Entities

- **Notificação de arquivo**: evento recebido via `s3_notifications_queue` indicando que um novo
  arquivo `.txt` foi criado no prefixo `uploads/` do armazenamento de arquivos — referencia o
  arquivo pelo nome/localização, sem conter o conteúdo do arquivo.
- **Arquivo posicional**: conteúdo binário/texto lido do armazenamento a partir da notificação;
  estruturado em cabeçalho (1), pedidos (registros tipo `1`) com seus itens (registros tipo `2`), e
  rodapé (1) — layout documentado em `docs/01-dominio-e-contratos.md` §6.
- **Linha de pedido**: uma unidade de trabalho publicada em `pedido_lines_queue` — representa um
  pedido válido extraído do arquivo, com a operação (`SOLICITAR`/`EDITAR`/`CANCELAR`), a origem
  (nome do arquivo e número da linha) e os dados já no formato esperado pela fila de comando
  correspondente.
- **Erro de processamento**: registro do motivo pelo qual um arquivo inteiro, uma linha ou um
  pedido específico foi rejeitado — identifica a origem (arquivo e, quando aplicável, linha) e uma
  descrição legível do problema.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos pedidos válidos de um arquivo estruturalmente correto resultam em uma
  mensagem publicada em `pedido_lines_queue` em até alguns segundos após o upload do arquivo.
- **SC-002**: 100% dos arquivos estruturalmente inválidos (cabeçalho/rodapé ausente ou contadores
  divergentes) resultam em zero mensagens publicadas e um motivo de rejeição registrado.
- **SC-003**: Em um arquivo com pedidos válidos e inválidos misturados, 100% dos pedidos válidos
  geram mensagem, independentemente da posição dos pedidos inválidos no arquivo.
- **SC-004**: Nenhuma mensagem duplicada é publicada quando a mesma notificação de arquivo é
  entregue mais de uma vez.
- **SC-005**: Nenhuma decisão de negócio (arquivo válido ou inválido) é registrada quando o
  armazenamento de arquivos está temporariamente indisponível — 100% desses casos preservam a
  notificação original para nova tentativa.

## Assumptions

- O Lambda Line Processor (fora do escopo desta feature) é o único consumidor de
  `pedido_lines_queue` e é responsável por transformar cada linha numa chamada real ao API
  Gateway; este serviço nunca chama o API Gateway nem escreve na tabela `orders` diretamente
  (docs/01-dominio-e-contratos.md §4).
- `pedidos_shared.file_layout.parse_file` (já implementado na feature `001-fundacao-compartilhada`)
  é reaproveitado para o parsing estrutural do arquivo — esta feature não reimplementa as regras
  de layout, apenas orquestra buscar o arquivo, chamar o parser e publicar o resultado.
- Para pedidos `SOLICITAR`/`EDITAR`, o campo `channel` do `parsed` é sempre `"BATCH"` (nunca
  `"HTTP"`), consistente com `Order.source_file`/`Order.source_line` só serem preenchidos quando
  `channel == "BATCH"` (docs/01-dominio-e-contratos.md §2.2).
- O arquivo original não é movido, renomeado ou removido do armazenamento após o processamento —
  permanece no prefixo `uploads/` indefinidamente; arquivar ou expirar arquivos processados está
  fora do escopo desta feature.
- Itens (registros tipo `2`) associados a um pedido `CANCELAR` são estruturalmente exigidos pelo
  layout do arquivo (contagem mínima de 1, §6) mas não fazem parte do payload de
  `cancelar_pedido_queue` — são parseados pelo `parse_file` reaproveitado, porém ignorados ao
  montar o `parsed` de uma linha `CANCELAR`.
