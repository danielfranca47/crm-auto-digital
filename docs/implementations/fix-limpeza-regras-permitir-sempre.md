# Limpar as regras antigas de "permitir sempre" do Claude Code

**Branch:** `worktree-fix+limpeza-regras-permitir-sempre`
**Status:** Todos os cenários validados
**Origem:** este item surgiu como "Ajuste possível" na graduação de `feat-modo-auto-sem-cliques.md` (04/10/2026), marcado como urgente pelo utilizador

---

## Motivação

Antes do modo auto, cada clique em "permitir sempre" acrescentava uma regra
`allow` às definições do Claude Code. Ficaram acumuladas 232 regras nas
definições pessoais (`~/.claude/settings.json`) e 83 nas do projeto
(`.claude/settings.json`). Com o modo auto ativo, a maioria é redundante — o
revisor automático já aprova esse trabalho sem clique — mas continuam a ter
efeito: um comando que casa com uma regra `allow` corre **sem passar pelo
revisor**.

Comportamento desejado: listas `allow` curtas, só com o que foi decidido
manter; nenhuma credencial dentro de uma regra.

**Decisões do utilizador (04/10/2026):**

- **Critério de corte: núcleo + testes automáticos.** Ficam as ferramentas de
  browser que olham ou clicam na página já aberta e a execução de testes
  (pytest, unittest, tsc). Tudo o resto sai.
- **Credenciais: só remover**, sem trocar chaves — o ficheiro pessoal nunca saiu
  desta máquina e os mesmos valores já estão nos `.env` no mesmo disco.

---

## Problemas Identificados (estado anterior)

1. **18 regras pessoais com credencial em texto simples** (o levantamento
   inicial contava 12). 4 tokens de sessão já expirados (o último venceu a
   09/09/2026); 10 com senhas de 6 contas de teste locais; **4 vivas** — duas
   com a chave de serviço (igual a `CORE_SERVICE_TOKEN` dos `.env` locais) e
   duas com o segredo de admin (igual a `ADMIN_SECRET` de `backend-core/.env`).
   Nenhuma credencial no ficheiro do projeto.
2. **Regras pessoais que saltavam o revisor:** `git add:*`, `git commit *`,
   `git push *`, `git checkout *`, `npm install *`, `npm run *`,
   `npx prisma *`, Python a ler código da entrada (`python -`),
   `Read(//c//**)` (disco inteiro), `evaluate_script` (código dentro da página)
   e `railway logs *`. As de `git` são as mais graves: é o revisor que impede um
   segredo de entrar num commit deste repositório público.
3. **Regras do projeto largas demais:** `curl -s http://localhost:*` e
   variantes (o coringa aceita um segundo endereço externo a seguir ao
   primeiro), `git stash *`, `git rm *`, e duas que imprimiam linhas de `.env`.
4. **Lixo de uso único nas duas listas:** PIDs antigos, caminhos de outro
   projeto, comandos exatos que nunca se repetem.

Descartado no diagnóstico:

- **Núcleo de regras de leitura** (skill `fewer-permission-prompts`): em modo
  auto os comandos só de leitura já correm sem revisor e sem clique, por isso
  essas regras não acrescentam nada.
- **`autoMode.classifyAllShell: true`:** suspende todas as regras de comando
  enquanto o modo auto está ativo — anularia as regras de teste que o
  utilizador escolheu manter.

---

## Abordagem

```
.claude/settings.json (projeto, versionado)      → o Claude edita
  allow: 83 → 56
    ├─ 16 de testes (pytest / unittest / tsc, Bash e PowerShell)
    ├─ 36 de browser na página já aberta (18 por servidor chrome-devtools)
    └─  4 de desktop, só olhar
  deny (32) e ask (12): intactos

~/.claude/settings.json (pessoal, na máquina)    → o utilizador aplica
  python C:\Temp\limpar-regras-claude.py
    ├─ allow: 232 → 0
    ├─ cópia de segurança sem as regras com credencial
    └─ resto das definições intacto
```

