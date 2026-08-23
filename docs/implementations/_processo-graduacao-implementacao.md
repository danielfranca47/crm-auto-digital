# Processo de Graduação: Implementação → Arquitectura

Quando um arquivo de `docs/implementations/` está **completo e validado**, o seu
conteúdo deve ser "graduado" para os docs de arquitectura em `docs/architecture/`.

Este processo garante que os docs de arquitectura ficam sempre sincronizados com
o código real, e que os arquivos de implementação (que são documentos de trabalho
temporários) são limpos quando já não são necessários.

---

## Quando executar este processo

Executar este processo quando **todas** estas condições forem verdadeiras:

1. O arquivo de implementação tem `**Status:** Todos os cenários validados`
2. Todos os checks obrigatórios estão marcados `[x]` (checks opcionais/edge-cases
   podem estar pulados com `[⏭️]` — isso é aceitável)
3. Não há fases adicionais abertas ou pendentes

Se algum check ainda estiver `[ ]`, o arquivo **não está pronto para graduação**.

---

## Passo 1 — Identificar que áreas foram afectadas

Ler o arquivo de implementação e listar as áreas do sistema que foram alteradas.
Usar [`_mapa-sistema.md`](../architecture/_mapa-sistema.md) como referência para
identificar a quais componentes e responsabilidades cada mudança pertence.

Exemplos de mapeamento:

| A implementação afectou... | Área no mapa |
|---|---|
| `routes/webhooks.py`, `inbound_handler.py` | Pipeline inbound WhatsApp |
| `decision_engine.py`, `orchestrator_models.py` | Motor de decisão LLM |
| `CamadaFluxoVenda.tsx`, blocos de Camada 7 | Fluxo de Venda (frontend + backend) |
| `ai_profiles` (novos campos) | AI Profile / Agentes |
| `followup_reconciler.py` | Follow-up |
| `routes/playground.py`, `Playground.tsx` | Paridade Playground ↔ WhatsApp |
| Painel admin (`AdminAgents.tsx`, endpoints `/admin/*`) | Contrato AdminAgents |

---

## Passo 2 — Ler os docs de arquitectura relevantes

Ler o [`_overview.md`](../architecture/_overview.md) para identificar quais documentos
cobrem as áreas identificadas no Passo 1.

Ler cada doc relevante **na íntegra** antes de fazer qualquer alteração.
O objectivo é perceber o que já está documentado e o que está em falta.

---

## Passo 3 — Decidir: actualizar existente ou criar novo

### Actualizar um doc existente quando:
- A implementação altera ou estende uma área já coberta
- A mudança é uma nova funcionalidade dentro de um domínio existente
  (ex.: novo campo no AI Profile → `agents.md`)

**Como actualizar:**
- Reescrever apenas as secções afectadas — não acrescentar parágrafos de "antes era X, agora é Y"
- Sem histórico de implementação no texto — isso pertence ao arquivo de impl. (que vai ser deletado)
- O resultado deve ser um espelho do código actual, enxuto e confiável

### Criar um novo doc quando:
- A implementação introduz uma área de responsabilidade sem doc existente
- A feature é grande o suficiente para não caber como secção num doc existente
  (regra prática: >3 conceitos distintos ou >5 arquivos de código envolvidos)

**Formato do novo doc:** `docs/architecture/<slug>.md`
**Actualizar** `_overview.md` com uma linha na tabela de documentos existentes.
**Actualizar** `_mapa-sistema.md` se a mudança acrescenta um novo serviço ou
componente de infra que ainda não está mapeado.

---

## Passo 4 — Fazer as actualizações

Editar (ou criar) os docs de arquitectura identificados.

**Checklist antes de fechar:**
- [ ] Todos os novos campos/comportamentos estão reflectidos no(s) doc(s) relevante(s)?
- [ ] `_mapa-sistema.md` precisa de novos arquivos críticos ou tabelas?
- [ ] `_overview.md` precisa de nova linha na tabela?
- [ ] Algum doc ficou desactualizado por esta implementação (algo que era verdade
      deixou de ser)?

