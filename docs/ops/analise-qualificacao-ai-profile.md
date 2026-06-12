# Análise: Qualificação, AI Profile e Base de Conhecimento

> Documento de resposta às dúvidas levantadas em 2026-05-04.  
> Não substitui docs de arquitetura — foca em **como as peças se conectam na prática**.

---

## 1 — Campos do AI Profile relacionados à qualificação

Estes são os campos do modelo `AIProfile` (`backend-core/app/models/ai_profile.py`) que afetam diretamente o comportamento da qualificação:

| Campo | Tipo | Padrão | Função |
|---|---|---|---|
| `qualification_required_fields` | JSON (lista) | `null` | Lista de chaves que o agente **obrigatoriamente** deve coletar antes de avançar. Se `null`, o guardrail não exige nenhum campo. Se lista vazia `[]`, avança sempre. |
| `qualification_fields` | JSON (lista de objetos) | `null` | Definição enriquecida dos campos custom (chave + label + hints). Usado para instruir o LLM sobre o que cada campo significa. |
| `qualification_score_threshold` | int | `6` | Score mínimo dos 4Ps (Power + Priority + Price + Timing, escala 0–12) que o lead precisa atingir para avançar. |
| `nurture_vs_discard_rule` | str | `"discard"` | O que fazer com leads que ficam abaixo do threshold — `"discard"` (descarta) ou `"nurture"` (entra em nurturing). |
| `buying_signal_keywords` | JSON | `null` | Palavras-chave que sinalizam intenção de compra (influenciam roteamento da Mãe). |

Os demais campos do AI Profile (tom de voz, niche, offer pack, follow-up, etc.) indiretamente moldam **como** o agente aborda a qualificação, mas não controlam o guardrail de avanço.

---

## 2 — O que o documento `agente-1-sdr-alto-ticket.md` diz é verdade?

**Parcialmente verdadeiro — o documento está desatualizado em relação ao código atual.**

### O que ainda é verdade

- A Mãe roteia para `qualification` enquanto existirem `missing_fields`.
- A Filha faz **1 pergunta por turno** (`current_field`).
- O histórico `asked_questions_json` impede repetição: máx. 3 perguntas por campo, 20 no total.
- A Filha nunca agenda reunião dentro da rota de qualificação (salvo pedido explícito do lead).
- `qualification_score_threshold` (padrão `6/12`) controla se o score 4P é suficiente para avançar.

### O que mudou / não é mais hardcoded

O documento cita campos fixos por modo:

```
agenda:    service_interest | availability_window | location_preference | price_acceptance
consultivo: + urgency | decision_role | constraints | budget_or_price_acceptance
```

**Mas o código atual (`qualification_guardrails.py`) não tem esses defaults hardcoded:**

```python
def required_fields_for_mode(agent_mode_normalized, required_fields_override=None):
    if required_fields_override is not None:
        return list(required_fields_override)
    return []   # ← sem config no AI Profile = nenhum campo obrigatório
```

Ou seja: **sem `qualification_required_fields` configurado, o agente nunca bloqueia o avanço por campos faltando** — apenas o score dos 4Ps conta (threshold 6/12).

### O que o usuário pode configurar além dos campos fixos

| Variável configurável | Campo AI Profile | Comportamento |
|---|---|---|
| Lista de campos obrigatórios | `qualification_required_fields` | Substitui completamente qualquer default. Lista vazia = sem qualificação obrigatória. |
| Definição semântica dos campos | `qualification_fields` | Informa o LLM o que cada campo representa (permite nomes 100% custom). |
| Score mínimo para avançar | `qualification_score_threshold` | De 0 a 12. Se quiser ignorar score, colocar 0. |
| Regra para leads fracos | `nurture_vs_discard_rule` | `"discard"` ou `"nurture"`. |

### Os 4 scores (4Ps) — são fixos

O cálculo dos 4Ps em `qualification_state.py` é hardcoded para ler **exatamente estas chaves**:

| Score | Chave lida | O que detecta |
|---|---|---|
| Power | `decision_role` | Se o lead é o decisor |
| Priority | `urgency` | Se há urgência |
| Price | `budget_or_price_acceptance` | Se aceita o preço |
| Timing | `availability_window` | Se tem disponibilidade definida |

Se o usuário configurar campos 100% custom sem nenhuma dessas 4 chaves, o score sempre será 0 — e o guardrail detecta isso e **libera o avanço automaticamente** para não bloquear indefinidamente (ver lógica `_4P_KEYS` no guardrail).

---

## 3 — Base de conhecimento vs. `required_fields` / `missing_fields`

São conceitos **completamente separados e com funções distintas**.

### Base de conhecimento (`/api/knowledge`)

- É um repositório de **informações sobre o negócio do usuário**: documentos, FAQs, arquivos de mídia, links.
- O conteúdo é injetado no contexto do LLM como "o que o agente sabe sobre a empresa/produto".
- Exemplos típicos: política de preços, diferenciais, casos de sucesso, scripts de objeções, cardápio.
- Está organizada por fases do pipeline (`qualification`, `presentation`, `closing`) — mas isso só indica **em qual fase aquele item deve ser fornecido ao LLM**, não tem relação com o guardrail de campos.

### `required_fields` / `missing_fields`

- São variáveis de **controle de fluxo estruturado** — dizem ao sistema quais dados do lead precisam ser coletados.
- `missing_fields` é calculado dinamicamente comparando `qualification_required_fields` com o `data_json` já preenchido do lead.
- Não é texto livre — é uma lista de chaves (`["urgency", "budget_or_price_acceptance"]`).

### O que cada um impacta na prática

