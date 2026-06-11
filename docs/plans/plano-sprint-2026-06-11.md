# Plano de Sprint — Meta Cloud API (WhatsApp Oficial) para Scale e Enterprise

> Gerado em 11/06/2026 com base em análise dos arquivos `scale-enterprise-roadmap.md`,
> `plans-subscriptions.md` e auditoria do código existente.

**Data de geração:** 11/06/2026
**Arquivos analisados:** `scale-enterprise-roadmap.md` · `plans-subscriptions.md`
**Status:** Aguardando confirmação de perguntas abertas (ver seção abaixo)

---

## Contexto e motivação

O fundador confirmou (resposta E1 em `plans-subscriptions.md`) que os planos Scale e Enterprise
dependem de dois pré-requisitos técnicos: **clonagem de voz** e **compatibilidade com a API
oficial da Meta**. Este sprint trata do segundo.

A API oficial (Meta Cloud API) resolve o risco principal do modelo atual com UazAPI:
- Contas UazAPI com volume alto são banidas em 2–8 semanas
- Com a Meta API, um único App pode ter até 20 números verificados — elimina a necessidade
  de múltiplas instâncias físicas e o risco estrutural de bloqueio

---

## Diagnóstico — Todos os itens auditados

| # | Item | Arquivo de origem | Status no sistema |
|---|---|---|---|
| F0-A | `max_instances` em `PlanLimits` | `scale-enterprise-roadmap.md` P2 | ❌ Campo ausente — `plan_limits.py` não tem `max_instances` |
| F0-B | Seed `crm_scale` + `crm_enterprise` | `scale-enterprise-roadmap.md` P1 | ❌ Não existe — `seed_initial_data()` não tem esses planos |
| F1 | `meta_cloud_client.py` — envio outbound | pesquisa externa | ❌ Não existe — `providers/` só tem `uazapi_client.py` |
| F1 | Roteador de provider (UazAPI ↔ Meta) | pesquisa externa | ❌ Não existe — executors chamam UazAPI diretamente |
| F2 | Webhook inbound Meta (`/webhooks/whatsapp/meta`) | pesquisa externa | ❌ Não existe — só existe `/webhooks/whatsapp/uazapi` |
| F2 | Endpoint GET de verificação (handshake Meta) | pesquisa externa | ❌ Não existe — Meta exige antes de ativar o webhook |
| F2 | Normalização payload Meta → formato interno | pesquisa externa | ❌ Não existe — só existe para UazAPI em `inbound_handler.py` |
| F3 | Rota `connect-meta` (backend-core) | pesquisa externa | ❌ Não existe — atual é QR Code UazAPI |
| F3 | Gate de `max_instances` na criação de conexão | `scale-enterprise-roadmap.md` P2 | ❌ Não existe — sem verificação de slots |
| F3 | UI de onboarding Meta no frontend-crm | pesquisa externa | ❌ Não existe — atual é QR Code UazAPI |
| F4 | Gestão de templates Meta (CRUD) | pesquisa externa | ❌ Não existe — sem tabela `whatsapp_templates` |
| F4 | Follow-up com template fora da janela 24h | pesquisa externa | ❌ Não existe — follow-up usa texto livre (rejeitado pela Meta) |
| F5 | Download de áudio via Meta Graph API | pesquisa externa | ❌ Não existe — atual usa URL temporária da UazAPI |

**Observação positiva:** `WhatsappConnection` já tem campo `provider` (linha 19,
`backend-core/app/models/whatsapp_connection.py`) com `default="uazapi"`. O modelo de dados
está preparado para multi-provider — só falta implementar a lógica.

**Correlações identificadas:**
- F0-A e F0-B têm sinergia total: mesmo arquivo de seed, mesmo momento de implementação
- F1 e F2 são tecnicamente acopladas: envio e inbound do mesmo provider devem ser entregues
  juntos para que o ciclo end-to-end possa ser testado
- F3 depende de F1+F2: só faz sentido fazer onboarding quando há envio e inbound funcionando
- F4 depende de F3: templates só são úteis quando há conexões Meta ativas
- F5 depende de F1+F2 mas é independente de F3 e F4

---

## Perguntas abertas para o admin

> As respostas abaixo serão preenchidas antes de avançar para a implementação de cada fase.
> Perguntas de F0 não têm bloqueador — essa fase pode ser implementada sem resposta.

