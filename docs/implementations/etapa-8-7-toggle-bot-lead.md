# Toggle Bot por Lead Individual

**Branch:** `etapa-8-6-audio-texto`
**Status:** Em andamento

---

## Motivação

O usuário pode precisar desativar o bot para um lead específico em qualquer fase do funil — por exemplo, por bug no atendimento, conversão offline, ou para delegar a um operador humano. A desativação global do bot não é adequada para esses casos.

Além disso, ao reativar o bot após desativação manual, o agente provavelmente não terá contexto suficiente para retomar a venda. O sistema deve avisar o usuário sobre esse risco antes de confirmar qualquer uma das ações.

---

## Problemas Identificados (estado anterior)

1. **Sem botão de desativação manual:** A UI não oferecia forma de desativar o bot por lead — apenas a reativação estava disponível (via alert block). A desativação só ocorria automaticamente (category_closing, fallback de mídia inválida).
2. **Sem aviso de perda de contexto:** Ao reativar o bot após pausa manual, o usuário não era alertado sobre o risco de o agente não ter contexto suficiente para retomar a conversa.
3. **`manual_disable` sem label amigável:** O campo `bot_disabled_reason` armazenava a string bruta — não havia tratamento específico para exibir "Desativado manualmente" no motivo da pausa.

---

## Abordagem

```
Bot ATIVO
  → Botão "Desativar bot" no header do card
  → Modal com aviso + checkbox obrigatório
  → Confirmar → bot_disabled=true, reason="manual_disable"
  → Badge "Agente desativado" + alert block aparecem

Bot DESATIVADO (reason=manual_disable)
  → Alert block com "Reativar bot"
  → Clique → Modal de aviso pós-pausa manual + checkbox obrigatório
  → Confirmar → bot_disabled=false

Bot DESATIVADO (category_closing / reunião agendada)
  → Alert block com "Reativar bot"
  → Clique → reativa diretamente (sem modal adicional — comportamento anterior mantido)
```

A distinção no modal de reativação é feita por `bot_disabled_reason === "manual_disable"`.

---

## Plano de Implementação

### Fase 1 — UI + Modais de confirmação

**Objetivo:** Adicionar botão de desativação no header e modais de aviso com checkbox obrigatório.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/LeadCardDialog.tsx` | Imports AlertDialog; 4 novos estados; `handleDisableBot`; `handleReactivateBot` modificado; botão no header; 2 AlertDialogs; label `manual_disable` no `botPauseReason` |

**Detalhes:**
- Import de `AlertDialog` e subcomponentes adicionado ao bloco de imports
- Estados: `showDisableModal`, `showReactivateWarningModal`, `disableAware`, `reactivateAware`
- `handleDisableBot`: chama `api.setLeadBotDisabled(id, { disabled: true, reason: "manual_disable" })`, fecha modal, limpa checkbox
- `handleReactivateBot`: se `bot_disabled_reason === "manual_disable"` e modal ainda não aberto, abre o modal de aviso em vez de reativar diretamente
- Botão "Desativar bot" renderizado no header (grupo de botões direito) somente quando `!currentLead.bot_disabled`
- `botPauseReason`: novo caso `"manual_disable"` → `"Desativado manualmente"`
- Dois AlertDialogs ao final do JSX (antes de `</DialogContent>`)

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `dd080c8` | Import AlertDialog, estados, handleDisableBot, handleReactivateBot com modal, botão header, 2 AlertDialogs, label manual_disable |

---

## Checks de Validação

### Cenário P1 — Botão aparece quando bot está ativo
- [ ] Abrir card de um lead com `bot_disabled=false`
- [ ] Confirmar que botão "Desativar bot" aparece no header (ao lado de Excluir)

### Cenário P2 — Modal de desativação com checkbox obrigatório
- [ ] Clicar em "Desativar bot"
- [ ] Confirmar que modal abre com texto de aviso
- [ ] Confirmar que botão "Desativar" fica desabilitado sem marcar o checkbox
- [ ] Marcar checkbox e confirmar que botão fica habilitado

### Cenário P3 — Desativação confirma e atualiza UI
- [ ] Com checkbox marcado, clicar "Desativar"
- [ ] Confirmar: badge "Agente desativado" aparece no header do card
- [ ] Confirmar: motivo "Desativado manualmente" exibido no alert block
- [ ] Confirmar: botão "Desativar bot" desaparece do header

### Cenário P4 — Modal de reativação após pausa manual
- [ ] Com lead `bot_disabled=true, reason="manual_disable"`, clicar "Reativar bot"
- [ ] Confirmar que modal de aviso abre com texto sobre pausa manual
- [ ] Confirmar que botão "Reativar mesmo assim" fica desabilitado sem checkbox
- [ ] Marcar checkbox, clicar confirmar → bot reativado

### Cenário P5 — Reativação após category_closing sem modal adicional
- [ ] Com lead `bot_disabled=true, reason="category_closing"`, clicar "Reativar bot"
- [ ] Confirmar que reativa diretamente (sem modal de aviso pós-manual)

---

## Ajustes Possíveis Pós-Implementação

- Por ora, o botão "Desativar bot" aparece em qualquer fase do funil. Poderia ser ocultado em certas categorias (ex: `archived`) se necessário no futuro.
- A recomendação de fornecer contexto no follow-up antes de reativar é textual (modal). Integração futura com o campo de instruções do follow-up poderia reforçar isso.