| Aspecto | Base de conhecimento | required_fields / missing_fields |
|---|---|---|
| Formato | Texto livre, arquivos, links | Lista de chaves estruturadas |
| Onde atua | Prompt do LLM (contexto semântico) | Guardrail (bloqueio lógico de avanço) |
| Quem lê | LLM (Filha) para formular respostas | Orquestrador (Mãe) para decidir rota |
| Efeito ausente | Agente responde sem contexto completo | Nenhum campo obrigatório, avança sempre |
| Configurado por | Usuário via UI de knowledge | Usuário via campo `qualification_required_fields` no AI Profile |

---

## 4 — É possível configurar um fluxo estilo mapa mental na qualificação?

**Não atualmente.** O sistema funciona assim:

- `qualification_required_fields` é uma **lista plana** de campos obrigatórios, sem ordem definida ou ramificações.
- A Filha escolhe qual campo perguntar a cada turno com base no `current_field` sugerido pela Mãe, que por sua vez vem dos `missing_fields`.
- A ordem e a forma de perguntar são determinadas pelo **LLM em runtime**, não por um fluxo definido pelo usuário.
- Não existe hoje um mecanismo de condicionais ("se respondeu X, pergunte Y; senão, pergunte Z").

### O que existe de controle

| Controle disponível | Como funciona |
|---|---|
| Quais campos coletar | `qualification_required_fields` — lista plana |
| O que cada campo significa | `qualification_fields` — descrição semântica para o LLM |
| Quantas tentativas por campo | Hardcoded: máx. 3 por campo, 20 no total (`asked_questions_json`) |
| Score mínimo para avançar | `qualification_score_threshold` |
| Instruções de comportamento | `custom_instructions` no AI Profile (texto livre) |

### Como o usuário pode influenciar o "fluxo" hoje

Indiretamente, via `custom_instructions` no AI Profile é possível instruir o LLM a seguir uma ordem preferencial ou aplicar condicional simples ("pergunte sobre urgência antes de preço"). Mas isso é uma sugestão ao LLM, não uma garantia de fluxo determinístico.

Um fluxo de mapa mental verdadeiro (com condicionais explícitas, ramificações, estados intermediários) seria uma funcionalidade a construir — não existe no sistema atual.

---

## 5 — Risco de conflito entre base de conhecimento de qualificação e `required_fields`

**Existe risco, mas é controlável.**

### Onde o conflito pode ocorrer

O risco se materializa quando o usuário coloca na base de conhecimento da fase `qualification` **instruções que contradigam ou se sobreponham** à lógica de campos obrigatórios. Exemplos problemáticos:

- Knowledge item diz "pergunte apenas nome e interesse" → mas `required_fields` exige 5 campos → LLM pode achar que já terminou a qualificação e tentar avançar, enquanto o guardrail bloqueia.
- Knowledge item lista campos em ordem diferente do `qualification_fields` → LLM pode se confundir sobre o que ainda falta.
- Knowledge item descreve o campo `urgency` de forma diferente da definição em `qualification_fields` → inconsistência semântica.

### Por que o impacto não é garantido

- A Mãe (orquestrador) usa os `missing_fields` do guardrail — isso é **lógico, não LLM**. O guardrail não lê a knowledge base.
- A Filha recebe tanto a knowledge base quanto os `missing_fields` → ela pode priorizar um sobre o outro dependendo do prompt.
- O prompt da Filha instrui a sempre focar no `current_field` sugerido — isso mitiga parte do risco.

### Recomendação prática

| Situação | Risco | Recomendação |
|---|---|---|
| Knowledge base fala de produto/serviço na fase de qualificação | Baixo | Normal e esperado — não conflita |
| Knowledge base contém scripts de qualificação com campos distintos dos `required_fields` | Alto | Alinhar os campos ou mover para `custom_instructions` |
| Knowledge base vazia + `required_fields` configurado | Nulo | Funciona bem |
| Knowledge base e `required_fields` completamente alinhados | Nulo | Configuração ideal |

Confirmar o impacto real em um caso específico **requer teste** — a interação entre conhecimento injetado e fluxo estruturado depende muito do prompt da Filha, que varia por playbook.

## 6 sobre os campos f1, f2 e f3 no ai-profile

Esses campos são salvos em qualification_fields — não têm nada a ver com custom_instructions.

Como funciona o ciclo completo
No modal "Adicionar campo", cada item que você cria gera um objeto assim:


{
  "key": "nome_do_pet",
  "label": "Nome do pet",
  "question": "Qual é o nome do seu pet?",
  "passive_hint": "Capturar se lead mencionar",
  "mode": "required",   // ou "optional" ou "off"
  "group": "f1"         // f1, f2 ou f3
}
Esse objeto vai para qualification_fields (JSON no banco).

O backend deriva automaticamente qualification_required_fields filtrando só os itens com mode = "required". Você nunca precisa preencher qualification_required_fields manualmente — ele é uma consequência do que você marca como "Obrigatório" no modal.

O orquestrador, na hora de montar o contexto para o LLM, lê qualification_fields e separa:

must_collect_with_questions — campos com mode = "required" (LLM vai perguntar ativamente)
nice_to_collect — campos com mode = "optional" (LLM captura se surgir na conversa)
Resumo dos três conceitos
Campo	O que é	Quem preenche
qualification_fields	Definição rica de cada campo (nome, pergunta, hint, grupo, importância)	Você, via modal F1/F2/F3
qualification_required_fields	Lista de chaves obrigatórias — derivada automaticamente	Backend (nunca você)
custom_instructions	Instruções gerais de comportamento do agente (tom, regras, exceções)	Campo separado no AI Profile
Os filtros F1 (Perfil e Fit), F2 (Intenção e Dor), F3 (4Ps) são apenas agrupamento visual para organizar os campos no painel — no backend tudo vai junto em qualification_fields com o atributo group indicando a qual filtro pertence.