---

## Passo 4b — Versionamento (só para features com versão explícita, ex.: agent-local)

Algumas features usam numeração de versão própria (ex.: "agent-local v2"),
independente do resto do sistema. Quando a implementação graduada pertence a
uma dessas features:

- O doc de arquitectura resultante (Passo 3/4) leva uma nota no topo:
  `**Versão documentada: vN.**` — vN é a versão que acabou de ser graduada.
  O doc é sempre um espelho da versão mais recente já graduada — nunca
  acumular texto tipo "na vN-1 era assim, agora é assim" no corpo.
- Qualquer item que sobrar para `docs/plans/` ou `docs/implementations/`
  (Passo 5b, ou um novo pedido do utilizador para essa mesma feature) leva
  `**Versão-alvo: vN+1.**` no topo, com link para o doc de arquitectura vN.
- Quando essa vN+1 for implementada e graduada por sua vez, o doc de
  arquitectura passa a dizer `vN+1` e o ciclo repete-se (`vN+2` nos plans).

Isto evita perder o histórico de "que versão faz o quê" quando arquitectura
(sempre a versão actual) e plans/implementations (sempre a próxima versão)
convivem no repo ao mesmo tempo.

**Empacotamento é sempre a última fase de uma versão.** Se a feature
distribui um binário/pacote (ex.: agent-local → `.exe` via PyInstaller), o
M-item de empacotamento vN nasce junto com a triagem do Passo 5b como o
**último item** do arquivo `docs/plans/<feature>-melhorias-futuras-V(N+1).md`
— e, assim que o arquivo de implementação de vN atingir
`Todos os cenários validados`, esse M-item específico já pode ser promovido
para `docs/implementations/<feature>-vN-empacotamento-<pacote>.md` (Status:
Aguardando Plan Mode) de imediato, sem esperar o resto do planeamento de
v(N+1). Ver [`docs/plans/_versionamento-agent-local.md`](../plans/_versionamento-agent-local.md)
para o exemplo aplicado ao agent-local.

---

## Passo 5 — Criar o template preenchido (se não existir)

Se `docs/implementations/_template-implementacao.md` não existir ou estiver
desactualizado em relação à estrutura do arquivo que está sendo graduado,
actualizá-lo para reflectir um exemplo realista do padrão actual.


---

## Passo 5b — Triagem de "Ajustes Possíveis" / "Fora do Escopo"

Antes de deletar o arquivo, verificar se ele tem uma secção final de sugestões
não implementadas (títulos usados no repo: `## Ajustes Possíveis Pós-Implementação`,
`## Fora do Escopo — Futuro`, ou equivalente). Se a secção não existir ou estiver
vazia, saltar este passo e ir directo ao Passo 6.

**Por quê:** esta secção acumula boas sugestões (correções, débito técnico,
melhorias) que historicamente eram perdidas ao deletar o arquivo na graduação,
sem nenhuma decisão explícita sobre o que fazer com elas. Este passo obrigatório
garante que nada é descartado silenciosamente.

### 1. Extrair e listar os itens

Ler a secção e listar cada sugestão como um item numerado (um item por
parágrafo/bullet; agrupar bullets que descrevem a mesma sugestão).

### 2. Perguntar ao utilizador quais são válidos

Mostrar a lista numerada e perguntar quais itens ainda fazem sentido implementar.
Aceitar resposta "todos", "nenhum" ou uma lista específica (ex.: "1 e 3").

Itens descartados ficam simplesmente de fora — não precisam de registo em lado
nenhum.

### 3. Para cada item validado, perguntar a prioridade

Perguntar, item a item (ou em bloco, se o utilizador preferir responder assim):

> "Este item é urgente (implementar já a seguir) ou não-urgente (fica no
> backlog para um sprint futuro)?"