Quem aplica a parte pessoal é o utilizador porque o revisor automático recusa
que o Claude altere as próprias regras de permissão (motivo
`[Self-Modification]`). O script fica fora do repositório (`C:\Temp\`): é de uso
único e mexe num ficheiro que não é versionado.

---

## Plano de Implementação

### Fase 1 — Limpeza das duas listas + documentação

**Objetivo:** projeto fica com o núcleo decidido, pessoal fica vazio e sem
credenciais, e a política fica escrita em `docs/ops`.

| Arquivo | O que muda |
|---|---|
| `.claude/settings.json` | `allow` reduzida de 83 para 56 regras (testes, browser na página aberta, desktop só olhar); `deny` e `ask` sem alteração |
| `docs/ops/local-dev.md` | Secção "Modo auto e regras de permissão do Claude Code": política da lista `allow` (o que fica, o que nunca entra), lista pessoal vazia, `classifyAllShell` desligado |
| `C:\Temp\limpar-regras-claude.py` (fora do repositório) | Script de uso único para o utilizador correr sobre `~/.claude/settings.json` |

Ficam de fora da lista `allow` do projeto, a passar pelo revisor:
`navigate_page`, `new_page`, `evaluate_script`, `upload_file`, clique e teclado
ao nível do desktop, e todo comando que não seja teste.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f2a58a2` | Lista `allow` do projeto reduzida ao núcleo + política documentada |

**Detalhes do commit `f2a58a2`:**
- `.claude/settings.json` — `allow` reescrita com as 56 regras do núcleo; `deny` e `ask` iguais
- `docs/ops/local-dev.md` — ponto `allow` reescrito como política; dois pontos novos em "Na máquina" (lista pessoal vazia, `classifyAllShell` desligado)
- `docs/implementations/fix-limpeza-regras-permitir-sempre.md` — template preenchido

### Relatório da Fase 1 — o que mudou na prática

**Antes:** havia 315 "permitir sempre" acumulados. Uma parte deixava o Claude
gravar e enviar alterações para o repositório público, instalar pacotes e ler o
disco inteiro sem que o revisor automático visse; 18 guardavam senhas e chaves
escritas por extenso.

**Agora:** no projeto ficam 56 permissões, só para correr testes automáticos e
para olhar e clicar na página de teste já aberta no browser. Tudo o resto —
commits, envios, instalações, abrir endereços — passa pelo revisor, sem clique.
As definições pessoais ficam vazias e sem credenciais **depois de o utilizador
correr o script** (`python C:\Temp\limpar-regras-claude.py`).

**Para validar:** Cenários A1 a A4, abaixo.

---

## Checks de Validação

### Cenário A1 — Ficheiro do projeto tem só o núcleo
- [x] Contar as regras de `.claude/settings.json`
- [x] Confirmar: `allow` = 56 (16 testes + 36 browser + 4 desktop), `deny` = 32, `ask` = 12
- [x] Confirmar: nenhuma regra `allow` com `git`, `curl`, `npm`, término de processo, `.env`, `evaluate_script`, `navigate_page`, `new_page`, `upload_file`
- **Validado em:** 04/10/2026 — contagens batem certo, 0 regras proibidas, 0 duplicadas

### Cenário A2 — Ficheiro pessoal vazio e sem credenciais
- [x] Utilizador corre `python C:\Temp\limpar-regras-claude.py`
- [x] Confirmar na saída: 232 regras encontradas, 18 com credencial, 0 depois, "Resto das definicoes intacto: sim"
- [x] Claude repete a verificação mascarada do diagnóstico sobre `~/.claude/settings.json` e sobre a cópia de segurança: total de regras com credencial = 0 nos dois
- [x] Cópia antiga `~/.claude/settings.json.bak-2026-10-04` apagada: guardava 18 regras com credencial
- **Validado em:** 04/10/2026 — `settings.json` com 0 regras e 0 credenciais; cópia de segurança com 214 regras (232 − 18) e 0 credenciais; resto das definições igual entre os dois. A saída do script não foi vista pelo Claude: os números foram reconstituídos a partir dos dois ficheiros. A cópia antiga (03/10/2026, 241 regras, 18 com credencial, desconhecida do script) foi apagada pelo utilizador, porque o revisor automático recusou que o Claude o fizesse; a verificação repetida confirma que já não existe.

### Cenário A3 — Conversa nova trabalha sem cliques
- [x] Abrir uma conversa nova depois de correr o script
- [x] Pedir um fluxo normal: correr os testes de um backend, um `git status`, uma captura de ecrã no browser
- [x] Confirmar: nenhum pedido de clique, nenhum erro de permissão
- **Validado em:** 04/10/2026 — testes do `backend-crm`, `git status` e captura de ecrã da página aberta no browser correram sem nenhuma recusa de permissão. A primeira tentativa de captura falhou por o browser de teste estar em uso por outra conversa (erro "browser is already running", não é erro de permissão); repetida com sucesso depois de essa conversa fechar. O utilizador confirmou que não lhe apareceu nenhum pedido de clique.
- **Limite desta execução:** a conversa correu a partir da pasta principal, que ainda tem a lista antiga do projeto (83 regras); a lista de 56 só entra em `main` na graduação. O que ficou provado é que a lista pessoal vazia não gera cliques. As três operações do fluxo estão cobertas da mesma forma nas duas listas (regra de `pytest`, `git status` só de leitura, `take_screenshot`).
- **Fora do âmbito:** a suíte do `backend-crm` deu 224 aprovados e 18 falhados, corrida sobre o código de `main` — esta implementação não toca em código de backend, por isso as falhas não vêm dela.

### Cenário A4 — Nada sensível entrou no repositório público
- [x] Rever o diff do commit da Fase 1
- [x] Confirmar: nenhum valor de `.env`, senha ou token no que foi commitado
- **Validado em:** 04/10/2026 — as 227 linhas adicionadas foram comparadas com todos os valores dos `.env` locais e com os padrões de credencial: 0 ocorrências

---

## Ajustes Possíveis Pós-Implementação

- **Trocar `CORE_SERVICE_TOKEN` e `ADMIN_SECRET`** — não foi feito por decisão
  consciente. É o passo a dar se o ficheiro de definições pessoais alguma vez
  tiver sido partilhado, sincronizado ou enviado a alguém.
- **Apagar a cópia de segurança** `~/.claude/settings.antes-limpeza-2026-10-04.json`
  quando já não houver dúvida de que nenhuma regra antiga faz falta.
- **Worktrees ativas com cópia antiga do ficheiro do projeto** (88 regras)
  recebem a versão limpa quando incorporarem `main`; conversas já abertas
  continuam com as regras antigas até serem fechadas.
- **As regras de teste podem ser suspensas pelo próprio modo auto**, se ele as
  tratar como intérprete com coringa. Nesse caso os testes passam pelo revisor
  — sem clique e sem prejuízo; não é motivo para as reescrever.
