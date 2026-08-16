# Fix: campos de qualificação não editáveis/removíveis no AI Profile

**Branch:** `fix/campos-qualificacao-nao-editaveis`
**Status:** Em andamento

---

## Motivação

O utilizador está reformulando o agente de IA para um novo nicho de negócio.
Na Camada de Qualificação (AI Profile → "O que o agente precisa saber"), tinha
2 campos configurados ("Tipo de sessão", "Disponibilidade") que não conseguia
editar o nome nem remover — o drawer "Editar campo" mostrava o nome como texto
estático (sem input) e não exibia o botão "Remover campo".

Causa raiz: `frontend-crm/src/components/agente/CamadaQualificacao.tsx` só
libera edição de nome (linha 249-261) e remoção (linhas 687 e 813) para campos
cuja `key` começa com `custom_`. Campos criados manualmente pelo botão "+
Adicionar campo" sempre recebem esse prefixo (`slugify(label)` prefixado). Mas
campos gerados via "✦ Gerar com IA" vêm do backend
(`backend-crm/routes/qualification.py`, endpoints `/generate-fields` e
`/generate-fields-for-filter`), onde o prompt do LLM apenas *pede* o prefixo
`custom_` para "campos não padrão" (linha 59 e 230) sem forçar isso em código.
Quando o LLM gera um campo parecido com um campo padrão (ex.: `session_type`,
`availability`), ele não aplica o prefixo — e esse campo fica permanentemente
travado no frontend. Foi exatamente o que aconteceu com os dois campos do
utilizador.

---

## Problemas Identificados (estado anterior)

1. **Nome do campo não editável para keys sem prefixo `custom_`**
   (`frontend-crm/src/components/agente/CamadaQualificacao.tsx:249-261`) — o
   `SuggestInput` de "Nome do campo" só renderiza se `isCustom` for `true`;
   caso contrário, mostra o label como texto estático sem forma de editar.

2. **Botão "Remover campo" ausente para keys sem prefixo `custom_`**
   (`CamadaQualificacao.tsx:687` no `ModalFiltroSDR`, e `:813` na
   `SecaoCamposPlana`) — `onRemove` só é passado ao `DrawerCampo` quando
   `editingField.key.startsWith('custom_')`.

3. **Campos gerados por IA nem sempre recebem o prefixo esperado**
   (`backend-crm/routes/qualification.py:59,230`) — o prompt do LLM só
   *sugere* o prefixo `custom_`, não é garantido no código, então campos
   gerados com nome parecido a um campo padrão ficam sem o prefixo e,
   por consequência, travados no frontend (problemas 1 e 2).

---

## Abordagem

Verificado que nenhuma lógica de backend depende da permanência de um campo
específico em `qualification_fields`:

- `backend-crm/services/qualification_guardrails.py:84` define
  `_4P_SCORABLE_KEYS` (usada só para decidir se aplica o gate de score dos
  4Ps). O próprio comentário do código (linha 80-83) já prevê e trata
  deliberadamente o caso de "perfis 100% custom" (nenhuma dessas keys
  presente): o gate de score é simplesmente pulado.
- `compute_missing_fields` / `qualification_required_fields`
  (`qualification_guardrails.py:20-50`) operam sobre o que estiver
  configurado em tempo de execução — não há lista fixa de campos
  obrigatórios no backend.

Ou seja: remover ou renomear qualquer campo (padrão ou gerado por IA) é
seguro. A correção é **só no frontend** — remover a restrição `isCustom` /
`startsWith('custom_')` que condiciona a UI, liberando edição de nome e
remoção para **qualquer** campo, independente da origem da `key`. A `key` em
si não muda — só o `label` (nome exibido) passa a ser sempre editável, como já
acontecia para campos custom (o `handleSaveField` já preserva a `key` ao
salvar: `f.key === updated.key ? updated : f`).

---

## Plano de Implementação

### Fase 1 — Liberar edição de nome e remoção para todos os campos

**Objetivo:** permitir renomear e remover qualquer campo de qualificação, não
só os criados manualmente com prefixo `custom_`.

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/components/agente/CamadaQualificacao.tsx` | `DrawerCampo`: input de nome sempre editável (remove o branch condicionado a `isCustom`); `ModalFiltroSDR` e `SecaoCamposPlana`: `onRemove` sempre passado ao `DrawerCampo`, sem checar prefixo da `key` |

```tsx
// ANTES (linha 249 e 258-261)
const isCustom = local.key.startsWith('custom_');
...
{isCustom
  ? <SuggestInput ... />
  : <div ...>{local.label}</div>
}

// DEPOIS
<SuggestInput className="o-input" value={local.label} onChange={e => up('label', e.target.value)} placeholder="Ex: Nome do pet" />
```

```tsx
// ANTES (linha 687 e 813)
onRemove={editingField.key.startsWith('custom_') ? () => handleRemoveField(editingField.key) : undefined}

// DEPOIS
onRemove={() => handleRemoveField(editingField.key)}
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `afed194` | Nome do campo sempre editável + "Remover campo" liberado para qualquer campo |

**Detalhes do commit `afed194`:**
- `frontend-crm/src/components/agente/CamadaQualificacao.tsx` — `DrawerCampo` removeu a condição `isCustom` que trocava o input de nome por texto estático; `ModalFiltroSDR` e `SecaoCamposPlana` removeram a condição `key.startsWith('custom_')` ao passar `onRemove`

### Relatório da Fase 1 — o que mudou na prática

**Antes:** campos de qualificação gerados via "✦ Gerar com IA" (ou qualquer
campo cuja key não começasse com `custom_`) ficavam travados — o nome
aparecia como texto fixo, sem input, e o botão "Remover campo" não existia.
**Agora:** qualquer campo, independente de como foi criado, pode ter o nome
renomeado e pode ser removido pelo drawer "Editar campo".
**Para validar:** Cenários F1, F2 e F3, abaixo.

---

## Checks de Validação

### Cenário F1 — Renomear campo existente sem prefixo `custom_`
- [ ] Abrir AI Profile → Camada de Qualificação → campo "Tipo de sessão" (ou
      qualquer campo com nome padrão/gerado por IA)
- [ ] Confirmar: input de nome está editável
- [ ] Alterar o nome, salvar, reabrir o campo → confirmar que o novo nome
      persistiu
- **Pendente**

### Cenário F2 — Remover campo existente sem prefixo `custom_`
- [ ] Abrir o campo "Disponibilidade" (ou outro campo travado)
- [ ] Confirmar: botão "Remover campo" está visível
- [ ] Clicar em remover → confirmar que o campo some da lista e não reaparece
      após salvar o AI Profile
- **Pendente**

### Cenário F3 — Regressão: campo custom criado do zero continua funcionando
- [ ] Clicar "+ Adicionar campo" → criar um novo campo
- [ ] Confirmar: nome editável e botão remover disponíveis, como antes
- **Pendente**

---

## Ajustes Possíveis Pós-Implementação

- O prompt do LLM em `backend-crm/routes/qualification.py` (linhas 59, 230)
  continua apenas "sugerindo" o prefixo `custom_` sem garanti-lo — não é mais
  necessário corrigir isso agora que o frontend não depende do prefixo para
  liberar edição/remoção, mas o prefixo ainda é usado para gerar a `key`
  inicial de campos novos (`slugify`). Não há ação pendente aqui.
