# Modo auto sem cliques de permissão

**Branch:** `worktree-feat+modo-auto-sem-cliques`
**Status:** Todos os cenários validados

---

## Motivação

O utilizador ficava preso ao ecrã a clicar "sim/não" em pedidos de permissão do
Claude Code durante o trabalho. É o primeiro alicerce de um objetivo maior
(decidido em 03/10/2026): um agente que executa sozinho a fila de
`docs/plans/` e `docs/implementations/`. Antes de qualquer automação, o trabalho
do dia-a-dia tem de correr sem cliques — mas com barreiras duras para as poucas
ações que nunca devem acontecer sem o utilizador.

Causa raiz dos cliques: o modo `auto` do Claude Code (um segundo modelo revê
cada ação no lugar do utilizador) existia mas não estava fixado nem configurado,
e a CLI do terminal estava numa versão que arranca sempre em modo manual.

---

## Problemas Identificados (estado anterior)

1. **CLI desatualizada:** `@anthropic-ai/claude-code` na v2.1.81. O arranque em
   modo `auto` no Windows só existe a partir da v2.1.233; nessa versão toda a
   sessão de terminal começava em modo manual.
2. **Modo auto sem configuração:** `~/.claude/settings.json` sem
   `permissions.defaultMode` e sem bloco `autoMode` — o revisor automático não
   sabia que o repositório é público, que push em `main` faz deploy, nem quais
   são os destinos de confiança.
3. **Nenhuma barreira dura:** zero regras `deny` e zero regras `ask` em qualquer
   ficheiro de definições. Nada impedia, por regra, um push forçado ou apagar um
   volume de produção no Railway.
4. **Regras "permitir sempre" perigosas acumuladas clique a clique:**
   `.claude/settings.json` tinha 5 regras de intérprete com código livre
   (`python -c ' *` e variantes); as definições pessoais tinham mais 8 do mesmo
   tipo e `railway run *` (corre qualquer comando com os segredos de produção) —
   precisamente o que o utilizador tinha recusado libertar no passado.

---

## Abordagem

```
Ação do Claude
  ├─ casa com regra deny  → nunca corre (push forçado; apagar/desanexar volume,
  │                         apagar ficheiros de volume, railway down/delete)
  ├─ casa com regra ask   → pergunta sempre (railway variable*, run, ssh, up,
  │                         upload para volume)
  ├─ leitura / edição na pasta de trabalho → corre sem perguntar
  └─ resto → revisor automático decide, com o contexto de autoMode.environment
               ├─ aprova → corre sem clique
               └─ bloqueia → Claude é avisado do motivo e segue por outro caminho
```

Duas camadas, porque nenhuma chega sozinha: as regras `deny`/`ask` só apanham a
forma habitual de escrever um comando; o revisor automático cobre o resto mas
não é uma garantia. `git push` normal fica sem pergunta por decisão do
utilizador — é o último passo do fluxo de graduação.

Abordagem descartada: construir um "agente de permissões" próprio (serviço que
intercepta os pedidos). O modo auto já é esse agente, mantido pelo fornecedor.

---

## Plano de Implementação

### Fase 1 — Configurar e documentar

**Objetivo:** sessões novas arrancam em modo auto, com barreiras duras para ações destrutivas.

| Arquivo | O que muda |
|---|---|
| `.claude/settings.json` | Novas listas `deny` (16 padrões × Bash e PowerShell) e `ask` (6 padrões × Bash e PowerShell); removidas as 5 regras `allow` de intérprete com código livre |
| `docs/ops/local-dev.md` | Nova secção "Modo auto e regras de permissão do Claude Code" — o que está no repo, o que está na máquina, como recriar noutro dispositivo |
| Máquina — CLI (fora do repo) | `@anthropic-ai/claude-code` 2.1.81 → 2.1.288 |
| Máquina — `~/.claude/settings.json` (fora do repo) | `permissions.defaultMode: "auto"`, bloco `autoMode.environment`, remoção de 9 regras `allow` (8 intérpretes livres + `railway run *`) — **aplicado pelo utilizador** |

Diferenças em relação ao plano aprovado:
- Apagar ficheiros **dentro** de um volume (`railway volume files delete`) entrou
  em `deny`, e enviar ficheiros para um volume (`upload`) entrou em `ask`. É nos
  volumes que ficam as bases de dados e, a seguir, os backups.
- O revisor automático recusou que o Claude alterasse `~/.claude/settings.json`
  (motivo `[Self-Modification]`). Risco previsto no plano; não foi contornado —
  essa parte é aplicada pelo utilizador.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `b55950b` | regras deny/ask, limpeza de intérpretes livres, documentação |

**Detalhes do commit `b55950b`:**
- `.claude/settings.json` — listas `deny` (32 regras) e `ask` (12 regras) novas; 5 regras `allow` de intérprete livre removidas
- `docs/ops/local-dev.md` — secção "Modo auto e regras de permissão do Claude Code"
- `docs/implementations/feat-modo-auto-sem-cliques.md` — este arquivo

### Relatório da Fase 1 — o que mudou na prática

**Antes:** nas sessões de terminal, cada comando pedia um clique. Nada impedia,
por regra, um push forçado ou apagar a base de dados de produção. Havia regras
antigas que deixavam correr código arbitrário sem revisão.

