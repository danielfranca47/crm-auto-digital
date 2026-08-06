# Ingestão de conhecimento — retomar revisão pendente ao reabrir o painel

**Branch:** *(a definir)*
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/knowledge-ingest-preview-aprovavel.md`.

Hoje, quando um job de ingestão termina (`status='completed'`), as categorias propostas ficam em
`jobs.result.proposed` até o utilizador revisar e aprovar via `POST /ingest/{job_id}/apply`. Se o
utilizador fechar o painel "Importar materiais" antes de revisar — nada foi escrito em
`knowledge_items` (seguro), mas também não há hoje como retomar essa revisão pendente sem
reprocessar o lote inteiro: `KnowledgeIngestPanel.tsx` sempre inicia na fase `'edit'` e não consulta
se existe um job `completed` anterior ainda sem `apply`.

A ideia é, ao abrir o painel, verificar se o utilizador tem um job de ingestão `completed` com
`proposed` não vazio e, se sim, ir direto para a fase de revisão em vez da fase de edição.

---

## Problemas Identificados (estado anterior)

1. **Sem consulta ao abrir o painel:** `KnowledgeIngestPanel.tsx` não busca jobs anteriores do
   utilizador ao montar — sempre começa em `phase='edit'`.
2. **Sem rota para listar jobs pendentes de revisão:** `routes/knowledge_ingest.py` não tem um
   endpoint tipo "último job completed com proposed não aplicado" — só `GET /ingest/{job_id}` por
   id específico.

---

## Próximos passos

Este arquivo nasce como stub — a implementação real só começa depois do diagnóstico normal
(Plan Mode) ser feito e aprovado pelo utilizador, seguindo
`docs/implementations/_guia-documentar-implementacao.md`.
