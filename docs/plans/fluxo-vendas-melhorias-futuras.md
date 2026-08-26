# Fluxo de Venda — melhorias futuras

> Contexto: itens deixados de fora da graduação de `fix-fluxo-vendas-sequencial.md`
> (gating sequencial de gatilhos, guardrail de transição de fase, `is_phase_entry`,
> bloco `booking_signal_opener` editável, funil visual no Kanban). Validados como
> úteis pelo utilizador na triagem pós-graduação (Passo 5b), mas marcados
> não-urgentes.

## M1 — Migrar instrução de agendamento para `consultivo` também

**Prioridade: BAIXA**

Na Fase 4 de `fix-fluxo-vendas-sequencial.md`, a instrução hardcoded "RECONHECIMENTO
DE INTERESSE DE AGENDAMENTO" (`decision_engine.py`, `_build_child_prompt_apresentation`,
variável `_booking_signal_block`) foi migrada para um bloco editável/removível
(`booking_signal_opener`) só para `agent_mode_normalized == "agenda"`.

Para `consultivo`, a instrução continua hardcoded. Diferente do caso do Closer (ver
`fix-instrucao-agendamento-closer.md`, item urgente da mesma triagem), aqui não há
contradição óbvia de propósito — `consultivo` usa `presentation_variant="scheduler"`
por padrão (mesmo formato do `agenda`), então "perguntar dia/horário" não é
tematicamente errado. O problema é mais sutil: o pipeline de `consultivo`
(`SALES_FLOW_PHASES_BY_AGENT_MODE.consultivo = ['p0','p1','p2','p4','p5']`) não tem
fase de pré-agendamento/agendamento, então `recommended_next_category='pre-agendamento'`
não corresponde a nenhum estágio real do funil dele (ainda que seja só informativo,
sem aplicação automática).

**O que fazer:** estender o mesmo padrão de `booking_signal_opener` (banner/card no
builder, leitura condicional no backend) para `agent_mode_normalized == "consultivo"`
— reaproveitando a infraestrutura já criada na Fase 4, só ampliando a condição de
`agent_mode_normalized == "agenda"` para incluir `"consultivo"`.

## M2 — Detalhar marcos do Fluxo de Venda no modal do lead

**Prioridade: BAIXA**

O funil resumido no card do Kanban (Fase 5 de `fix-fluxo-vendas-sequencial.md`,
componente `SalesFlowFunnel` em `LeadCard.tsx`) mostra só a fase atual e as fases
concluídas — não detalha *quais* gatilhos específicos dentro da fase atual já
dispararam (ex.: "já aceitou ver a tabela" vs. "ainda não escolheu o serviço").

Essa informação já existe persistida (`leads.triggers_fired`, JSON array de block
IDs) mas nunca chega à UI além do resumo por fase.

**O que fazer:** no modal completo do lead (`LeadCardDialog.tsx`), adicionar uma
secção que resolva `triggers_fired` contra os blocos `intent_trigger`/`kw_trigger`
configurados na fase atual do `sales_flow` do AI Profile, mostrando o `intent`/label
de cada gatilho já disparado (ex.: lista "✅ Cliente aceitou ver a tabela de preços").
Precisa buscar `ai_profile.sales_flow` no frontend (hoje só usado em
`CamadaFluxoVenda.tsx`) para resolver os labels a partir dos `block_id`.

---

## Espera e Webhook — pesquisa de mercado (26/08/2026)

**Contexto:** os blocos `espera` (Smart Delay) e `webhook`, configuráveis no builder
desde sempre mas sem nenhum efeito real em runtime, foram implementados em
`feat/sales-flow-espera-pausa` e `feat/sales-flow-webhook-execucao` (ver
`docs/architecture/sales-flow.md`, secções "Pausa do Fluxo" e "Execução do bloco
webhook"). Com as duas versões mínimas funcionando (pausa com opção de resposta da
LLM durante a espera; disparo real do webhook com retry/backoff, headers ainda
fixos), o utilizador pediu uma pesquisa de mercado — como ManyChat, HubSpot, Kommo,
n8n, SleekFlow, Twilio Studio e Landbot implementam os mesmos dois recursos — para
identificar lacunas e priorizá-las por esforço × impacto antes de decidir os
próximos passos.

### O que o mercado oferece

