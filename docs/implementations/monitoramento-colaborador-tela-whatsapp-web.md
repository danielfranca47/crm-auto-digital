# Tela estilo WhatsApp Web para monitoramento de colaboradores

**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`monitoramento-colaborador-whatsapp.md` (base do monitoramento de WhatsApp de
colaborador — ver [`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md)).

Hoje a única forma de ver as conversas monitoradas é abrindo cada lead
individualmente no Kanban (coluna "Monitorado"). O utilizador quer uma tela
nova, dedicada, que simule a experiência do WhatsApp Web: navegar pelos
telefones/colaboradores, entrar em cada conversa, ler mensagens e ver mídias
enviadas/recebidas — com filtro por colaborador, por instância, ou exibindo
todas de uma vez.

---

## Contexto técnico conhecido (para o diagnóstico de Plan Mode)

- Fonte de dados já existe: leads com `category='monitoring'` +
  `collab_monitor_instance_id` preenchido (`leads` table), mensagens em
  `messages` (`model='inbound'` ou `model='human_agent'`).
- `collab_monitor_instances` (backend-crm) já expõe nome do colaborador +
  status de conexão — a tela precisa de um endpoint que agregue
  "colaborador → leads → mensagens" em vez de navegar lead por lead.
- Mídia: hoje `monitor_inbound_handler.py` **ignora mensagens sem texto**
  (imagem/áudio) — ver `docs/implementations/monitoramento-colaborador-whatsapp.md`
  (já graduado). Se esta tela precisa exibir mídia, o tratamento de mídia no
  handler de ingestão precisa ser resolvido primeiro (ou como fase interna
  desta mesma implementação).
- Frontend: provavelmente uma página nova (não um painel dentro de
  `AiProfile.tsx`, que hoje só tem o cadastro mínimo em
  `MonitoramentoColaboradores.tsx`) — decisão de produto sobre navegação
  (rota própria vs. modal) fica para o Plan Mode.

---

## Próximo passo

Plan Mode: diagnóstico completo (já existe / o que construir / riscos) antes
de qualquer código, seguindo
[`_guia-documentar-implementacao.md`](_guia-documentar-implementacao.md).
