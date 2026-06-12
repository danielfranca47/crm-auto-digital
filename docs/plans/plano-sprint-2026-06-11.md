# Plano de Sprint — Meta Cloud API (WhatsApp Oficial) para Scale e Enterprise

> Gerado em 11/06/2026 com base em análise dos arquivos `scale-enterprise-roadmap.md`,
> `plans-subscriptions.md` e auditoria do código existente.
> Atualizado em 11/06/2026 após respostas do admin às perguntas abertas.

**Data de geração:** 11/06/2026
**Arquivos analisados:** `scale-enterprise-roadmap.md` · `plans-subscriptions.md`
**Status:** Perguntas respondidas — aguardando credenciais de teste Meta para iniciar P1

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

> Todas respondidas em 11/06/2026.

### Q1 (experiência — impacta F3)
Clientes Scale/Enterprise que já têm conexão UazAPI ativa: a migração para Meta é
**obrigatória** (o plano novo só aceita Meta) ou **opcional** (UazAPI e Meta coexistem
no mesmo plano)?

> R (admin): _Não, só existirá para os planos scale e enterprise a api oficial_

**Impacto:** P3 precisa bloquear a criação de conexões UazAPI para planos Scale/Enterprise — não é
apenas um gate de `max_instances`, mas também um gate de provider. Como os planos ainda não
estão à venda, não há clientes a migrar; o bloqueio só afeta novos onboardings.

---

### Q2 (experiência — impacta F4)
Quando o follow-up tenta enviar após +24h de inatividade do cliente e não há template
Meta configurado para aquele usuário, o que deve acontecer?

> R (admin): _(b) deve cancelar e mostrar a justificativa para o usuário_

**Impacto:** Fase 4 precisa criar um registro de cancelamento com motivo visível no painel do
cliente (componente de UI a mais além da lógica de estado). Nada que bloqueie, mas deve ser
detalhado no Plan Mode da Fase 4.

---

### Q3 (estratégia — impacta F3)
A conexão via Meta Cloud API ficará disponível **apenas para Scale e Enterprise**, ou
também para o plano Growth como upgrade opcional?

> R (admin): _Somente para os planos Scale e Enterprise_

**Impacto:** Confirma o design já assumido no sprint. Sem ajuste necessário.

---

### Q4 (estratégia — impacta modelo de cobrança)
O custo por mensagem da Meta (marketing ~US$0,025/msg; utility muito menor) será
**absorvido no preço do plano** ou **repassado ao cliente** como excedente adicional ao
limite de conversas IA?

> R (admin): _Repassado ao cliente_

**Impacto:** Não bloqueia nenhuma fase deste sprint. Vai precisar de um sprint futuro dedicado
a tracking e reporting de custo Meta por cliente (dashboard de consumo ou exportação de log).
Nota para manutenção: este item não está coberto em nenhum dos `plans/*` atuais — será necessário
criar um novo arquivo de plano quando chegar o momento.

---

### Q5 (estratégia — desbloqueia F0 imediatamente)
O seed `crm_scale` e `crm_enterprise` pode ser entregue **agora** (planos ativáveis no
painel admin manualmente), mesmo antes de qualquer desenvolvimento na API Meta?

> R (admin): _não, a ideia é disponibilizarmos primeiro essa funcionalidade que vai ser a base dele antes de vender_

**Impacto:** F0 (seed + max_instances) deixa de ser a primeira entrega e passa a ser
implementado **após** P1 (Fases 1+2) estar validado. A ordem do sprint foi reajustada
em conformidade. Ver nova sequência abaixo.

---

### Q6 (configuração externa — impacta onboarding F3)
Já existe um **App criado no Meta for Developers** com WhatsApp Business Platform
configurado, ou o processo de criação do App é algo que o admin/cliente precisa fazer
do zero ao contratar Scale/Enterprise?

> R (admin): _eu ainda não realizei nenhuma configuração externa para esta fase. precisarei de instruções. Estava a ler o https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/get-started-for-tech-providers e vi que será um processo longo de verificações por parte da meta mas necessário a se cumprir de outras exigencias. Estou determinado a fazer_

**Esclarecimento e impacto — ler antes de iniciar P1:**

A documentação lida é o caminho **Tech Provider / Solution Provider** — que é o caminho
correto para um SaaS onde cada cliente conecta o seu próprio número de WhatsApp. Mas há
dois modelos de autorização possíveis com implicações diferentes para P3:

