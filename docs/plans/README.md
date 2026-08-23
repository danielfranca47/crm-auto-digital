# docs/plans — Como usar

Este diretório é a **camada analítica** do processo de desenvolvimento. Aqui ficam os
planos de melhorias futuras e os sprints priorizados antes de entrar no ciclo de
implementação.

---

## Arquivos presentes

| Arquivo | O que é |
|---|---|
| `_guia-analise-planos.md` | Instrução interna para o Claude — como conduzir a análise |
| `_template-plano-semanal.md` | Exemplo preenchido de sprint plan — referência visual |
| `_versionamento-agent-local.md` | Regra do ciclo de versões vN do agent-local (única feature do repo com numeração própria) — empacotamento sempre como última fase de cada versão |
| `plano-sprint-YYYY-MM-DD.md` | Sprint plan gerado após análise (criado sob demanda) |
| `kiwify-checkout-melhorias-*.md` | Melhorias identificadas após a etapa de checkout |
| `pipeline-configurable-fields.md` | Campos configuráveis do AI Profile ainda a implementar |
| `plans-subscriptions.md` | Modelo de planos e assinaturas — decisões pendentes |
| `scale-enterprise-roadmap.md` | Roadmap dos planos Scale e Enterprise |
| `ai-profile-instrucoes-por-fase.md` | Instruções de IA por fase — a implementar |
| `agentes-agenda-melhorias-futuras.md` | Multi-profissional por conta, closing seletivo, confiabilidade da confirmação de agendamento, error boundary, guards redundantes e badge de fuso |
| `cancelamento-reagendamento-melhorias-futuras.md` | Itens deixados de fora do M1 de cancelamento/reagendamento já graduado: handoff humano na janela pós-confirmação, janela de 30 dias, gap de autenticação, bug de status duplicado em follow-up |
| `followup-auto-trigger-melhorias-futuras.md` | Itens deixados de fora do M2 (disparo automático/check-in de inatividade): falso-positivo de actividade, bug de trava do banco em `progress_followup_after_auto_send`, Agent 2 fora do check-in, worker sem isolamento de conta em testes locais |
| `agent-local-melhorias-futuras-V3.md` | Itens deixados de fora da graduação da v2 do agent-local (M1–M9) + M10 "Empacotamento v3", sempre a última fase — ver `_versionamento-agent-local.md` |
| `seguranca-melhorias-futuras.md` | Achados Altos/Médios/Baixos da auditoria de segurança de 2026-07-15 ainda não corrigidos (os 2 críticos já foram corrigidos e graduados) |
| `central-ajuda-usuario.md` | Central de Ajuda educativa para usuários (estilo Meta Ads Help) — nasce do gap de descoberta de `custom_instructions`/Fluxo de Venda como redes de segurança configuráveis |
| `email-cold-outreach-melhorias-futuras.md` | Itens deixados de fora da v1 do email cold outreach graduado: suporte Outlook/Microsoft 365 (OAuth), múltiplas contas SMTP por utilizador |
| `persistencia-dados-melhorias-futuras.md` | Item deixado de fora da correcção de persistência do backend-crm: aplicar a mesma checagem de arranque (recusar subir sem env var de persistência) ao backend-core |
| `qualificacao-score-generalizado-melhorias-futuras.md` | Fases 3-4 adiadas de `qualificacao-flexivel-score-generalizado.md` (score generalizado para campos custom, presets não-obrigatórios com risco a redesenhar) + didática/transparência de score na UI + gate de score pular checagem com reunião real confirmada |
| `qualificacao-race-condition-melhorias-futuras.md` | Item deixado de fora do fix de race condition em `upsert_qualification_state()` já graduado: TOCTOU similar em `increment_attempt()` |
| `fluxo-vendas-melhorias-futuras.md` | Itens deixados de fora da graduação do fix de fluxo de vendas sequencial: migrar instrução de agendamento para `consultivo`, detalhar marcos do Fluxo de Venda no modal do lead |
| `confiabilidade-integracoes-externas-melhorias-futuras.md` | Itens deixados de fora da graduação do fix de SMTP+webhook Efí do primeiro assinante: auditoria de falhas silenciosas em dependências externas, auditoria de efeitos de reentrega em todos os webhooks |
| `reembolso-melhorias-futuras.md` | Itens deixados de fora da graduação do botão de reembolso admin MVP: agente automático de reembolso dos 7 dias via email, inconsistência "7 dias" vs "30 dias" na copy da landing |