**Agora:** a CLI está atualizada e passa a arrancar em modo auto. Ficam
proibidos em qualquer circunstância o push forçado e tudo o que apaga ou desliga
coisas no Railway. Cinco tipos de ação perguntam sempre: mexer em variáveis,
correr comandos em produção, entrar no servidor, publicar à mão e enviar
ficheiros para um volume. As regras antigas de código livre saíram do projeto. Falta um passo teu: aplicar a configuração nas
tuas definições pessoais e escolher "Auto" no VS Code.

**Para validar:** Cenários A1 a A5, abaixo.

---

## Checks de Validação

### Cenário A1 — CLI atualizada
- [x] `claude --version` mostra versão ≥ 2.1.283
- **Validado em:** 04/10/2026 — `2.1.288 (Claude Code)`

### Cenário A2 — Revisor automático com o contexto do projeto
- [x] Utilizador aplica a configuração a `~/.claude/settings.json`
- [x] `claude auto-mode config` mostra as 7 entradas de ambiente escritas (repositório público, deploy em `main`, Railway, domínios, dados sensíveis)
- **Validado em:** 04/10/2026 — utilizador correu o script; `defaultMode: auto`, 232 regras `allow` (9 removidas), cópia de segurança `settings.json.bak-2026-10-04` criada; `claude auto-mode config` lista as 7 entradas

### Cenário A3 — VS Code abre em Auto
- [x] Abrir uma conversa nova no painel do VS Code
- [x] Confirmar: o indicador de modo, por baixo da caixa de texto, diz **Auto**
- **Validado em:** 04/10/2026 — captura de ecrã do utilizador: as 6 conversas abertas, incluindo uma acabada de abrir, mostram "Auto" ao lado do modelo

### Cenário A4 — Trabalho normal sem cliques
- [x] Numa sessão em modo auto: correr `pytest` de um backend, um `curl` a localhost e um clique via chrome-devtools
- [x] Confirmar: zero pedidos de permissão
- **Validado em:** 04/10/2026, conversa do VS Code em modo Auto — `pytest` do
  backend-executors (265 passaram, 73 falharam), arranque do backend-executors
  na porta 8002, `curl http://localhost:8002/health` (HTTP 200) e abrir
  `/docs` + clique em "GET /health" via chrome-devtools. Nenhuma ação foi
  recusada nem ficou à espera do lado do Claude, e o utilizador confirmou que
  não apareceu nenhum pedido no ecrã.
- **Nota sobre as 73 falhas:** não têm relação com esta implementação (a branch
  não toca em código de backend). 16 são falta de `.env` na worktree
  (`CRM_SERVICE_TOKEN não configurado`); as restantes são testes desalinhados
  do código atual (ex.: `DecisionOutput` sem `pre_send_media`,
  `decision_trace`, `suggested_category`). Fica por confirmar se também falham
  em `main` com `.env` presente.

### Cenário A5 — Barreiras duras funcionam
- [x] `git push --force --dry-run` é recusado pela regra `deny`
- [x] `railway variables` gera pedido de confirmação (cancelar)
- **Validado em:** 04/10/2026 — sessão sem ecrã (`claude -p`) lançada dentro
  desta worktree, com um comando de controlo para cada regra:
  - `git push --dry-run` correu; `git push --force --dry-run` foi recusado
    (`Permission to use Bash with command git push --force --dry-run has been denied.`)
  - `railway --version` correu; `railway variables --help` ficou retido à espera
    de autorização (`Claude requested permissions to use Bash, but you haven't granted it yet.`).
    Usou-se `--help` para nenhuma variável de produção aparecer caso a regra
    falhasse — casa com o mesmo padrão `railway variable*`.
- **Nota:** numa sessão sem ecrã o pedido de confirmação não tem quem o responda
  e conta como recusa; numa sessão interativa aparece como pergunta. As regras só
  valem para sessões abertas numa pasta que já as tenha — esta worktree antes do
  merge, qualquer pasta depois do merge em `main` (uma sessão aberta na pasta
  principal antes do merge não recusa o push forçado).

---

## Ajustes Possíveis Pós-Implementação

- As 232 regras `allow` restantes nas definições pessoais (e 83 no projeto) foram
  acumuladas clique a clique; a maioria é inofensiva mas redundante em modo auto.
  Uma limpeza geral ficou fora do escopo. Alternativa de uma linha, se algum dia
  se quiser que o revisor veja todos os comandos de shell independentemente
  dessas regras: `autoMode.classifyAllShell: true` (custo: cada comando espera
  pela decisão do revisor).
- 12 dessas regras pessoais têm o que parece ser uma senha ou token embutido no
  próprio texto da regra (ex.: comandos `curl` de login). Não estão no
  repositório, mas valeria removê-las.
- Sessões sem ecrã (`claude -p`) abertas numa worktree ignoram as regras `allow`
  do projeto com o aviso "this workspace has not been trusted" — as `deny` e
  `ask` continuam a valer e o revisor automático decide o resto. Relevante para
  o agente que vai executar a fila sozinho: ou a pasta é marcada como de
  confiança, ou ele depende só do revisor automático.
- As regras `deny`/`ask` não cobrem formas alternativas de escrever o mesmo
  comando (ex.: opções antes do subcomando). Se isso se revelar um problema, o
  caminho é um hook `PreToolUse` que inspeciona o comando inteiro.
