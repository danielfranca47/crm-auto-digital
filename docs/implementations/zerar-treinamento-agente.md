# Zerar treinamento + escolha na importação

**Branch:** `feat/zerar-treinamento-agente`
**Status:** Em andamento

---

## Motivação

O usuário está em produção, no AI Profile, e quer recriar um agente do zero. Hoje já
existe exportar/importar configuração + treinamento (`AgentExportImportPanel.tsx` +
`/playground/training/export|import`), mas faltam duas coisas:

1. **Zerar treinamento**: não há como limpar os exemplos de treinamento
   (`playground_training_items`, feedback do Playground) para recomeçar o
   aprendizado do zero, sem precisar importar um arquivo.
2. **Escolha na importação**: hoje, ao importar um arquivo que inclui treinamento,
   ele **sempre substitui** o treinamento atual (DELETE + INSERT incondicional em
   `playground_import_training`, `backend-crm/routes/playground.py:1495`). O
   usuário quer poder escolher entre "Substituir treinamento" ou "Manter
   treinamento atual" no momento da importação.

"Treinamento" aqui = os itens de `playground_training_items` (few-shot de feedback
do Playground), não o AI Profile inteiro — o reset é só dessa base de aprendizado.

---

## Abordagem

```
AgentExportImportPanel ganha 3ª aba "Zerar treinamento"
  → checkbox de ciência habilita botão
  → DELETE /playground/training → limpa playground_training_items do user_id

AgentExportImportPanel · aba Importar (quando arquivo inclui treinamento)
  → radios "Substituir" (default) | "Manter treinamento atual"
  → handleImport() só chama importTraining() se escolha = "Substituir"
```

---

## Plano de Implementação

### Fase 1 — Backend: endpoint de reset de treinamento

**Objetivo:** permitir apagar todos os itens de treinamento do usuário sem
precisar importar um arquivo.

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/playground.py` | Novo endpoint `DELETE /playground/training` — `DELETE FROM playground_training_items WHERE user_id = ?`, retorna `{"deleted": N}`, loga `training_reset` |
| `frontend-crm/src/services/api.ts` | Novo client `api.playground.resetTraining()` |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|

---

### Fase 2 — Frontend: aba "Zerar treinamento" + escolha na importação

**Objetivo:** expor o reset na UI com confirmação, e permitir escolher
substituir/manter treinamento ao importar.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/AgentExportImportPanel.tsx` | Nova aba `reset` com checkbox de ciência + botão; nova escolha `replace`\|`keep` na aba `import`, condicional a `handleImport()` |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|

---

## Checks de Validação

### Cenário P1 — Zerar treinamento
- [ ] Abrir modal Exportar/Importar → aba "Zerar treinamento"
- [ ] Botão desabilitado sem marcar checkbox
- [ ] Marcar checkbox → botão habilita → confirmar → sucesso exibido
- **Pendente**

### Cenário P2 — Importar substituindo treinamento (comportamento atual preservado)
- [ ] Importar arquivo com treinamento, escolher "Substituir" (default)
- [ ] Confirmar: treinamento anterior é removido e o do arquivo é aplicado
- **Pendente**

### Cenário P3 — Importar mantendo treinamento atual
- [ ] Importar arquivo com treinamento, escolher "Manter treinamento atual"
- [ ] Confirmar: configuração do AI Profile é aplicada, mas treinamento existente permanece intacto
- **Pendente**

---

## Ajustes Possíveis Pós-Implementação

- Nenhum identificado até o momento.