### Q1 (experiência — impacta F3)
Clientes Scale/Enterprise que já têm conexão UazAPI ativa: a migração para Meta é
**obrigatória** (o plano novo só aceita Meta) ou **opcional** (UazAPI e Meta coexistem
no mesmo plano)?

> R (admin): _a preencher_

---

### Q2 (experiência — impacta F4)
Quando o follow-up tenta enviar após +24h de inatividade do cliente e não há template
Meta configurado para aquele usuário, o que deve acontecer?

- (a) Pausa o follow-up deste lead e exibe alerta no painel para o admin agir
- (b) Cancela definitivamente o follow-up deste lead (sai da fila)
- (c) Envia como texto livre mesmo assim e assume o risco de rejeição pela Meta

> R (admin): _a preencher_

---

### Q3 (estratégia — impacta F3)
A conexão via Meta Cloud API ficará disponível **apenas para Scale e Enterprise**, ou
também para o plano Growth como upgrade opcional?

> R (admin): _a preencher_

---

### Q4 (estratégia — impacta modelo de cobrança)
O custo por mensagem da Meta (marketing ~US$0,025/msg; utility muito menor) será
**absorvido no preço do plano** ou **repassado ao cliente** como excedente adicional ao
limite de conversas IA?

> R (admin): _a preencher_

---

### Q5 (estratégia — desbloqueia F0 imediatamente)
O seed `crm_scale` e `crm_enterprise` pode ser entregue **agora** (planos ativáveis no
painel admin manualmente), mesmo antes de qualquer desenvolvimento na API Meta?

> R (admin): _a preencher_

---

### Q6 (configuração externa — impacta onboarding F3)
Já existe um **App criado no Meta for Developers** com WhatsApp Business Platform
configurado, ou o processo de criação do App é algo que o admin/cliente precisa fazer
do zero ao contratar Scale/Enterprise?

> R (admin): _a preencher_

---

## Sprint — Itens selecionados

### P1 — Fase 0: Fundação de dados (seed + max_instances)

**Origem:** `docs/plans/scale-enterprise-roadmap.md` — P1 e P2
**Prioridade:** ALTA — bloqueia a ativação manual de qualquer cliente Scale/Enterprise
**Esforço estimado:** baixo (1–2 arquivos no backend-core, sem impacto em outros serviços)
**Dependências:** nenhuma — pode ser implementado agora sem nenhuma resposta pendente

**Contexto:**
O `PlanLimits` não tem o campo `max_instances`, e os planos `crm_scale` e `crm_enterprise`
não existem no seed. Isso significa que mesmo que o admin queira ativar um cliente Scale
manualmente hoje, não tem como — o plano não existe no banco. Esta fase resolve isso sem
tocar em nenhuma lógica de envio ou webhook.

**Entrega esperada:**
- Admin consegue ativar `crm_scale` ou `crm_enterprise` pelo painel imediatamente após o deploy
- O campo `max_instances` existe no modelo e no banco, pronto para ser verificado na Fase 3
- Limites do Scale: `max_leads=5000`, `max_ia_conversas_monthly=1500`,
  `max_whatsapp_send_daily=200`, `max_instances=3`, `follow_up_enabled=True`,
  `playground_monthly_limit=None`
- Limites do Enterprise: `max_leads=None`, `max_ia_conversas_monthly=5000`,
  `max_whatsapp_send_daily=None`, `max_instances=5`, `follow_up_enabled=True`,
  `playground_monthly_limit=None`

**Prompt para o processo de implementations:**
```
Gostaria de preparar a fundação de dados para os planos Scale e Enterprise.
Actualmente nem o plano crm_scale nem o crm_enterprise existem no banco — qualquer
tentativa de ativar esses planos no painel admin falha silenciosamente.

Comportamento actual: o seed_initial_data() não tem crm_scale nem crm_enterprise.
O modelo PlanLimits não tem o campo max_instances. Admin não consegue ativar
clientes nesses planos.
Comportamento desejado: os dois planos existem no banco com os limites definidos
abaixo. O campo max_instances existe no PlanLimits (nullable = ilimitado).
O admin consegue ativar qualquer cliente em Scale ou Enterprise pelo painel.

Limites do crm_scale: max_leads=5000, max_ia_conversas_monthly=1500,
max_whatsapp_send_daily=200, max_instances=3, follow_up_enabled=True,
playground_monthly_limit=None.
Limites do crm_enterprise: max_leads=None, max_ia_conversas_monthly=5000,
max_whatsapp_send_daily=None, max_instances=5, follow_up_enabled=True,
playground_monthly_limit=None.

Área do sistema: backend-core (modelo PlanLimits + seed de planos).
Referência de arquitectura do modelo: docs/plans/scale-enterprise-roadmap.md.

Leia o docs\implementations\_guia-documentar-implementacao.md e siga o processo.
```

