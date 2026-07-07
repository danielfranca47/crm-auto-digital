# Toggle de tema claro/escuro na página AI Profile

**Branch:** `main`
**Status:** Em andamento

---

## Motivação

A página `/ai-profile` (Identidade do Agente Orion, `AiProfile.tsx`) só existe em
tema escuro hoje, mesmo o resto do CRM já tendo um mecanismo de tema claro/escuro
funcional (botão sol/lua no `CrmHeader`, estado em `ThemeContext`, persistido em
`localStorage` sob a chave `crm-theme`). O usuário quer que o AI Profile ganhe o
mesmo toggle.

Causa raiz: `AiProfile.tsx` é envolvido por `OrionShell`, que carrega `orion.css`.
O seletor `.orion-shell` redefine as variáveis shadcn (`--background`,
`--foreground`, etc.) e ~24 tokens próprios (`--o-bg`, `--o-text`, `--o-active`,
...) com valores fixos de tema escuro — sem nenhuma variante clara. Como o
`ThemeProvider` já envolve toda a árvore de rotas (incluindo `/ai-profile`) e já
aplica a classe `light`/`dark` no `<html>`, não é necessário novo estado/contexto —
só falta (1) um botão que chame `toggleTheme()` já existente, e (2) ensinar
`orion.css` a reagir à classe `.light` herdada do `<html>`.

---

## Problemas Identificados (estado anterior)

1. **Sem botão de toggle na topbar do Orion:** `frontend-crm/src/pages/AiProfile.tsx`
   linhas ~572-586 — a topbar tem "↕ Exportar/Importar", "? Entenda os tipos de
   agentes" e "← CRM", mas nenhum controle de tema.
2. **`orion.css` nunca reage à classe `.light`:** `frontend-crm/src/styles/orion.css`
   linhas 7-59 — o seletor `.orion-shell` define uma única paleta (escura) sem
   nenhum bloco `.light .orion-shell`.

---

## Abordagem

```
Usuário clica no toggle (novo botão em AiProfile.tsx)
  → toggleTheme() já existente (ThemeContext) alterna classe light/dark no <html>
  → orion.css ganha bloco `.light .orion-shell { ... }` com paleta clara
       → tokens shadcn + ~24 tokens --o-* redefinidos
       → resto da UI (10 abas, ~29 componentes) resolve automaticamente via var(--o-*)
```

---

## Plano de Implementação

### Fase 1 — Botão de toggle na topbar

**Objetivo:** expor o `toggleTheme()` já global na UI do AI Profile

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/pages/AiProfile.tsx` | Importa `Sun`/`Moon` (lucide-react) e `useTheme`; adiciona botão `o-btn` no grupo de ações da topbar |

### Fase 2 — Paleta clara do Orion Design System

**Objetivo:** fazer `orion.css` renderizar corretamente quando `<html>` tem classe `.light`

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/styles/orion.css` | Novo bloco `.light .orion-shell { ... }` redefinindo tokens shadcn + `--o-*` |

---

## Checks de Validação

### Cenário P1 — Toggle alterna e persiste
- [ ] Abrir `/ai-profile`, clicar no botão de tema
- [ ] Confirmar: UI muda para claro, `localStorage['crm-theme']` = `light`
- [ ] Reload da página mantém o tema escolhido

### Cenário P2 — Legibilidade nas 10 abas em modo claro
- [ ] Percorrer Resumo, Identidade, Qualificação, Pipeline, Conhecimento(+Wizard),
      Apresentação, Oferta, Fluxo de Venda, Follow-up, Conexão
- [ ] Confirmar: texto, bordas, badges de status legíveis, sem "manchas escuras"

### Cenário P3 — Regressão do tema escuro
- [ ] Alternar de volta para escuro
- [ ] Confirmar: nada mudou visualmente em relação ao estado anterior à Fase 2

### Cenário P4 — Herança em outras páginas Orion
- [ ] Abrir `TiposAgentes.tsx` / `DebugAiProfile.tsx` com tema já em claro
- [ ] Confirmar: herdam a paleta clara mesmo sem toggle próprio

---

## Ajustes Possíveis Pós-Implementação

- Valores exatos de hex/HSL da paleta clara são uma proposta de design inicial;
  ajustáveis sem alterar a arquitetura caso o QA visual revele baixo contraste.
