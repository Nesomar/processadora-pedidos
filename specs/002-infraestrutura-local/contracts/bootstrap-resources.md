# Contrato: nomes de recursos criados pelo bootstrap

Este é o "contrato" desta feature — não uma API HTTP, mas o acordo de nomes entre o que o
bootstrap cria no Ministack e o que `Settings` (pedidos_shared, feature 001) espera ler das
variáveis de ambiente. Ver data-model.md pra tabela completa.

## Regras de contrato

1. Toda variável de ambiente de nome de recurso (`ORDERS_TABLE_NAME`, `ORDERS_BUCKET_NAME`,
   `*_QUEUE_URL`) MUST estar declarada em `.env.example` (raiz do repo) — nenhum nome de recurso
   hardcoded só dentro do script de bootstrap ou só dentro de um serviço.
2. Adicionar uma fila nova (por uma spec de serviço futura) MUST: (a) adicionar a variável
   correspondente em `.env.example`, (b) adicionar a criação da fila + sua DLQ no script de
   bootstrap, (c) usar exatamente essa variável no `Settings` do serviço consumidor — os três
   passos andam juntos, nunca um sem os outros dois.
3. Nenhuma fila é adicionada ao bootstrap sem DLQ + `maxReceiveCount = 3` (constitution I.4) — a
   função "criar fila" do bootstrap não expõe um caminho que crie fila sem DLQ.
4. O bootstrap MUST ser seguro para rodar contra um Ministack que já tenha os recursos (idempotente
   — research.md #3); nenhum consumidor deste contrato pode assumir que precisa limpar o ambiente
   antes de rodar o bootstrap de novo.
