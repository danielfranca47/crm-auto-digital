# Mover lembrete de reunião (ao lead) da Camada Apresentação para a Camada Follow-up

> **Nota:** este arquivo foi criado retroativamente — a implementação já estava
> concluída, testada e commitada quando o utilizador perguntou se o ciclo de
> `docs/implementations/` tinha sido seguido. Não tinha sido (Plan Mode foi usado,
> mas o arquivo de implementação foi pulado). Criado agora só para fechar o
> registo formal antes de graduar.

---

**Branch:** `main`
**Status:** Todos os cenários validados

---

## Motivação

O utilizador reportou confusão entre dois mecanismos diferentes que pareciam
sobrepostos: o "Lembrete de reunião" (enviado ao **lead**, horas antes da sessão)
e o "Dossiê pré-reunião" (enviado ao **operador**). Os dois viviam na mesma
Camada 5 · Apresentação, lado a lado, com nomes parecidos.

Pedido explícito do utilizador: mover a configuração das horas de envio do
lembrete **ao lead** para a Camada Follow-up — já que conceitualmente é uma
mensagem automática programada para o lead, mesma família dos outros disparos
de follow-up — e deixar o Dossiê (operador) isolado em Apresentação.

---

## Problemas Identificados (estado anterior)

1. **Dois mecanismos lead-facing vs. operator-facing na mesma seção visual**
   (`frontend-crm/src/components/agente/CamadaApresentacao.tsx`) — "Lembretes de
   reunião" (lead) e "Dossiê pré-reunião" (operador) apareciam em sequência,
   sem nenhuma separação conceptual clara na UI.

---

## Abordagem

Realocação pura de UI — sem mudança de backend. `appointment_reminder_offsets`
continua sendo lido/escrito exactamente igual em
`frontend-crm/src/services/api.ts` (`appointment_reminder_h1`/`h2` no
`AgentConfig` continuam mapeados para esse mesmo campo). Mesmo padrão já usado
no M3 para mover `nurture_vs_discard_rule` de Qualificação para Follow-up.

```
CamadaApresentacao.tsx                    CamadaFollowup.tsx
  Seção: Lembretes de reunião    ──move──►   Seção 0 · Lembrete de reunião
  Seção: Dossiê pré-reunião       (fica)      Seção 1 · Gatilho automático
  ...                                        ...
```

A nova seção em `CamadaFollowup.tsx` só renderiza quando
`isScheduleMode = agent_mode !== 'direto' && agent_mode !== 'closer'` —
mesma condição que já controlava a visibilidade da própria Camada 5.

---

## Plano de Implementação

### Fase única — mover seção + atualizar subtítulos + doc

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaApresentacao.tsx` | Remove `DrawerLembretes`, entrada `'lembretes'` do `DrawerKey`, variável `lembretes`, bloco "Seção: Lembretes" e seu render. "Dossiê pré-reunião" inalterado |
| `frontend-crm/src/components/agente/CamadaFollowup.tsx` | Adiciona `DrawerLembretes` (mesmo conteúdo), `isScheduleMode`, nova "Seção 0 · Lembrete de reunião" condicional, e o render do drawer |
| `frontend-crm/src/pages/AiProfile.tsx` | Corrige subtítulo da Camada 5 (deixa de citar "lembretes de reunião") e da Camada Follow-up (passa a citar "lembrete de reunião") |
| `docs/ai-profile-fields.md` | Move a linha de `appointment_reminder_h1`/`h2` da tabela "Camada 5 — Apresentação" para a tabela "Follow-up" |

### Commits

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `53352c2`* | Move `DrawerLembretes`/seção de `CamadaApresentacao.tsx` para `CamadaFollowup.tsx`; atualiza `docs/ai-profile-fields.md` |
| 2 | `0a41e29` | Corrige subtítulos de Camada 5 e Camada Follow-up em `AiProfile.tsx` |

\* *Este commit foi gerado pelo hook automático `Stop` (`.claude/settings.json`), removido depois por decisão do utilizador — ver `a59a03b`. O hash fica registado aqui porque é o commit real que contém a mudança de código, mesmo tendo sido criado pelo hook em vez de um `git commit` explícito desta tarefa.*

---

## Checks de Validação

### Cenário P1 — Seção some da Camada 5, aparece na Camada Follow-up
- [x] Login na conta de teste (`hybrid_scheduler` / `agenda`), abrir `/ai-profile`
- [x] Abrir Camada 5 · Apresentação — confirmar que só resta "Dossiê pré-reunião" (sem "Lembretes de reunião")
- [x] Abrir Camada Follow-up — confirmar nova "Seção 0 · Lembrete de reunião" no topo, com os valores reais (`48h e 6h antes`)
- **Validado em:** 25/06/2026 — confirmado via snapshot do browser (chrome-devtools MCP)

### Cenário P2 — Editar e salvar persiste
- [x] Abrir drawer "Lembretes automáticos" na Camada Follow-up
- [x] Alterar 1º lembrete de 48h para 20h, salvar a camada
- [x] Recarregar a página — valor `20h e 6h antes` persiste (round-trip real via `PUT`/`GET /ai-profiles/me`)
- [x] Restaurado para `48h e 6h antes` (valor original da conta de teste) ao final do teste
- **Validado em:** 25/06/2026

### Cenário P3 — `tsc` sem erros novos
- [x] `npx tsc -b --noEmit` no `frontend-crm` — zero erros nos dois arquivos tocados
- **Validado em:** 25/06/2026

---

## Ajustes Possíveis Pós-Implementação

Nenhum identificado — mudança pequena e auto-contida, sem gaps conhecidos.