- **Urgente** → vai para `docs/implementations/` (passo 4 abaixo)
- **Não-urgente** → vai para `docs/plans/` (passo 5 abaixo) — perguntar também
  a prioridade declarada ALTA/MÉDIA/BAIXA, usada depois pela análise de sprint
  (ver [`_guia-analise-planos.md`](../plans/_guia-analise-planos.md))

### 4. Item urgente → criar arquivo em docs/implementations/

Criar um novo arquivo seguindo [`_guia-documentar-implementacao.md`](_guia-documentar-implementacao.md),
preenchendo o que já se sabe a partir do item original (motivação, contexto,
arquivos prováveis).

**Isto não substitui o Plan Mode obrigatório.** O novo arquivo nasce com
`**Status:** Aguardando Plan Mode` — a implementação real só começa depois do
diagnóstico normal (Passo 0 do guia) ser feito e aprovado pelo utilizador.

Referenciar a origem no campo Motivação: "Este item surgiu como 'Ajuste possível'
na graduação de `<arquivo-graduado>.md`."

### 5. Item não-urgente → registar em docs/plans/

Seguir a convenção de [`docs/plans/README.md`](../plans/README.md):
- Se já existir um arquivo `<tema>-melhorias-futuras.md` para a mesma feature
  (ou uma relacionada), **acrescentar** o item lá como novo `M<n>` com a
  prioridade ALTA/MÉDIA/BAIXA definida no passo 3.
- Caso contrário, criar `docs/plans/<slug-da-feature>-melhorias-futuras.md`
  novo, com o contexto "Itens deixados de fora da implementação
  `<arquivo-graduado>.md`" e cada item como `M<n>`.

### 6. Confirmar antes de prosseguir

Mostrar ao utilizador um resumo do que foi decidido (item → destino) antes de
seguir para o Passo 6. Os itens migrados já não precisam de estar na secção
"Ajustes Possíveis" do arquivo original — ele vai ser deletado no passo seguinte.

---

## Passo 6 — Deletar o arquivo de implementação

Após confirmar que toda a informação arquitecturalmente relevante está nos docs
de arquitectura, remover o arquivo de implementação:

```bash
git rm docs/implementations/<nome-do-arquivo>.md
```

**O que NÃO precisa de migrar:**
- Histórico de fases e diagnósticos — pertence ao git log / PR
- Trechos de código antes/depois — visível no git diff
- Notas de testes com datas específicas — ficam nos commits
- "Ajustes Possíveis Pós-Implementação" / "Fora do Escopo" — já tratados no
  Passo 5b (triados e migrados para `docs/implementations/` ou `docs/plans/`
  antes de chegar aqui)

**O que SIM precisa de migrar:**
- Comportamentos e regras de runtime não-óbvios
- Novos campos de schema (DB, API, AI Profile)
- Novos fluxos de dados ou integrações
- Flags, variáveis de ambiente e invariantes

---

## Passo 6b — Fechar sprint plan (se aplicável)

Se o arquivo de implementação graduado tinha o campo `**Sprint:**` preenchido:

1. Abrir o arquivo de sprint plan indicado em `docs/plans/`
2. Na seção **"Tracking de absorção"**, actualizar a linha deste item:
   - Preencher "Arquivo de implementação" com o nome do arquivo graduado
   - Mudar status de ⏳ para ✅
   - Registar o hash do commit de graduação na coluna "Commit"
3. Verificar se **todos os itens** do tracking estão ✅

**Se ainda houver itens ⏳ Pendente:**
- Salvar as alterações ao sprint plan e incluir no commit de graduação (Passo 7)

**Se todos os itens estiverem ✅** → executar limpeza completa:
4. Ler a seção "Manutenção" do sprint plan — ela lista exatamente quais `docs/plans/*`
   deletar e sob que condição. Para cada arquivo com condição satisfeita:
   ```bash
   git rm docs/plans/<arquivo-de-plans>.md
   ```
   **Regra obrigatória:** nunca deletar arquivos prefixados com `_` em `docs/plans/`
   (ex.: `_guia-analise-planos.md`, `_template-plano-semanal.md`). Esses são guias
   permanentes do processo analítico — só os arquivos de planos concretos são deletados.
