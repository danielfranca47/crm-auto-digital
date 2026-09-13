# Limpeza/expiração automática de uploads antigos

**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`fix-upload-planilhas-sem-auth.md`. Naquela implementação, os arquivos enviados
para importação de leads passaram a ficar isolados por usuário em
`data/uploads/ai/{user_id}/`, mas nenhuma rotina apaga esses arquivos depois de
processados — eles são temporários por natureza (usados só durante o fluxo de
importação de planilha do Assistente IA) e se acumulam indefinidamente em disco.

Comportamento desejado: uma rotina (job periódico, ou limpeza no momento em que o
processamento termina com sucesso) remove arquivos de upload que já não são mais
necessários, evitando crescimento indefinido do disco.

---

## Área do sistema

`backend-crm` — `routes/uploads.py`, `routes/assistente_ia.py` (`/processar`,
`/preview`), pasta `data/uploads/ai/`.

---

## Próximo passo

Este arquivo ainda não passou pelo **Passo 0 (Diagnóstico em Plan Mode)** de
`_guia-documentar-implementacao.md`. Para iniciar: entrar em Plan Mode usando o
contexto acima como ponto de partida (decidir se a limpeza é por idade do
arquivo, por já ter sido processado, ou ambos; se é job periódico ou síncrono),
responder as 3 perguntas do Passo 0, e só depois de aprovado seguir para a
criação de branch + worktree (Passo 1).
