# Aviso de risco ao configurar handoff_policy="ignore" sem texto customizado

**Branch:** `feat/aviso-handoff-ignore-sem-texto`
**Status:** Em andamento

---

## Motivação

Durante a investigação de `sessao-teste-corrente.md` (Cenário 6 — "falar com humano") foi
confirmado que o bug crítico original (resposta vazia quando a LLM Mãe falha na 1ª
mensagem da sessão) já está corrigido no código desde 08/08/2026 (`decision_engine.py`,
commit `b1bbaaa`, graduado em `docs/architecture/llm-architecture.md`, seção "Fallback
final: falha da LLM Mãe sempre vira handoff").

Nessa mesma investigação apareceu um **caminho de silêncio diferente, que ainda existe
hoje por design**: em `backend-executors/app/services/handoff_policy.py` (linhas
114-135), se `ai_profile.handoff_policy == "ignore"` **e** `handoff_custom_text` estiver
vazio, qualquer handoff (não só falha de LLM — qualquer handoff, em qualquer turno da
conversa) devolve `next_action="ignore"` + `message_text=""`. É comportamento
intencional do backend (não é um bug de código a corrigir), mas o operador pode escolher
essa combinação em `/ai-profile` sem perceber o risco, porque a UI não avisa nada hoje.

Comportamento desejado: quando o usuário selecionar a política "Ignorar" sem preencher a
mensagem personalizada de handoff, mostrar um aviso explicando o risco e exigir um
checkbox de ciência antes de permitir salvar essa combinação no drawer.

---

## Problemas Identificados (estado anterior)

1. **Sem aviso na UI para a combinação de risco:**
   `frontend-crm/src/components/agente/CamadaIdentidade.tsx:108-139` (`DrawerHandoff`) —
   o usuário podia selecionar `handoff_policy="ignore"` e deixar `handoff_custom_text`
   vazio e salvar normalmente, sem nenhuma indicação de que o lead ficaria sem resposta
   nesse cenário.
2. **`DrawerBase` sem suporte a desabilitar o "Salvar":**
   `frontend-crm/src/components/agente/CamadaIdentidade.tsx:725-747` — o botão "Salvar"
   do rodapé do drawer não tinha como ser condicionalmente desabilitado; era necessário
   para bloquear o salvamento até a confirmação do checkbox.

---

## Abordagem

```
Usuário abre Drawer "Política de handoff" (Camada 1)
  → seleciona policy + digita (ou não) mensagem personalizada
  → isRisky = policy === "ignore" && texto vazio
      ├─ isRisky = false → botão "Salvar" habilitado normalmente
      └─ isRisky = true  → aviso "⚠ lead não recebe nenhuma resposta..." aparece
             + checkbox "Estou ciente do risco..." (desmarcado)
             → botão "Salvar" fica desabilitado até o checkbox ser marcado
  → qualquer mudança de policy ou de texto reseta o checkbox para desmarcado
```

Mudança 100% frontend — não altera `decision_engine.py` nem `handoff_policy.py`; o
comportamento do backend continua o mesmo, só a UI passa a avisar antes de permitir a
configuração.

---

## Plano de Implementação

### Fase 1 — Aviso + checkbox de ciência no Drawer de handoff

**Objetivo:** bloquear o salvamento da combinação `ignore` + texto vazio até o usuário
confirmar ciência do risco.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaIdentidade.tsx` | `DrawerBase` ganha prop opcional `saveDisabled?: boolean`, aplicada ao botão "Salvar" (`disabled` + opacidade reduzida). `DrawerHandoff` ganha estado `acknowledged`, calcula `isRisky`, renderiza aviso (`o-alert o-alert-danger`) + checkbox quando `isRisky`, e passa `saveDisabled={isRisky && !acknowledged}` para `DrawerBase`. Trocar `policy`/`text` de mudarem direto para `handlePolicyChange`/`handleTextChange` (resetam `acknowledged`). |

```tsx
// ANTES — DrawerBase sempre habilitado
<button className="o-btn o-btn-primary" onClick={onSave}>Salvar</button>

// DEPOIS — respeita saveDisabled
<button className="o-btn o-btn-primary" onClick={onSave} disabled={saveDisabled}
  style={saveDisabled ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}>Salvar</button>
```

```tsx
// DrawerHandoff — novo estado + gate
const [acknowledged, setAcknowledged] = useState(false);
const isRisky = localPolicy === 'ignore' && !localText.trim();
// ... <DrawerBase saveDisabled={isRisky && !acknowledged}> ...
{isRisky && (
  <>
    <div className="o-alert o-alert-danger">⚠ lead não recebe nenhuma resposta...</div>
    <input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} />
  </>
)}
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `020637d` | frontend: aviso + checkbox de ciência para handoff_policy=ignore sem texto |

**Detalhes do commit `020637d`:**
- `frontend-crm/src/components/agente/CamadaIdentidade.tsx` — `DrawerBase` ganha prop
  `saveDisabled`; `DrawerHandoff` ganha `acknowledged`/`isRisky`, aviso condicional e
  checkbox de confirmação.
- `docs/implementations/aviso-handoff-ignore-sem-texto.md` (novo) — este arquivo.

### Relatório da Fase 1 — o que mudou na prática

**Antes:** ao configurar a política de handoff como "Ignorar" e deixar a mensagem
personalizada em branco, o drawer salvava normalmente, sem nenhum aviso — mesmo sendo
essa a combinação que faz o bot ficar completamente mudo quando precisa transferir a
conversa para um humano.

**Agora:** assim que essa combinação é selecionada no drawer, aparece um aviso vermelho
explicando o risco, e o botão "Salvar" fica desabilitado até o usuário marcar um checkbox
confirmando que está ciente. Qualquer mudança na política ou no texto desmarca o checkbox
de novo — ele nunca fica "guardado" de uma sessão para outra.

**Para validar:** Cenários P1 a P5, abaixo.

---

## Checks de Validação

### Cenário P1 — Aviso aparece e bloqueia o salvamento
- [ ] Abrir `/ai-profile`, Camada 1 → "Política de handoff"
- [ ] Selecionar "Ignorar — sem ação automática" com o campo de mensagem vazio
- [ ] Confirmar: aviso vermelho aparece e botão "Salvar" fica desabilitado

### Cenário P2 — Checkbox libera o salvamento
- [ ] Com o aviso visível (cenário P1), marcar o checkbox "Estou ciente do risco..."
- [ ] Confirmar: botão "Salvar" habilita e o drawer fecha normalmente ao clicar

### Cenário P3 — Preencher mensagem remove o aviso
- [ ] Com policy "Ignorar" selecionada, preencher a mensagem personalizada
- [ ] Confirmar: aviso e checkbox somem, "Salvar" fica habilitado sem precisar do checkbox

### Cenário P4 — Outras políticas nunca mostram o aviso
- [ ] Selecionar "Manter bot ativo e notificar operador" ou "Desabilitar bot imediatamente"
- [ ] Confirmar: aviso nunca aparece, independente do texto estar vazio ou preenchido

### Cenário P5 — Checkbox não persiste entre aberturas
- [ ] Salvar a combinação de risco já com o checkbox marcado (cenário P2)
- [ ] Fechar e reabrir o drawer "Política de handoff"
- [ ] Confirmar: checkbox aparece desmarcado de novo (precisa reconfirmar a cada edição)

---

## Ajustes Possíveis Pós-Implementação

- Nenhum identificado até o momento — escopo é só a UI de aviso; comportamento do backend
  permanece intencionalmente inalterado.
