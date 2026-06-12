# docs/architecture — Guia para o Developer

## O que é esta pasta

Documentos que descrevem **como o sistema funciona agora**. São espelhos do código
actual — enxutos, sem histórico de implementação, sem "antes era X".

Servem para o Claude (e para ti) entenderem uma área antes de trabalhar nela.

---

## Ficheiros

### Ficheiros com `_` — meta / índices (ler primeiro)

| Ficheiro | Para que serve |
|---|---|
| `_mapa-sistema.md` | Mapa completo do sistema: todos os serviços, arquivos críticos, fluxo de dados, BD, integrações externas. **Começa aqui se estiveres perdido.** |
| `_overview.md` | Tabela de navegação: qual doc ler por área + quando actualizar vs criar novo doc |

### Ficheiros regulares — documentação por área

| Ficheiro | Área |
|---|---|
| `sales-flow.md` | Camada 7 — Fluxo de Venda (blocos, triggers, fire_once, fases) |
| `llm-architecture.md` | Motor de decisão: LLM Mãe, LLM Filhas, contratos |
| `webhooks.md` | Pipeline inbound WhatsApp (áudio, mídia, buffer, bot_disabled) |
| `pipeline-phases.md` | Qualificação / Apresentação / Fechamento por agent_mode |
| `agents.md` | AI Profile (schema, campos) + Agentes Locais + toggle bot por lead |
| `followup.md` | Arquitectura de follow-up: estados, reconciliador, circuit breaker |
| `playground-parity.md` | Paridade Playground ↔ WhatsApp real (ContextBundle) |
| `admin-agents-contract.md` | Contrato AdminAgents frontend ↔ backend |

---

## Como usar

**Antes de pedir uma feature ou fix:** indica ao Claude para ler o doc relevante.
Sem isso, ele pode não ter o contexto necessário e vai ter que adivinhar.

**Após uma feature estar concluída e testada:** pede ao Claude para actualizar
os docs afectados. O processo está em
`docs/implementations/_processo-graduacao-implementacao.md`.

---

## Prompts úteis

### Quero entender como funciona uma área

```
Lê docs/architecture/_mapa-sistema.md e depois o doc de arquitectura relevante
para [área]. Explica-me como funciona [componente/fluxo].
```

### Quero que o Claude conheça o sistema antes de implementar

```
Antes de começar, lê docs/architecture/_mapa-sistema.md e docs/architecture/[area].md
para teres contexto do que vais alterar.
```

### Após uma feature estar validada e pronta para graduar

```
O arquivo docs/implementations/[nome].md está com todos os checks validados.
Segue o processo em docs/implementations/_processo-graduacao-implementacao.md
para actualizar os docs de arquitectura e remover o arquivo.
```

### Quero saber se algum doc de arquitectura está desactualizado

```
Lê docs/architecture/_mapa-sistema.md e compara com o estado actual do código.
Há algo que precise de ser actualizado?
```

---

## O que esperar do Claude

Quando peders para ler ou actualizar um doc de arquitectura, o Claude vai:
1. Ler o ficheiro na íntegra antes de propor qualquer mudança
2. Reescrever apenas as secções afectadas (não acrescenta histórico)
3. Manter o tom enxuto — se não é necessário saber, não está no doc
4. Actualizar `_mapa-sistema.md` se o trabalho introduzir novo serviço ou componente
5. Actualizar `_overview.md` se for criado um novo doc de área
