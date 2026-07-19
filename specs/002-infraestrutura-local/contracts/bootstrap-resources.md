# Contrato: recursos criados pelo bootstrap

"Contrato" = o acordo de nomes entre o que o bootstrap cria no Ministack e o que `Settings`
(pedidos_shared, feature 001) espera ler. Ver data-model.md pra tabela completa.

## Regras de contrato

1. Toda variável de nome de recurso MUST estar em `.env.example` (raiz do repo) — nenhum nome
   hardcoded só no bootstrap ou só num serviço.
2. As 9 filas, as 2 tabelas e o bucket (com notificação) são o conjunto **completo** e **fechado**
   do domínio atual — não "conjunto mínimo de exemplo" como numa versão anterior desta feature.
   Se `docs/01-dominio-e-contratos.md` ganhar uma fila/tabela nova no futuro, o bootstrap MUST ser
   estendido junto com a atualização daquele documento, nunca antes.
3. Nenhuma fila é criada sem DLQ + `maxReceiveCount = 3` (constitution I.4).
4. A tabela `orders` MUST ser criada com `GSI1` e `GSI2` já na definição inicial (Ministack não
   suporta adicionar GSI via update de forma simples) — não existe "criar tabela simples primeiro,
   adicionar índice depois" neste contrato.
5. O bootstrap MUST ser seguro pra rodar contra um Ministack que já tenha os recursos (idempotente);
   a notificação de evento do bucket especificamente MUST comparar config existente vs esperada
   antes de escrever (research.md #5) — nunca sobrescrever incondicionalmente.