| Abordagem | Como o cliente conecta | Exigência Meta |
|---|---|---|
| **Manual (token direto)** | Cliente cria App próprio no Meta, copia `phone_number_id` + `access_token` e cola na UI | Nenhuma aprovação adicional para este fluxo; cliente precisa ter App Meta próprio |
| **Embedded Signup (OAuth)** | Cliente clica num botão na plataforma → fluxo OAuth Meta → credenciais entregues automaticamente | Requerido para Tech Providers com múltiplos clientes; Meta exige demonstração no App Review |

Para um CRM SaaS com clientes normais (não técnicos), **Embedded Signup é o caminho correto
a longo prazo**. Pedir que o cliente copie tokens manualmente não é viável em escala.
A Meta também tende a exigir Embedded Signup durante o App Review para plataformas multi-tenant.

**Decisão para este sprint:** P3 será implementado com **token manual** (abordagem beta fechada
para os primeiros clientes Scale/Enterprise). O Embedded Signup entra num sprint posterior.
Isso é aceite pela Meta desde que o App Review inclua um disclaimer de "versão beta, Embedded
Signup em roadmap".

**A verificação deve correr em paralelo com o desenvolvimento, não antes:**

- O desenvolvimento (P1, P2) pode arrancar com a **test WABA** que a Meta disponibiliza
  gratuitamente ao criar o App — sem nenhuma aprovação necessária
- O bloqueio para produção é a Business Verification + App Review — processo de 2–4 semanas
- Se o desenvolvimento começar agora e a verificação começar agora, os dois terminam
  aproximadamente ao mesmo tempo

**O que a Meta verifica no App Review e riscos de reprovação:**

| Exigência | Risco | Mitigação |
|---|---|---|
| HTTPS no webhook endpoint | Baixo — produção já usa HTTPS | Confirmar antes de submeter |
| Privacy Policy acessível publicamente | Baixo — website tem, mas precisa estar publicado | Verificar URL no momento de submeter |
| Vídeo de demo do fluxo completo | Médio — precisa mostrar lead respondendo e bot com reply | Gravar após P1+P2 funcionando com test WABA |
| Uso legítimo (não spam) | Baixo — CRM com leads que iniciaram contato é caso aprovável | Q2 (cancelar fora de 24h) já documenta consciência das regras Meta |
| Embedded Signup no demo (para Tech Provider) | Médio — sem Embedded Signup, Meta pode pedir revisão | Submeter com token manual + disclaimer de roadmap |

---

## Pré-requisito externo — tarefa do admin (esta semana)

**Este passo desbloqueia P1 (desenvolvimento).** Sem as credenciais de teste, o dev não tem
como testar envio ou inbound Meta.

