# Camada dedicada de Follow-up no AI Profile (M3)

**Branch:** `main`
**Status:** Em andamento — Fases 1-2 implementadas e validadas (25/06/2026). Fases 3-4 pendentes.
**Plano:** `docs/plans/followup-proativo-e-cancelamento-agenda.md` (M3)

---

## Motivação

A configuração de follow-up do AI Profile (cadência, tentativas, instruções por
variante, toggles de disparo automático) está hoje espalhada por 8 drawers
diferentes dentro da Camada 3 (Pipeline e comportamento), mais 1 campo
(`nurture_vs_discard_rule`) na Camada 2 (Qualificação). O operador precisa de
saber em qual aba cada coisa está, sem visão de conjunto do que controla o
follow-up. Os dois campos novos do M2 (`followup_auto_trigger_*`,
`followup_checkin_*`) já nasceram em cards isolados na Camada 3, propositalmente
preparados para serem absorvidos por esta camada dedicada.

Decisão de produto (confirmada com o utilizador): a nova camada cobre a
**configuração de negócio** do follow-up (tipos, comportamento do bot) e vive em
`/ai-profile`. A **execução/operacional** (pausar, retomar, cancelar, editar
mensagem agendada) continua exclusivamente na Central de Follow-ups
(`/follow-ups`) — sem alteração nessa página.

---

## Problemas Identificados (estado anterior)

1. **Campos de follow-up espalhados:** 17 campos em 8 drawers de
   `frontend-crm/src/components/agente/CamadaPipeline.tsx` (Camada 3) + 1 campo
   (`nurture_vs_discard_rule`) em `CamadaQualificacao.tsx` (Camada 2).
2. **Campo morto descoberto na auditoria:** `followup_h1`/`followup_h2`/`followup_h3`
   (drawer "Cadência de follow-up", `CamadaPipeline.tsx:114-127`) são lidos/escritos
   dentro de `offer_pack` (`api.ts:1309-1311` e `1425-1427`) mas **nenhum backend**
   (`backend-core`, `backend-crm`, `backend-executors`) lê esses nomes — grep
   confirmado, zero ocorrências. É um controlo cosmético: o operador acha que está
   configurando a cadência real, mas o motor usa só `followup_cadence`/
   `followup_max_attempts`/`followup_first_offset` (drawer "Follow-up avançado",
   esses sim reais).
3. **Segundo consumidor do campo morto não detectado na auditoria inicial:**
   `frontend-crm/src/components/Dashboard.tsx:83` lê `agentConfig?.followup_h1`
   dentro de `c3Checks` (barra de progresso da Camada 3) — quebra a build ao
   remover o campo do tipo `AgentConfig` se não for tratado.
4. **Docs desatualizadas:** `docs/guia-campos-ai-profile.md` (linhas 295-302)
   afirma incorretamente que `followup_state.py` lê `followup_h1/h2/h3`;
   `docs/ai-profile-fields.md` (linhas 148-150) lista o campo como
   `"Metadado / futuro"`. Ambas precisam de correção.

---

## Abordagem

```
CamadaPipeline.tsx (Camada 3)              CamadaQualificacao.tsx (Camada 2)
  ├─ 7 drawers reais de follow-up   ──┐      ├─ nurture_vs_discard_rule ──┐
  └─ DrawerFollowup (h1/h2/h3, morto) │      └─ (resto fica)              │
         │ (sai na Fase 3)            │                                  │
         ▼                            ▼                                  ▼
    REMOVIDO                  CamadaFollowup.tsx (nova Camada "⑧ Follow-up")
  (tipo, api.ts,                ├─ Seção 1 · Gatilho automático
   Dashboard.tsx,               ├─ Seção 2 · Cadência e tentativas
   docs)                        ├─ Seção 3 · Instruções de conteúdo
                                 └─ Seção 4 · Qualificação e follow-up
```

Componentes auxiliares (`EditCard`, `DrawerBase`, `SliderField`, `ToggleRow`) são
**duplicados** em `CamadaFollowup.tsx`, não extraídos para um arquivo partilhado —
segue o padrão 100% consistente já usado em todo `components/agente/` (cada
Camada já duplica a sua própria cópia local). Extrair seria um refactor maior,
fora do escopo deste M3.

---

## Plano de Implementação

### Fase 1 — Criar `CamadaFollowup.tsx` e mover os 7 drawers reais

