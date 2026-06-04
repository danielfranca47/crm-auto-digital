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

## Passo 5 — Criar o template preenchido (se não existir)

Se `docs/implementations/_template-implementacao.md` não existir ou estiver
desactualizado em relação à estrutura do arquivo que está sendo graduado,
actualizá-lo para reflectir um exemplo realista do padrão actual.


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
- "Ajustes Possíveis Pós-Implementação" — viram issues/planos futuros se aplicável

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

### Passo 6 — Deletado
- `docs/implementations/etapa-8-6-audio-transcricao-inbound.md`

---

## Manutenção deste processo

Se o processo mudar (ex.: nova convenção de naming, novo tipo de doc, novo passo),
actualizar este arquivo para reflectir o padrão actual.
