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
| 1 | `773a240` | backend: DELETE /playground/training + client resetTraining() |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** não existia nenhuma forma (nem na tela, nem por trás dos panos) de
apagar o treinamento do agente sem importar um arquivo por cima.
**Agora:** existe uma rota no servidor que apaga todo o treinamento do
usuário atual. Ainda não aparece nada na tela — isso é a Fase 2.
**Para validar:** nenhum cenário isolado; valida-se junto com os Cenários da
Fase 2, abaixo.

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
| 1 | `a3e8d81` | frontend: aba "Zerar treinamento" + escolha substituir/manter na importação |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** o modal "Exportar / Importar agente" só tinha duas abas. Ao
importar um arquivo com treinamento, ele sempre substituía o treinamento
atual, sem opção de escolha — e não havia como zerar o treinamento sem
importar um arquivo.
**Agora:** o modal tem uma terceira aba, "Zerar treinamento", que apaga todo
o treinamento da conta atual (exige marcar "Estou ciente que essa ação não
pode ser desfeita" antes de habilitar o botão). Na aba "Importar", quando o
arquivo escolhido inclui treinamento, aparecem dois botões de opção:
"Substituir treinamento atual" (continua sendo o padrão pré-marcado) e
"Manter treinamento atual" — se essa segunda opção for escolhida, só a
configuração do agente é aplicada e o treinamento existente não é tocado.
**Para validar:** Cenários P1, P2 e P3, abaixo.

---

## Checks de Validação

### Cenário P1 — Zerar treinamento
- [x] Abrir modal Exportar/Importar → aba "Zerar treinamento"
- [x] Botão desabilitado sem marcar checkbox
- [x] Marcar checkbox → botão habilita → confirmar → sucesso exibido
- **Validado em:** 01/09/2026 — testado ao vivo via browser (chrome-devtools MCP) com usuário de teste local; mensagem "2 exemplo(s) de treinamento removido(s)." exibida e confirmado no banco (`playground_training_items` zerado para o usuário)

### Cenário P2 — Importar substituindo treinamento (comportamento atual preservado)
- [x] Importar arquivo com treinamento, escolher "Substituir" (default)
- [x] Confirmar: treinamento anterior é removido e o do arquivo é aplicado
- **Validado em:** 01/09/2026 — testado ao vivo; antes da importação havia 2 itens ("Exemplo atual 1/2"), depois só o item do arquivo ("Item do arquivo importado") — confirmado via consulta direta ao banco

### Cenário P3 — Importar mantendo treinamento atual
- [x] Importar arquivo com treinamento, escolher "Manter treinamento atual"
- [x] Confirmar: configuração do AI Profile é aplicada, mas treinamento existente permanece intacto
- **Validado em:** 01/09/2026 — testado ao vivo; os 2 itens ("Exemplo atual 1/2") permaneceram intactos após a importação, item do arquivo não foi adicionado — confirmado via consulta direta ao banco. Aviso de substituição de treinamento corretamente ocultado na UI ao selecionar "Manter"

---

## Ajustes Possíveis Pós-Implementação

- **Achado lateral (pré-existente, fora do escopo desta implementação):**
  `DEFAULT_AGENT_CONFIG.nurture_vs_discard_rule` (`frontend-crm/src/types/agente.ts`)
  usa `false` (boolean) como default, mas o backend (`backend-core/app/api/ai_profiles.py`)
  espera `Optional[str]`. Isso só se manifesta quando um `profilePatch` de importação
  não inclui esse campo (ex.: um arquivo `.json` editado manualmente, ou um formato de
  exportação futuro que omita o campo) — nesse caso `PUT /ai-profiles/me` falha com 422
  (`"Input should be a valid string"`). Um export real gerado pelo próprio painel nunca
  aciona isso, porque `getConfig()` sempre popula esse campo com uma string válida
  (`"discard"`/`"nurture"`). Confirmado ao vivo durante os testes desta implementação
  (ver Cenários P2/P3 acima) — corrigido ali apenas nos arquivos de teste manuais, não
  no código-fonte. Sugestão: trocar o default de `DEFAULT_AGENT_CONFIG.nurture_vs_discard_rule`
  para `"discard"` (ou `null`) num fix separado.
