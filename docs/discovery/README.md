# docs/discovery — Guia para o Developer

## O que é esta pasta

O "centro de inteligência" do produto. Antes de algo ir para `plans/` ou
`implementations/`, e quando ainda há dúvida se vale a pena ou qual a melhor
solução, o tema é investigado aqui: evidência no código, como o mercado resolve,
opções de solução e ligação às metas do produto. Cada investigação termina num
**veredito** que tu decides.

```
Levantamento ──► discovery/ ──► plans/ ──► implementations/ ──► architecture/
 (material bruto)  (vale a pena?)  (fila)     (construção)         (estado atual)
```

Não é obrigatório passar por aqui: um bug confirmado com solução clara vai
direto para `implementations/`.

---

## Ficheiros

| Ficheiro | Para que serve |
|---|---|
| `_guia-discovery.md` | Processo completo para o Claude |
| `_template-investigacao.md` | Estrutura de cada investigação |
| `_metas-produto.md` | As 3–5 metas do produto — âncora das prioridades. **Tu validas** |
| `_radar.md` | Painel: o que está pronto para decidir, em investigação, em stand-by e descartado |
| `levantamentos/` | Material de origem (conversas, relatórios, feedbacks) |
| `<slug>.md` | Uma investigação por tema |

---

## Onde entras tu

Só em dois momentos:

1. **Metas** — validar `_metas-produto.md` quando a estratégia mudar (raro).
2. **Vereditos** — quando o radar tiver investigações "Prontas para decisão",
   decidir em lote: implementations, plans, stand-by ou descartar.

Tudo o resto (investigar, pesquisar mercado, pontuar) é autónomo.

---

## Comandos

| Comando | O que faz |
|---|---|
| `/discovery-levantar <arquivo ou texto>` | Divide um levantamento em investigações (e manda bugs confirmados direto para implementations) |
| `/discovery-aprofundar <slug>` | Investigação completa de um tema → "Pronta para decisão" |
| `/discovery-status` | Painel não-técnico: o que decidir, gatilhos de stand-by, metas por validar |
| `/discovery-decidir` | Aplica os teus vereditos |

Os comandos vivem em `.claude/commands/` (não versionado). Se não aparecerem
num computador novo, ver `docs/ops/local-dev.md`, secção "Comandos slash locais".

---

## Prompts úteis

### Tenho material novo para analisar
```
/discovery-levantar docs/discovery/levantamentos/<arquivo>
```
(ou cola o texto direto depois do comando)

### Quero saber o que está pendente de decisão
```
/discovery-status
```

### Quero investigar a fundo um tema
```
/discovery-aprofundar <slug>
```

### Quero rever as metas
```
Lê docs/discovery/_metas-produto.md e ajuda-me a revê-las — a estratégia mudou: <o que mudou>.
```