Os arquivos sem prefixo `_` são os **planos concretos** — contêm melhorias identificadas
que ainda não foram implementadas.

---

## Como criar um novo arquivo de planos

Quando identificares melhorias futuras (ao fim de uma implementação, numa sessão de
análise, ou ao notar um gap no produto), cria um arquivo neste diretório.

> Se o item veio da secção "Ajustes Possíveis" / "Fora do Escopo" de um arquivo
> sendo graduado, este arquivo é criado como parte do **Passo 5b** de
> [`_processo-graduacao-implementacao.md`](../implementations/_processo-graduacao-implementacao.md) —
> só depois de o utilizador confirmar que o item é válido e não-urgente.

**Formato do nome:** `<tema-descritivo>.md`

**Estrutura mínima:**

```markdown
# Título do tema

> Contexto: de onde veio este documento (ex.: pós-graduação da etapa X).

## M1 — Nome da melhoria

**Prioridade: ALTA / MÉDIA / BAIXA**

[Descrição do problema e do que precisa mudar. Citar arquivos/comportamentos
relevantes se já souber.]
```

Não há formato obrigatório rígido — o importante é que cada item seja identificável
(M1, M2... ou por título) e tenha prioridade declarada.

---

## Como disparar uma análise de sprint

Quando quiseres priorizar o que implementar a seguir, diz ao Claude Code:

> **"Analisa os plans e monta o sprint"**

O Claude vai:
1. Ler todos os arquivos de planos deste diretório
2. Verificar o que já existe (ou não) no sistema actual
3. Mapear dependências entre os itens
4. Fazer perguntas sobre experiência desejada, produto ou estratégia quando precisar
   da tua decisão
5. Propor 2–3 itens priorizados (P1/P2/P3) com justificativa
6. **Aguardar a tua aprovação** antes de gerar o arquivo de sprint

Após a tua aprovação, é criado `docs/plans/plano-sprint-YYYY-MM-DD.md`.

---

## O que contém um sprint plan

Cada sprint plan tem:
- **Diagnóstico** — tabela com todos os itens auditados e o estado no sistema
- **Perguntas respondidas** — decisões de produto/estratégia confirmadas por ti
- **P1 / P2 / P3** — os itens do sprint, cada um com contexto e prompt pronto
- **Tracking de absorção** — tabela de progresso, preenchida pelo Claude de implementations
- **Manutenção** — quais arquivos de planos deletar quando o sprint estiver completo

---

## Como iniciar uma implementação do sprint

Cada item P1/P2/P3 do sprint plan tem um **prompt pronto**. Para iniciar:

1. Abrir o arquivo `plano-sprint-YYYY-MM-DD.md`
2. Copiar o prompt do item que queres implementar
3. Colar no Claude Code

O Claude de implementations vai ao Plan Mode, investiga o código e segue o processo
normal de `docs/implementations/`.

---

## O que acontece com os arquivos após as implementações

O operacional (Claude de implementations) trata da limpeza automaticamente:

- A cada graduação de implementação, marca o item como ✅ no tracking do sprint plan
- Quando todos os itens do sprint estiverem ✅, deleta os arquivos de planos que
  ficaram vazios + o próprio sprint plan

**Não precisas de fazer nada manualmente** — o ciclo fecha sozinho ao graduar a última
implementação do sprint.

Os únicos arquivos que **nunca são deletados** são os prefixados com `_`
(`_guia-analise-planos.md`, `_template-plano-semanal.md`).