---

### P2 — Fases 1+2: Meta Cloud Client + Webhook inbound

**Origem:** pesquisa técnica realizada em 11/06/2026
**Prioridade:** ALTA — fundação técnica da qual todas as fases seguintes dependem
**Esforço estimado:** médio-alto (novo provider, novo endpoint, normalização de payload)
**Dependências:** P1 (recomendado, não bloqueante) — sem P1 o teste end-to-end não valida planos

**Contexto:**
Toda a arquitetura de envio e recepção atual é exclusiva para UazAPI. Para suportar a Meta
Cloud API, o sistema precisa de uma camada de abstração de provider (um roteador que escolhe
UazAPI ou Meta com base no `connection.provider`) e de um novo endpoint de webhook para
receber mensagens da Meta no formato dela.

As duas partes (envio outbound + inbound) são entregues juntas porque uma sem a outra não
permite validação end-to-end: inbound sem envio = bot recebe mas não responde; envio sem
inbound = bot responde mas não recebe.

**Entrega esperada:**
- Uma conexão WhatsApp com `provider="meta"` consegue enviar e receber mensagens pelo mesmo
  pipeline de IA que o UazAPI usa hoje (sem duplicação de lógica)
- O endpoint `/webhooks/whatsapp/meta` está ativo com o handshake GET obrigatório da Meta
- O payload da Meta é normalizado para o `InboundEvent` interno — `inbound_handler.py` e
  toda a lógica downstream não percebem a diferença de provider
- Tipos de mensagem suportados nesta fase: `text`, `audio` (ptt), `image` — suficientes para
  o ciclo básico de qualificação e follow-up

**Prompt para o processo de implementations:**
```
Gostaria de implementar o suporte à Meta Cloud API como provider de WhatsApp.
Actualmente todo o envio e recepção de mensagens passa exclusivamente pela UazAPI.
Clientes nos planos Scale e Enterprise precisam de poder usar a API oficial da Meta
para eliminar o risco de bloqueio de conta com volumes altos.

Comportamento actual: o executor chama sempre a UazAPI para envio. O único webhook
inbound é /webhooks/whatsapp/uazapi. Não há suporte a nenhum outro provider.
Comportamento desejado: uma conexão com provider="meta" usa a Meta Cloud API para
envio (via Graph API v21.0) e recebe mensagens pelo novo endpoint
/webhooks/whatsapp/meta. Todo o pipeline downstream (inbound_handler, orchestrator,
LLM, follow-up) funciona igual — o provider é transparente para essas camadas.

Referência técnica externa:
- Envio: POST https://graph.facebook.com/v21.0/{phone_number_id}/messages
  com Bearer token e JSON conforme Meta Graph API
- Inbound: Meta envia POST com payload entry[].changes[].value.messages[]
  e exige verificação GET com hub.verify_token antes de ativar
- Biblioteca Python recomendada: pywa (pywa.readthedocs.io) ou implementação direta

O campo provider="meta" já existe em WhatsappConnection (linha 19,
backend-core/app/models/whatsapp_connection.py). O modelo está preparado.

Área do sistema: backend-core (novo provider client) + backend-crm (novo endpoint
webhook + normalização) + backend-executors (roteador de provider no runner de envio).

Leia o docs\implementations\_guia-documentar-implementacao.md e siga o processo.
```

---

### P3 — Fase 3: Onboarding Meta + gate de instâncias

**Origem:** pesquisa técnica realizada em 11/06/2026
**Prioridade:** MÉDIA — necessária para que o cliente consiga configurar a conexão Meta
sem intervenção manual do admin
**Esforço estimado:** médio (nova rota backend + UI frontend + gate max_instances)
**Dependências:** P1 (gate max_instances) + P2 (conexão Meta funcional end-to-end)

**Contexto:**
Sem esta fase, conectar uma instância Meta requer que o admin intervenha manualmente no
banco para criar o registro. A Fase 3 entrega o fluxo de onboarding self-service: o cliente
Scale/Enterprise entra com as credenciais Meta (phone_number_id + access_token) e o sistema
valida, salva e ativa automaticamente.

O gate de `max_instances` impede que um plano Start ou Growth conecte um número Meta quando
não deveria.