**Objetivo:** nova Camada funcional com todos os campos reais movidos, sem tocar
nos campos mortos `followup_h1/h2/h3` ainda.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaFollowup.tsx` (novo) | Copia `DrawerFollowupAvancado`, `DrawerFollowupAutomatico`, `DrawerFollowupCheckin`, `DrawerFollowupGoalInstructions`, `DrawerCartRecoveryAttempts`, `DrawerFollowupOutcomeInstructions`, `DrawerFollowUpInstructions` de `CamadaPipeline.tsx`; componente principal com 4 seções (Seção 4 só entra na Fase 2) |
| `frontend-crm/src/components/agente/CamadaPipeline.tsx` | Remove as 7 funções de drawer movidas, as keys correspondentes de `DrawerKey`, as variáveis `_isCloserAgent`/`_isHybridAgent`/`_fuInstrValue`/`_fuInstrLabel`, os EditCards da "Seção 2" (exceto "Thresholds de follow-up", que sai na Fase 3) |
| `frontend-crm/src/pages/AiProfile.tsx` | Novo `PanelId 'followup'`, item no `navItems` (`'⑧ Follow-up'`, entre `'fluxo'` e `'conexao'`), nova função `PainelCamadaFollowup` (réplica do padrão de `PainelCamada3`), novo bloco de render |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `813244e` | `CamadaFollowup.tsx` (novo) + remoção dos 7 drawers/EditCards de `CamadaPipeline.tsx` + nova Camada em `AiProfile.tsx` |

### Relatório da Fase 1 — o que mudou na prática

**Antes:** a configuração de follow-up (cadência, disparo automático, check-in de
clientes, instruções por tipo de agente) ficava espalhada dentro da Camada 3
(Pipeline), misturada com configurações de conexão, opt-out e LGPD.

**Agora:** existe uma aba nova, "⑧ Follow-up", com tudo isso reunido em 3 seções
(Gatilho automático / Cadência e tentativas / Instruções de conteúdo). A Camada 3
continua com o resto normalmente — só perdeu a parte de follow-up, que agora vive
no lugar certo.

**Para validar:** Cenário P1, abaixo — já testado ao vivo nesta sessão (ver
notas).

---

### Fase 2 — Mover `nurture_vs_discard_rule`

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaFollowup.tsx` | Adiciona Seção 4 "Qualificação e follow-up" com o card "Nurture vs Descarte", `sub`/`help` ajustados para referenciar "Score mínimo" da Camada Qualificação |
| `frontend-crm/src/components/agente/CamadaQualificacao.tsx` | Remove o card (linhas ~1212-1220) |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `3a9b8c9` | Move `nurture_vs_discard_rule` da Camada Qualificação para a Seção 4 da Camada Follow-up |

### Relatório da Fase 2 — o que mudou na prática

**Antes:** a decisão "o que fazer com um lead que não atinge o score mínimo"
(nutrir ou descartar) ficava na Camada Qualificação, ao lado do campo de score —
mas é, na prática, um comportamento de follow-up.

**Agora:** o card "Nurture vs Descarte" vive na Seção 4 da Camada Follow-up, com
uma nota explícita de que depende do "Score mínimo" configurado em Qualificação.

**Para validar:** Cenário P2, abaixo — já testado ao vivo nesta sessão.

---

