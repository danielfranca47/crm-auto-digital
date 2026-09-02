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

## Fase 3 — Fix: `nurture_vs_discard_rule` tipado como boolean em vez de string (02/09/2026)

### Problema identificado

Achado lateral durante os testes da Fase 2 (Cenários P2/P3): `AgentConfig.nurture_vs_discard_rule`
(`frontend-crm/src/types/agente.ts`) estava tipado e usado como `boolean` em todo o
frontend, mas o backend (`backend-core/app/models/ai_profile.py`) sempre tratou a coluna
como `Optional[str]` (`"nurture"` | `"discard"` | `null`, default `"discard"`).

Isso não era só um problema de importação de arquivo — o toggle real da UI em
"Camada Follow-up → Nurture vs Descarte" (`CamadaFollowup.tsx`) fazia
`!config.nurture_vs_discard_rule`, transformando o valor em um boolean genuíno. Ao
salvar essa camada, `PUT /ai-profiles/me` rejeitava com 422 (`"Input should be a valid
string"`), impedindo o usuário de salvar qualquer alteração na camada Follow-up depois
de mexer nesse toggle uma vez. Também havia um bug de leitura: como toda string
não-vazia é truthy em JS, um perfil real vindo do backend com `"discard"` aparecia como
"Nurture passivo" na tela (o inverso do valor real).

### Correção

| Arquivo | Mudança |
|---|---|
| `frontend-crm/src/types/agente.ts` | `nurture_vs_discard_rule: boolean` → `'nurture' \| 'discard' \| null`; default `false` → `'discard'` |
| `frontend-crm/src/components/agente/CamadaFollowup.tsx` | Toggle e exibição do card "Nurture vs Descarte" passam a comparar `=== 'nurture'` em vez de truthiness; clique alterna explicitamente entre `'nurture'`/`'discard'` |

### Commits Fase 3

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | *(a registrar)* | fix: nurture_vs_discard_rule como string em vez de boolean |

### Relatório da Fase 3 — o que mudou na prática

**Antes:** o card "Nurture vs Descarte" (Camada Follow-up) podia mostrar o estado
errado ao carregar um agente já configurado, e clicar nele e depois salvar a camada
sempre falhava com um erro genérico ("Erro ao importar"/erro de salvar), sem indicar a
causa.
**Agora:** o card mostra o estado real do agente corretamente, o clique alterna entre
"Nurture ativo" e "Descarte" de forma explícita, e salvar a camada funciona nos dois
sentidos.
**Para validar:** Cenário C1, abaixo.

### Cenário C1 — Toggle Nurture vs Descarte salva corretamente nos dois sentidos
- [x] Abrir Camada Follow-up de um agente com `nurture_vs_discard_rule="discard"` no banco
- [x] Confirmar: card mostra "Descarte imediato" / badge "DESCARTE" (não invertido)
- [x] Clicar no card → muda para "Nurture passivo" / "NURTURE ATIVO" → Salvar → toast "Configuração salva" (sem 422)
- [x] Confirmar no banco: `nurture_vs_discard_rule = 'nurture'`
- [x] Clicar novamente → volta para "Descarte imediato" → Salvar → toast "Configuração salva"
- [x] Confirmar no banco: `nurture_vs_discard_rule = 'discard'`
- **Validado em:** 02/09/2026 — testado ao vivo via browser (chrome-devtools MCP), ambos os sentidos confirmados via consulta direta ao banco

---

## Ajustes Possíveis Pós-Implementação

- Nenhum identificado até o momento.