5. Deletar o próprio arquivo de sprint plan:
   ```bash
   git rm docs/plans/plano-sprint-YYYY-MM-DD.md
   ```
6. Incluir tudo no commit de graduação (Passo 7)

---

## Passo 7 — Commit único

Fazer um único commit com todas as alterações: docs actualizados, docs criados,
arquivo(s) de implementação removido(s), e limpeza de sprint/plans se aplicável.

Mensagem sugerida:
```
docs: graduar <nome-da-feature> → actualizar architecture

- <arquivo>.md: <o que foi actualizado>
- <outro>.md: criado (nova área: <descrição>)
- Removido: docs/implementations/<arquivo>.md (todos os testes validados)
- Removido: docs/plans/<arquivo>.md (sprint absorvido)  ← se aplicável
```

---

## Passo 8 — Merge de volta e push

Depois do commit de graduação (Passo 7), fechar a branch da implementação
(ver `CLAUDE.md`, secção "Estratégia de branch por implementação"):

1. Voltar para a branch que originou esta branch de feature (normalmente
   `main`; se a implementação era aninhada, a branch de feature pai).
2. `git merge` local da branch de feature nela — sem PR.
3. `git push` da branch original.
4. Apagar a branch de feature local (`git branch -d <branch>`) e, se foi
   usada uma `git worktree`, removê-la (`git worktree remove <pasta>`).

Se houver outra implementação sendo graduada ao mesmo tempo, os merges são
sempre sequenciais — nunca simultâneos. Mergear e dar push de uma primeiro;
só depois mergear a outra, resolvendo ali qualquer conflito que surja.

---

## Exemplo completo

### Contexto
Feature "Áudio Inbound + Transcrição" estava completa (`etapa-8-6-audio-transcricao-inbound.md`).

### Passo 1 — Áreas afectadas
- `inbound_handler.py`, `webhooks.py`, `audio_transcription.py` → Pipeline inbound
- `ai_profiles` (novo campo `audio_transcription_enabled`) → AI Profile
- `core_client.py` (novo `send_whatsapp_direct`) → Integrações internas

### Passo 2 — Docs relevantes
- `webhooks.md` (pipeline inbound) — ler
- `agents.md` (AI Profile schema) — ler

### Passo 3 — Decisão
- `webhooks.md` existente: faltava secção de áudio/media → **actualizar**
- `agents.md` existente: faltava campo `audio_transcription_enabled` → **actualizar**
- Nenhum novo domínio introduzido → não criar novo doc

### Passo 4 — Actualizações feitas
- `webhooks.md`: nova secção "Tratamento de Mensagens de Áudio e Mídia"
  com normalização de messageType, pipeline de transcrição, media_fallback
- `agents.md`: campo `audio_transcription_enabled`, campos do `offer_pack`,
  secção "Toggle de Bot por Lead"

### Passo 5b — Triagem
- Arquivo tinha 2 itens em "Ajustes Possíveis": (1) suportar vídeo além de áudio,
  (2) cache de transcrição para áudios repetidos
- Utilizador validou os dois; (1) marcado urgente, (2) não-urgente/MÉDIA
- (1) → novo `docs/implementations/suporte-video-inbound.md` (Aguardando Plan Mode)
- (2) → adicionado como `M1` em `docs/plans/audio-transcricao-melhorias-futuras.md`

### Passo 6 — Deletado
- `docs/implementations/etapa-8-6-audio-transcricao-inbound.md`

### Passo 8 — Merge de volta
- `git merge` de `feat/audio-transcricao-inbound` em `main` + `git push` de `main`
- Branch `feat/audio-transcricao-inbound` apagada localmente

---

## Manutenção deste processo

Se o processo mudar (ex.: nova convenção de naming, novo tipo de doc, novo passo),
actualizar este arquivo para reflectir o padrão actual.