| Plataforma | Espera / Delay | Webhook |
|---|---|---|
| **ManyChat** (Smart Delay / External Request) | Duração (min/h/dias) **ou** data específica; janela de horário permitido ("continuar entre 8h–22h"); restrição por dia da semana; cancelamento manual via tag+condição | GET/POST/PUT, **headers customizados**, corpo em JSON, **mapeia a resposta de volta** para campos do contato via JSONPath, caminho de **fallback** se a chamada falhar, botão de **teste** (recurso PRO) |
| **HubSpot** | Delay até data de calendário, até valor de uma propriedade de data, **ou** até ocorrência de um evento | Método, URL, query params, **configuração de autenticação** (appId/tipo) |
| **SleekFlow / Twilio Studio** | Nó "Wait for event/reply": pausa com timeout, mas **ramifica** — responde (palavra-chave/botão) → um caminho; timeout sem resposta → outro | — |
| **n8n** | Pausa que retoma via URL de webhook dedicada — espera por evento externo, não só por tempo | — |
| **Landbot** | — | Chamada REST completa, resposta reutilizável no fluxo, header de Authorization, modo avançado |
| **Kommo** | — | Fire-and-forget no pipeline digital, exige resposta 200 em até 2s |

### Comparando com o que temos

| Recurso | Mercado | Nós temos hoje |
|---|---|---|
| Espera por duração | ✅ quase todos | ✅ (dias/h/min) |
| Espera até data/hora fixa | ✅ ManyChat, HubSpot | ❌ |
| Janela de horário permitido (não retomar de madrugada) | ✅ ManyChat | ❌ |
| Espera com ramificação (responde → um caminho / não responde → outro) | ✅ SleekFlow, Twilio | ❌ — nosso `espera` só despausa e segue o mesmo caminho linear |
| Webhook: headers customizados/autenticação | ✅ quase todos | ❌ — sem esse campo, a maioria das APIs reais simplesmente não aceita a chamada |
| Webhook: corpo customizável (não só texto livre) | ✅ ManyChat, HubSpot | ❌ — hoje é uma `note` de texto solto, não um JSON moldável |
| Webhook: mapear resposta de volta para o fluxo | ✅ ManyChat, Landbot | ❌ — o nosso é fire-and-forget puro |
| Webhook: retry automático em falha | ✅ (varia) | ✅ — já implementado (3 tentativas, backoff) |
| Webhook: botão de teste no builder | ✅ ManyChat | ❌ |
| Webhook: log de execução visível ao usuário | parcial | ❌ — só existe no banco/logs internos |

### Prioridade recomendada (esforço × impacto)

| # | Gap | Esforço | Impacto | Por quê |
|---|---|---|---|---|
| 1 | Headers customizados + autenticação no webhook | Baixo | Alto | Sem isso, praticamente nenhuma API real de mercado aceita a chamada (quase todas exigem `Authorization: Bearer ...` ou API key no header). Gap mais crítico — hoje o recurso funciona tecnicamente mas é inutilizável para a maioria dos casos reais. Reaproveita a arquitetura já construída (`sales_flow_webhook.py`/`sales_flow_webhook_worker.py`). |
| 2 | Corpo do webhook customizável (JSON com variáveis, não texto livre) | Médio | Alto | O sistema já tem `{{variáveis}}` usado em `mensagem`/`orientacao` (`_resolve_sales_flow_variables()`) — dá para reaproveitar. Sem isso, o usuário não controla o formato que a API de destino espera. |
| 3 | Janela de horário permitido na espera (quiet hours) | Médio | Médio-Alto | Preocupação prática real: uma espera de "2 horas" configurada às 22h pode fazer o bot mandar mensagem às 00h. Todo concorrente pesquisado tem algo assim. |
| 4 | Botão de "testar agora" no builder do webhook | Médio | Médio | Não é gap funcional, mas todo concorrente tem — sem isso o usuário só descobre se configurou certo publicando de verdade. |
| 5 | Log de execução do webhook visível no builder/lead | Médio-Alto | Médio | Puramente de confiança/observabilidade — hoje só dá pra saber se disparou olhando o banco. |
| 6 | Espera até data/hora específica (não só duração relativa) | Baixo-Médio | Médio | Útil para lembretes/campanhas agendadas, mas a duração relativa já cobre a maioria dos casos de uso atuais do produto. |
| 7 | Espera com ramificação (responde → caminho A / silêncio → caminho B) | Alto | Alto | Maior gap estratégico, mas é conceitualmente uma feature nova (mistura `espera` com a lógica de ramificação que já existe em `condicao`), não um ajuste do bloco atual. |
| 8 | Mapear resposta do webhook para uma variável do lead | Alto | Alto (casos avançados) | Exigiria mudar o webhook de assíncrono (fire-and-forget, como é hoje) para síncrono nesse caso específico — maior risco arquitetural do lote, pois o fluxo precisaria esperar a resposta antes de continuar. |