### Fase 3 — Remover os campos mortos `followup_h1/h2/h3`

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/types/agente.ts` | Remove de `OfferPackExtra`, `AgentConfig`, `DEFAULT_AGENT_CONFIG` |
| `frontend-crm/src/services/api.ts` | Remove leitura (`getConfig`) e escrita (`saveConfig`) em `offer_pack` |
| `frontend-crm/src/components/agente/CamadaPipeline.tsx` | Remove `DrawerFollowup`, `followupConfigured`, `fu1Label`, o EditCard "Thresholds de follow-up", a "Seção 2" inteira (fica vazia), a key `'followup'` do `DrawerKey` |
| `frontend-crm/src/pages/AiProfile.tsx` | `layer3Items` perde `followup_h1 > 0` (denominador `/5`→`/4`); `SummaryCard` "Cadência follow-up" é substituído por um card "Follow-up" que resume o estado do disparo automático e navega para a nova Camada |
| `frontend-crm/src/components/Dashboard.tsx` | Remove a chave `followup` de `c3Checks` (linha 83) |
| `docs/guia-campos-ai-profile.md`, `docs/ai-profile-fields.md` | Remove/corrige as menções a `followup_h1/h2/h3` |

### Fase 4 — Graduação do M3

Atualizar `docs/plans/followup-proativo-e-cancelamento-agenda.md` (M3 → graduado),
confirmar se `docs/architecture/agents.md`/`followup.md` precisam de alguma nota
sobre a nova localização na UI, e remover este arquivo de implementação.

---

## Checks de Validação

### Cenário P1 — Fase 1: campos movidos funcionam na nova Camada
- [x] Nova aba "⑧ Follow-up" aparece entre "Fluxo de Venda" e "Conexão"
- [x] Os 7 EditCards aparecem com os valores corretos (iguais aos que apareciam na Camada 3 antes)
- [x] Abrir drawer, editar (toggle "Follow-up automático"), salvar — valor atualiza no EditCard sem reload
- [x] Banner "Editando Follow-up" + "Salvar Follow-up" persiste após reload da página
- [x] Visibilidade condicional por `template_key` confirmada para `hybrid_scheduler` (mostra "Instrução por outcome", oculta "Instrução por objectivo"/"Instrução por tentativa · Carrinho", que são SDR/closer-only) — `⏭️` SDR e closer não testados ao vivo nesta sessão (sem conta de teste desses tipos disponível), confirmado por revisão de código (mesma lógica `_isCloserAgent`/`_isHybridAgent` copiada caractere-a-caractere)
- [x] Camada 3 (Pipeline): Seções 0/1/3 continuam intactas; Seção 2 só tem "Thresholds de follow-up"
- **Validado em:** 25/06/2026 — `npx tsc -b --noEmit` sem novos erros (erros pré-existentes no resto do repo, nenhum nos arquivos tocados); teste ao vivo via browser (chrome-devtools MCP) na conta de teste (`user_id=15`, `hybrid_scheduler`/`agenda`): aba "⑧ Follow-up" renderizou as 4 seções esperadas (Gatilho automático com 2 cards, Cadência e tentativas com 1 card mostrando valores reais já configurados — `120,2880,5760`/`3 tentativas`/`09:00-18:00`, Instruções de conteúdo com 2 cards do tipo hybrid); toggle "Follow-up automático" ligado/salvo/recarregado (persistiu "Ativo · 3 dia(s)" após reload), depois revertido a "Desativado" e salvo de novo para não alterar a conta de teste. Camada 3 confirmada intacta nas Seções 0/1/3, Seção 2 com apenas "Thresholds de follow-up" (campo morto, sai na Fase 3).

### Cenário P2 — Fase 2: nurture_vs_discard_rule
- [x] Card desaparece da Camada Qualificação
- [x] Card aparece na Seção 4 da Camada Follow-up, toggle funciona, persiste
- **Validado em:** 25/06/2026 — `npx tsc -b --noEmit` sem novos erros; teste ao vivo via browser: card "Score mínimo"/"Sinais de compra" confirmados como únicos restantes em "Parâmetros avançados" da Camada Qualificação; card "Nurture vs Descarte" confirmado na Seção 4 da Camada Follow-up, referenciando "Score mínimo" da Camada 2; toggle clicado (Nurture→Descarte), draft banner apareceu corretamente, "Descartar rascunho" usado para reverter sem persistir (não era necessário alterar o dado real da conta de teste só para validar o toggle).

### Cenário P3 — Fase 3: campos mortos removidos
- [ ] `npx tsc -b --noEmit` sem erros
- [ ] `rg "followup_h1|followup_h2|followup_h3" frontend-crm/src` retorna zero resultados
- [ ] Resumo: card antigo "Cadência follow-up" não aparece; novo card "Follow-up" aparece e navega certo
- [ ] Badge da Camada 3 mostra `X/4` (não `X/5`) e reflete opt-out/LGPD/reativação/mídia corretamente
- [ ] Camada 3: "Seção 2" desapareceu sem deixar espaço vazio
- [ ] Dashboard (home): barra de progresso da Camada 3 não quebra
- [ ] Salvar qualquer Camada continua funcionando; `PUT /ai-profiles/me` não envia mais `followup_h1/h2/h3`

---

## Ajustes Possíveis Pós-Implementação

- `docs/ai-profile-fields.md` está globalmente desatualizado (referencia um
  componente `AgenteConfiguracao.tsx` que não existe) — fora do escopo deste M3,
  só a tabela de `followup_h1/h2/h3` é corrigida.
