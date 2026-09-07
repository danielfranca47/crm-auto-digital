# IA mãe classifica estágio do lead monitorado

**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`monitoramento-colaborador-whatsapp.md` (base do monitoramento de WhatsApp de
colaborador — ver [`docs/architecture/collab-monitor.md`](../architecture/collab-monitor.md)).

Hoje, todo lead criado pelo monitoramento de colaborador nasce na categoria
fixa `"monitoring"` (coluna "Monitorado" do Kanban) e nunca sai dali
automaticamente. O utilizador quer que a IA mãe **leia a conversa** do
colaborador com o lead e identifique o estágio real (qualificação,
apresentação, fechamento, etc.) — o mesmo tipo de classificação que já existe
para o pipeline do agente (`suggested_category` em `decision_engine.py`) —
posicionando o lead monitorado na coluna correspondente do Kanban.

---

## Contexto técnico conhecido (para o diagnóstico de Plan Mode)

- Hoje `services/collab_monitor/monitor_inbound_handler.py::handle_monitor_inbound()`
  **nunca** chama `orchestrator.py`/`decision_engine.py` — é justamente essa
  separação que garante que o monitoramento não aciona a IA nem o envio. Uma
  classificação de estágio precisaria de um caminho de LLM **read-only**
  (só analisa, nunca decide resposta nem aciona envio) — provavelmente
  reaproveitando o padrão de `services/spy_agent/module_sales_pipeline.py`
  (análise de pipeline de vendas já existente no Agente Espião, mas hoje
  aplicada de forma agregada/uma vez, não por lead/mensagem).
- Precisa de decisão de produto: a classificação roda a cada mensagem nova
  (custo de LLM por mensagem) ou em lote/periodicamente? Que guardrail evita
  a IA mover um lead "sozinha" de forma errada (equivalente ao que
  `qualification_guardrails.py` faz para o pipeline real)?
- Pontos prováveis de mudança: novo módulo em `services/collab_monitor/`
  para a classificação, `find_or_create_monitor_lead()` (categoria inicial),
  frontend (`KanbanBoard.tsx`/`LeadsContext.tsx` já suportam mover
  leads entre colunas, mas a UI pode precisar sinalizar "movido pela IA").

---

## Próximo passo

Plan Mode: diagnóstico completo (já existe / o que construir / riscos) antes
de qualquer código, seguindo
[`_guia-documentar-implementacao.md`](_guia-documentar-implementacao.md).