**Recomendação:** #1 e #2 primeiro (baratos, reaproveitam código existente, resolvem
a limitação mais séria — hoje o webhook não serve para integrar com APIs reais que
exigem autenticação; dá para fazer como uma única implementação pequena). #3 é o
próximo bom custo-benefício. #7 e #8 são itens de roadmap separados — mudanças
estruturais maiores, não ajustes incrementais dos blocos atuais.

## M3 — Webhook: headers customizados + autenticação

**Prioridade: ALTA**

Ver tabela de priorização acima, item #1. Sem headers configuráveis (ex.:
`Authorization: Bearer ...`, API key), o bloco `webhook` não consegue integrar com a
maioria das APIs reais de mercado — é o gap mais crítico identificado na pesquisa.

**O que fazer:** adicionar lista de headers (chave/valor) na config do bloco
`webhook` (`CamadaFluxoVenda.tsx`), propagar pelo `system_action` →
`create_job` (`executor.py`) → payload do job → `httpx.request(..., headers=...)`
em `runners/sales_flow_webhook.py`.

## M4 — Webhook: corpo customizável (JSON com variáveis)

**Prioridade: ALTA**

Ver tabela acima, item #2. Hoje o campo `note` é texto livre solto no payload fixo
do job — o usuário não controla o formato JSON que a API de destino espera.

**O que fazer:** substituir/complementar `note` por um editor de corpo JSON no
builder, reaproveitando `_resolve_sales_flow_variables()` (já usado por
`mensagem`/`orientacao`, ver `docs/architecture/dynamic-variables.md`) para permitir
`{{lead.nome_whatsapp}}` etc. dentro do corpo.

## M5 — Espera: janela de horário permitido (quiet hours)

**Prioridade: MÉDIA**

Ver tabela acima, item #3. Sem isso, uma espera configurada à noite pode fazer o
bot retomar contato de madrugada — comportamento presente em todo concorrente
pesquisado (ManyChat: "continuar entre 8h–22h").

**O que fazer:** novo campo opcional no bloco `espera` (janela de horário
permitido); ao expirar a pausa fora da janela, adiar a retomada até o próximo
horário válido em vez de disparar imediatamente.

## M6 — Webhook: botão de teste no builder

**Prioridade: MÉDIA**

Ver tabela acima, item #4. Builder UX/confiança — hoje o usuário só descobre se
configurou a URL/método certos publicando de verdade.

## M7 — Webhook: log de execução visível

**Prioridade: MÉDIA**

Ver tabela acima, item #5. Observabilidade — histórico de disparos e status hoje só
existe na tabela `jobs`, sem nenhuma superfície no builder ou no card do lead.

## M8 — Espera: modo "até data/hora específica"

**Prioridade: MÉDIA**

Ver tabela acima, item #6. Complementa o modo atual (duração relativa) para casos de
lembrete/campanha agendada a uma data fixa, não relativa ao momento do disparo.

## M9 — Espera com ramificação (responde → caminho A / silêncio → caminho B)

**Prioridade: ALTA (impacto) / ALTO (esforço) — roadmap, não incremental**

Ver tabela acima, item #7. Maior gap estratégico da pesquisa — transforma `espera`
de pausa passiva em ponto de decisão ativo, como o "Wait for event" do SleekFlow/
Twilio Studio. Não é um ajuste do bloco `espera` atual: cruza com a lógica de
ramificação já existente em `condicao` (ver `docs/architecture/sales-flow.md`,
"Lógica de Ramificação") — provavelmente exige desenho próprio em Plan Mode antes de
qualquer implementação.

## M10 — Webhook: mapear resposta de volta para variável do lead

**Prioridade: ALTA (impacto, casos avançados) / ALTO (esforço) — roadmap**

Ver tabela acima, item #8. Exigiria mudar o webhook de assíncrono (fire-and-forget,
arquitetura atual) para síncrono nesse caso específico — o fluxo precisaria esperar
a resposta da API externa antes de continuar. Maior risco arquitetural do lote;
avaliar com cuidado antes de comprometer.
