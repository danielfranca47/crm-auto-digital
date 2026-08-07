# Ingestão de conhecimento — edição inline na tela de revisão

**Branch:** `feat/ajuste-configuracao-ai-profile`
**Status:** Em andamento

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

## Abordagem

```
Tela de revisão: cada proposta ganha um <textarea> editável (valor inicial = p.content)
  → utilizador corrige o texto de 1+ categorias, mantém aprovação via checkbox
  → "Gravar N selecionada(s)" → POST /apply { approved, edited_content: {categoria: texto atual} }
    → backend grava o texto editado (não o original do classificador) para as categorias aprovadas
```

---

## Plano de Implementação

### Fase 1 — Backend + Frontend

**Objetivo:** permitir corrigir o texto de uma proposta na tela de revisão antes de gravar.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/knowledge_ingest/ingest_worker.py` | `apply_ingest_review()` ganha parâmetro `edited_content`; usa o texto editado (com fallback pro original se vazio) ao gravar e no preview retornado |
| `backend-crm/routes/knowledge_ingest.py` | `ApplyIngestRequest` ganha campo `edited_content: Dict[str, str] = {}`; repassa para `apply_ingest_review()` |
| `frontend-crm/src/services/api.ts` | `applyKnowledgeIngest()` ganha terceiro parâmetro opcional `editedContent` |
| `frontend-crm/src/components/agente/KnowledgeIngestPanel.tsx` | Estado `editedContent: Map<string,string>`; fase `'review'` ganha `<textarea className="o-input">` editável fora do `<label>` do checkbox; `confirmApply()` envia o texto atual das categorias aprovadas |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(preencher após commit)* | *(preencher após commit)* |

---

## Checks de Validação

### Cenário P1 — Editar e gravar conteúdo corrigido
- [ ] Gerar uma proposta na revisão, editar o texto de uma categoria (ex.: corrigir um valor)
- [ ] Manter aprovada e clicar "Gravar"
- [ ] Confirmar na Base de Conhecimento que o item gravado tem o texto editado, não o original da IA
- [ ] Confirmar que a tela "Resultado da importação" mostra o preview editado
- **Pendente**

### Cenário P2 — Guarda contra conteúdo vazio
- [ ] Apagar todo o texto de uma categoria aprovada e gravar
- [ ] Confirmar que o item foi gravado com o texto original (não vazio) — guarda de segurança
- **Pendente**

### Cenário P3 — Edição em categoria desmarcada é irrelevante
- [ ] Editar o texto de uma categoria e desmarcar o checkbox antes de gravar
- [ ] Confirmar que a categoria não é gravada (comportamento normal de descarte, sem efeito da edição)
- **Pendente**

---

## Ajustes Possíveis Pós-Implementação

*(preencher se surgir algo durante a implementação/validação)*
