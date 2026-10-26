---
description: Divide um levantamento (conversa, relatório, feedback) em investigações de discovery — bugs confirmados vão direto para implementations. Passo 1 do fluxo de discovery
---

Leia `docs/discovery/_guia-discovery.md` e siga os **Passos 1 e 2** (levantamento →
gaps → triagem) sobre o material indicado a seguir: $ARGUMENTS

Se `$ARGUMENTS` estiver vazio, pergunte ao usuário qual é o levantamento (caminho de
arquivo ou texto colado) e pare.

1. **Guardar o levantamento** em `docs/discovery/levantamentos/AAAA-MM-DD-<tema>.<ext>`
   (data de hoje). Se o material foi colado como texto, salve-o num `.md`. Se é um
   arquivo noutra pasta do repo, mova com `git mv` (ou mova e depois `git add`, se não
   era rastreado). Não edite o conteúdo original.
2. **Verificar cada afirmação no código** antes de a aceitar — cite arquivo:linha.
   Leia também `docs/discovery/_radar.md`: não recrie investigação que já exista, esteja
   em stand-by ou em "Descartados" (a não ser que o levantamento traga facto novo —
   nesse caso diga qual).
3. **Triagem**, conforme a tabela do Passo 2 do guia:
   - Bug confirmado + solução óbvia → `docs/implementations/<slug>.md` com
     `**Status:** Aguardando Plan Mode`, no mesmo formato reduzido que o
     `/statusplans-avancar` usa (Motivação / Área do sistema / Próximo passo), com
     `**Origem:**` apontando para o levantamento.
   - Já existe / não se aplica → sem arquivo; só no resumo ao usuário.
   - Incerteza → `docs/discovery/<slug>.md` a partir de
     `docs/discovery/_template-investigacao.md`, `**Status:** Levantado`, preenchendo
     **só** as secções marcadas com (L). Não aprofunde agora — isso é o
     `/discovery-aprofundar`.
4. **Atualizar `docs/discovery/_radar.md`** (secção "Em investigação / Levantadas").
5. **Commit único** seguindo as regras do `CLAUDE.md` (`docs:` + `git add` nos arquivos
   específicos + corpo listando cada arquivo). Sem push.

**Resumo ao usuário** (linguagem não-técnica): tabela com cada gap → destino
(implementations / investigação / já existe / não se aplica) e porquê numa frase.
Feche sugerindo qual investigação aprofundar primeiro (a de meta mais prioritária em
`_metas-produto.md`) com o comando pronto: `/discovery-aprofundar <slug>`.
