# Ingestão de conhecimento — edição inline na tela de revisão

**Branch:** *(a definir)*
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/knowledge-ingest-preview-aprovavel.md`.

Hoje, a tela "Revise antes de gravar" (`KnowledgeIngestPanel.tsx`, fase `'review'`) só permite
aprovar ou descartar cada categoria proposta pela IA — o conteúdo é mostrado como texto estático,
sem forma de corrigir um valor errado (ex.: um preço mal extraído) antes de gravar. Hoje a única
forma de corrigir é aprovar mesmo assim e editar depois, já dentro da base de conhecimento
(`EDITAR` no card do item).

A ideia é permitir editar o texto de cada proposta diretamente na tela de revisão, antes do apply —
o conteúdo editado é o que é gravado quando a categoria é aprovada.

---

## Problemas Identificados (estado anterior)

1. **Conteúdo somente leitura na revisão:** `KnowledgeIngestPanel.tsx`, fase `'review'`, renderiza
   `p.content` como texto estático (`<div>{p.content}</div>`) — sem campo editável.
2. **Apply usa sempre o conteúdo original:** `apply_ingest_review()`
   (`backend-crm/services/knowledge_ingest/ingest_worker.py`) grava `entry.get("content")` vindo de
   `jobs.result.proposed` tal como o classificador gerou — não há forma do frontend enviar uma
   versão editada.

---

## Próximos passos

Este arquivo nasce como stub — a implementação real só começa depois do diagnóstico normal
(Plan Mode) ser feito e aprovado pelo utilizador, seguindo
`docs/implementations/_guia-documentar-implementacao.md`.