**Entrega esperada:**
- Cliente Scale/Enterprise consegue conectar um número Meta sem intervenção do admin
- Ao atingir o limite de instâncias do plano, o sistema bloqueia com mensagem de erro clara
- A UI do frontend-crm oferece dois caminhos: "Conectar via QR Code" (UazAPI, planos Start/Growth)
  e "Conectar via API Meta" (visível apenas para Scale/Enterprise ou conforme Q3)

**Nota:** este prompt só deve ser disparado **após** P1 e P2 estarem com checks validados.

**Prompt para o processo de implementations:**
```
Gostaria de implementar o fluxo de onboarding self-service para conexões Meta Cloud API.
Actualmente não há como um cliente configurar uma conexão Meta sem intervenção manual
do admin no banco de dados.

Comportamento actual: não existe rota para criar conexão Meta. O único fluxo de
conexão é QR Code via UazAPI.
Comportamento desejado: clientes nos planos elegíveis (Scale/Enterprise) conseguem
conectar um número Meta inserindo phone_number_id e access_token diretamente na UI.
O sistema valida as credenciais (chamada de teste à Meta Graph API antes de salvar),
cria o registro com provider="meta" e ativa a conexão. Se o plano atingiu o limite
max_instances, a criação é bloqueada com mensagem clara.

Área do sistema: backend-core (nova rota /whatsapp/connect-meta + validação de token
+ gate max_instances usando o campo criado em P1) + frontend-crm (nova opção no fluxo
de conexão de WhatsApp, condicionada ao plano do utilizador).

Dependência: P1 (max_instances no PlanLimits) e P2 (cliente Meta funcional) devem
estar implementados e validados antes de iniciar esta fase.

Leia o docs\implementations\_guia-documentar-implementacao.md e siga o processo.
```

---

## Fases futuras (fora deste sprint)

### Fase 4 — Templates Meta + follow-up fora da janela 24h

**Motivo de exclusão:** depende de Q2 (decisão de produto sobre comportamento com +24h sem template)
e de P3 estar em produção e validado. Esforço alto (nova tabela + CRUD + lógica de follow-up).
Entra no próximo sprint após validação de P1–P3.

**Contexto para o próximo sprint:**
A Meta exige templates pré-aprovados para qualquer contato após 24h de inatividade do cliente.
O follow-up atual envia texto livre — isso seria rejeitado pela API. Templates precisam de
CRUD próprio, aprovação pela Meta (24–48h) e lógica no `followup_state.py` para detectar
a janela e escolher entre texto livre (< 24h) ou template aprovado (> 24h).

---

### Fase 5 — Download de áudio via Meta Graph API

**Motivo de exclusão:** depende de P2 (inbound Meta) e é um refinamento — a ausência de Fase 5
não impede o sistema de funcionar, apenas faz com que áudios recebidos via Meta caiam no
`media_fallback` em vez de serem transcritos. Baixo risco de bloquear a entrega principal.

**Contexto para o próximo sprint:**
A UazAPI fornece uma URL temporária para download de áudio. A Meta usa um fluxo diferente:
GET `/{media_id}` retorna a URL, que então requer `Authorization: Bearer {token}` para download.
A `audio_transcription.py` precisa de um segundo método de download consciente do provider.

---

## Tracking de absorção

> Atualizado pelo Claude de implementations durante o ciclo de vida do sprint.
> Cada item é marcado ✅ na graduação da sua implementação. Quando todos estiverem ✅,
> a limpeza de `docs/plans/*` e deste arquivo é feita no mesmo commit de graduação.

| # | Item | Arquivo de implementação | Status | Commit de graduação |
|---|---|---|---|---|
| P1 | Fundação de dados — seed + max_instances | — | ⏳ Pendente | — |
| P2 | Meta Cloud Client + Webhook inbound | — | ⏳ Pendente | — |
| P3 | Onboarding Meta UI + gate de instâncias | — | ⏳ Pendente | — |

---

## Manutenção dos arquivos docs/plans/*

> Executada automaticamente pelo Claude de implementations no Passo 6b da graduação,
> quando o Tracking de absorção estiver completo (todos ✅).

| Arquivo plans/* | Condição para deletar |
|---|---|
| `scale-enterprise-roadmap.md` | Quando P1, P2 e P3 estiverem todos absorvidos E Fases 4 e 5 tiverem sido absorvidas em sprint posterior |
| `plans-subscriptions.md` | Não deletar neste sprint — contém definições de produto ainda em uso |