**Passo A — Business Verification (iniciar imediatamente, corre em paralelo):**
1. Aceder a [business.facebook.com](https://business.facebook.com) → Settings → Business Info
2. Iniciar Business Verification com documentos da empresa
3. Timeline: 3 dias a 2 semanas dependendo da documentação

**Passo B — Criar o Meta App e obter credenciais de teste (prioritário para dev):**
1. Aceder a [developers.facebook.com](https://developers.facebook.com) → Create App → Business
2. Add Product → WhatsApp → configurar WhatsApp Business Platform
3. No painel do App: obter o test WABA com `phone_number_id` e `access_token` de teste
4. Partilhar essas credenciais de teste para iniciar P1

**Passo C — Submeter App Review (após P1+P2 validados, antes de P3 ir a produção):**
1. Solicitar permissões `whatsapp_business_messaging` + `whatsapp_business_management`
2. Gravar vídeo de demo mostrando o ciclo completo (cliente envia → bot responde)
3. Incluir disclaimer: "fluxo beta com token manual; Embedded Signup em desenvolvimento"
4. Timeline após submissão: 3–10 dias úteis

---

## Sprint — Itens selecionados (ordem revisada)

> Ordem ajustada com base nas respostas Q5 e Q6: P1 (Fases 1+2) agora é a primeira
> entrega de código; F0 (seed) passou para P2 pois os planos só devem ser ativáveis
> após a API Meta estar funcional.

---

### P1 — Fases 1+2: Meta Cloud Client + Webhook inbound

**Origem:** pesquisa técnica realizada em 11/06/2026
**Prioridade:** ALTA — fundação técnica da qual todas as fases seguintes dependem
**Esforço estimado:** médio-alto (novo provider, novo endpoint, normalização de payload)
**Dependências:** credenciais de teste Meta (Passo B do pré-requisito externo acima)

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

### P2 — Fase 0: Fundação de dados (seed + max_instances)

**Origem:** `docs/plans/scale-enterprise-roadmap.md` — P1 e P2
**Prioridade:** ALTA — bloqueia a ativação de qualquer cliente Scale/Enterprise
**Esforço estimado:** baixo (1–2 arquivos no backend-core, sem impacto em outros serviços)
**Dependências:** P1 validado — os planos só devem ser ativáveis após a API Meta estar funcional (Q5)

**Contexto:**
O `PlanLimits` não tem o campo `max_instances`, e os planos `crm_scale` e `crm_enterprise`
não existem no seed. O fundador confirmou (Q5) que esses planos não devem estar disponíveis
antes da API Meta estar operacional — portanto esta fase vem após P1 validado.

**Nota sobre Q1:** além de criar os planos, esta fase deve garantir que conexões com
`provider="uazapi"` são bloqueadas para usuários Scale/Enterprise — só `provider="meta"` é
permitido nesses planos. O gate pode ser implementado aqui ou em P3; o Plan Mode vai definir
o ponto mais natural de aplicação.

**Entrega esperada:**
- Admin consegue ativar `crm_scale` ou `crm_enterprise` pelo painel após o deploy
- O campo `max_instances` existe no modelo e no banco, pronto para ser verificado em P3
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

Contexto adicional (Q1): planos Scale e Enterprise só permitem conexões com
provider="meta" — conexões UazAPI devem ser bloqueadas para esses planos.
Verificar se o ponto natural de aplicação deste gate é aqui (seed/modelo) ou
em P3 (rota de criação de conexão) e decidir no Plan Mode.

Área do sistema: backend-core (modelo PlanLimits + seed de planos).
Referência de arquitectura do modelo: docs/plans/scale-enterprise-roadmap.md.

Leia o docs\implementations\_guia-documentar-implementacao.md e siga o processo.
```

---

### P3 — Fase 3: Onboarding Meta + gate de instâncias

**Origem:** pesquisa técnica realizada em 11/06/2026
**Prioridade:** MÉDIA — necessária para que o cliente consiga configurar a conexão Meta
sem intervenção manual do admin
**Esforço estimado:** médio (nova rota backend + UI frontend + gate max_instances)
**Dependências:** P1 (conexão Meta funcional end-to-end) + P2 (max_instances no PlanLimits)

**Contexto:**
Sem esta fase, conectar uma instância Meta requer que o admin intervenha manualmente no
banco para criar o registro. A Fase 3 entrega o fluxo de onboarding self-service: o cliente
Scale/Enterprise entra com as credenciais Meta e o sistema valida, salva e ativa automaticamente.

**Decisão de abordagem (derivada de Q6):** esta fase implementa **token manual** (beta fechado).
O cliente insere `phone_number_id` e `access_token` diretamente na UI. Esta abordagem é
válida para os primeiros clientes Scale/Enterprise. O fluxo **Embedded Signup** (OAuth completo,
Meta-preferred para Tech Providers) entra num sprint posterior e precisa de App Review aprovado
antes de poder ser implementado em produção.

**Entrega esperada:**
- Cliente Scale/Enterprise consegue conectar um número Meta sem intervenção do admin
- Ao atingir o limite de instâncias do plano (`max_instances`), sistema bloqueia com mensagem clara
- Tentativa de criar conexão UazAPI num plano Scale/Enterprise é bloqueada com mensagem clara
- A UI do frontend-crm oferece dois caminhos distintos: "Conectar via QR Code" (UazAPI,
  planos Start/Growth) e "Conectar via API Meta" (visível apenas para Scale/Enterprise)

**Nota:** este prompt só deve ser disparado **após** P1 e P2 estarem com checks validados e
após as credenciais definitivas de produção Meta estarem disponíveis (App Review aprovado
ou ambiente beta com test WABA).

**Prompt para o processo de implementations:**
```
Gostaria de implementar o fluxo de onboarding self-service para conexões Meta Cloud API.
Actualmente não há como um cliente configurar uma conexão Meta sem intervenção manual
do admin no banco de dados.

Comportamento actual: não existe rota para criar conexão Meta. O único fluxo de
conexão é QR Code via UazAPI.
Comportamento desejado: clientes nos planos Scale e Enterprise conseguem conectar um
número Meta inserindo phone_number_id e access_token diretamente na UI (abordagem beta:
token manual; Embedded Signup OAuth entra em sprint posterior).
O sistema valida as credenciais antes de salvar (chamada de teste à Meta Graph API).
Cria o registro com provider="meta" e ativa a conexão.
Dois gates aplicados: (1) se o plano atingiu max_instances, criação bloqueada com
mensagem clara; (2) se o plano for Scale ou Enterprise, tentativa de criar conexão
UazAPI é bloqueada.

Área do sistema: backend-core (nova rota /whatsapp/connect-meta + validação de token
+ gates) + frontend-crm (nova opção no fluxo de conexão de WhatsApp, condicionada
ao plano do utilizador, com dois caminhos: QR Code para Start/Growth e API Meta para
Scale/Enterprise).

Dependência: P1 (Meta Cloud Client funcional) e P2 (max_instances no PlanLimits)
devem estar implementados e validados antes de iniciar esta fase.

Leia o docs\implementations\_guia-documentar-implementacao.md e siga o processo.
```

---

## Fases futuras (fora deste sprint)

### Fase 4 — Templates Meta + follow-up fora da janela 24h

**Motivo de exclusão:** depende de P3 estar em produção e validado. Esforço alto
(nova tabela + CRUD + lógica de follow-up + componente de UI para cancelamento).
Entra no próximo sprint após validação de P1–P3.

**Contexto para o próximo sprint:**
A Meta exige templates pré-aprovados para qualquer contato após 24h de inatividade do cliente.
O follow-up atual envia texto livre — isso seria rejeitado pela API. Templates precisam de
CRUD próprio, aprovação pela Meta (24–48h) e lógica no `followup_state.py` para detectar
a janela e escolher entre texto livre (< 24h) ou template aprovado (> 24h).

Admin confirmou (Q2): quando o follow-up cai fora da janela sem template configurado,
o comportamento é **cancelar o follow-up daquele lead e registrar a justificativa visível
ao cliente no painel**. A Fase 4 precisa de um componente de UI para exibir esse status
além da lógica de estado.

---

### Fase 5 — Download de áudio via Meta Graph API

**Motivo de exclusão:** depende de P1 (inbound Meta) e é um refinamento — a ausência de Fase 5
não impede o sistema de funcionar, apenas faz com que áudios recebidos via Meta caiam no
`media_fallback` em vez de serem transcritos. Baixo risco de bloquear a entrega principal.

**Contexto para o próximo sprint:**
A UazAPI fornece uma URL temporária para download de áudio. A Meta usa um fluxo diferente:
GET `/{media_id}` retorna a URL, que então requer `Authorization: Bearer {token}` para download.
A `audio_transcription.py` precisa de um segundo método de download consciente do provider.

---

### Fase 6 — Embedded Signup (OAuth Meta)

**Motivo de exclusão:** depende de App Review aprovado e envolve implementação de fluxo
OAuth completo com Facebook Login. Entra num sprint posterior após P3 beta validado com
os primeiros clientes.

**Contexto:** o Embedded Signup substitui o token manual de P3. O cliente clica num botão,
autoriza o App Meta via OAuth, e as credenciais chegam automaticamente — sem copiar tokens.
Meta preferred para Tech Providers com múltiplos clientes. Requer que o App Review já tenha
sido aprovado com o fluxo de demo.

---

### Sprint futuro — Tracking de custo Meta por cliente

**Motivo de exclusão:** admin confirmou (Q4) que o custo por mensagem Meta é repassado ao
cliente. Será necessário um sprint dedicado a tracking e reporting deste custo (dashboard
de consumo ou exportação de log). Não bloqueia nenhuma fase técnica atual.

---

## Tracking de absorção

> Atualizado pelo Claude de implementations durante o ciclo de vida do sprint.
> Cada item é marcado ✅ na graduação da sua implementação. Quando todos estiverem ✅,
> a limpeza de `docs/plans/*` e deste arquivo é feita no mesmo commit de graduação.

| # | Item | Arquivo de implementação | Status | Commit de graduação |
|---|---|---|---|---|
| P1 | Meta Cloud Client + Webhook inbound (Fases 1+2) | — | ⏳ Aguardando credenciais Meta | — |
| P2 | Fundação de dados — seed + max_instances (Fase 0) | — | ⏳ Aguardando P1 validado | — |
| P3 | Onboarding Meta UI + gate de instâncias (Fase 3) | — | ⏳ Aguardando P1 + P2 | — |

---

## Manutenção dos arquivos docs/plans/*

> Executada automaticamente pelo Claude de implementations no Passo 6b da graduação,
> quando o Tracking de absorção estiver completo (todos ✅).

| Arquivo plans/* | Condição para deletar |
|---|---|
| `scale-enterprise-roadmap.md` | Quando P1, P2 e P3 estiverem todos absorvidos E Fases 4, 5 e 6 tiverem sido absorvidas em sprint posterior |
| `plans-subscriptions.md` | Não deletar neste sprint — contém definições de produto ainda em uso |
