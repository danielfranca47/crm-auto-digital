# Ingestão de conhecimento — retomar revisão pendente ao reabrir o painel

**Branch:** `feat/ajuste-configuracao-ai-profile`
**Status:** Em andamento

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

## Problemas Identificados (estado anterior)

1. **Sem consulta ao abrir o painel:** `KnowledgeIngestPanel.tsx` não busca jobs anteriores do
   utilizador ao montar — sempre começa em `phase='edit'`.
2. **Sem rota para listar jobs pendentes de revisão:** `routes/knowledge_ingest.py` não tem um
   endpoint tipo "último job completed com proposed não aplicado" — só `GET /ingest/{job_id}` por
   id específico.
3. **Bug adjacente encontrado durante o diagnóstico:** `apply_ingest_review()`
   (`backend-crm/services/knowledge_ingest/ingest_worker.py:151`) só remove de `result["proposed"]`
   as categorias que foram efetivamente aplicadas (`applied_keys`) — categorias desmarcadas pelo
   utilizador (decisão de "não gravar") ou que colidiram com `now_existing` ficam presas em
   `proposed` para sempre. Sem corrigir isso, a feature de retomada reabriria repetidamente jobs já
   revisados e descartados pelo utilizador.

---

## Abordagem

```
Painel monta → GET /api/knowledge/ingest/pending
  ├─ existe job completed do usuário com result.proposed não vazio (apply nunca chamado)
  │    → carrega status/result desse job → phase='review' direto
  └─ nenhum → phase='edit' (fluxo normal)
```

**Definição adotada de "pendente":** a revisão de um job só é considerada encerrada quando
`POST /apply` é chamado nele (mesmo "Continuar sem gravar" com zero aprovados conta como decisão
tomada). `apply_ingest_review` passa a esvaziar `result["proposed"]` por completo ao final de cada
chamada — tudo que estava proposto nessa leva foi decidido: aplicado, já aplicado, colidiu com item
existente (`now_existing`), ou descartado por desmarcação.

---

## Plano de Implementação

### Fase 1 — Backend + Frontend + Docs

**Objetivo:** painel retoma a revisão pendente ao reabrir, sem reprocessar o lote.

| Arquivo | O que muda |
|---|---|
| `backend-crm/services/knowledge_ingest/ingest_worker.py` | `apply_ingest_review()`: `result["proposed"] = []` ao final (corrige retenção de categorias descartadas/colididas); nova função `find_pending_review_job_id(user_id)` |
| `backend-crm/routes/knowledge_ingest.py` | Nova rota `GET /api/knowledge/ingest/pending`, declarada antes de `GET /{job_id}` |
| `frontend-crm/src/services/api.ts` | Novo tipo `KnowledgeIngestPendingResponse` + método `crm.getPendingKnowledgeIngestReview()` |
| `frontend-crm/src/components/agente/KnowledgeIngestPanel.tsx` | `Phase` ganha `'checking'` (estado inicial); `useEffect` de mount consulta `/pending` e pula para `phase='review'` se houver pendência |
| `docs/architecture/knowledge-base.md` | Reescreve a seção "Se o utilizador fechar o painel sem revisar" para descrever o novo fluxo de retomada |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `942e68b` | backend: fix apply_ingest_review + rota /pending; frontend: fase 'checking' + resume; docs |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se você fechasse a janela "Importar materiais" depois da IA terminar de analisar seus
arquivos, mas antes de você revisar e confirmar o que gravar, essa análise ficava perdida — só era
possível recuperá-la reenviando os mesmos materiais e esperando a IA processar tudo de novo.

**Agora:** ao reabrir "Importar materiais", o painel verifica automaticamente se há uma análise já
pronta esperando revisão e, se houver, leva você direto para a tela de revisão com o resultado
que a IA já tinha gerado — sem reprocessar nada. Também corrigi um efeito colateral: antes, mesmo
depois de você revisar e decidir não gravar algumas seções, essas seções ficavam marcadas como
"pendentes" para sempre; agora, terminar a revisão (mesmo sem aprovar nada) encerra a pendência de
verdade.

**Para validar:** Cenários P1, P2 e P3, abaixo.

---

## Checks de Validação

### Cenário P1 — Retomar revisão pendente ao reabrir o painel
- [ ] Enviar 1 fonte que cubra uma categoria vazia, aguardar `phase='review'`
- [ ] Fechar o modal sem aprovar nada (sem chamar apply)
- [ ] Reabrir "Importar materiais" → deve pular direto para a tela de revisão com as mesmas propostas
- **Pendente**

### Cenário P2 — Job revisado não reaparece
- [ ] Na tela de revisão retomada, aprovar 1 categoria e confirmar → `phase='done'`
- [ ] Fechar e reabrir de novo → deve voltar para `phase='edit'` limpo (mesmo tendo desmarcado outras categorias na revisão anterior)
- **Pendente**

### Cenário P3 — Mesmo comportamento a partir do wizard de onboarding
- [ ] Repetir o Cenário P1 a partir de `StepImport` (wizard), não só do painel normal
- **Pendente**

---

## Ajustes Possíveis Pós-Implementação

*(preencher se surgir algo durante a implementação/validação)*
