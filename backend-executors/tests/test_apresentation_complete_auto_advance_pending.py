"""Fase 2 de sales-flow-fase-pendente-guardrail.md — fecha o buraco em que
`apresentation_complete_auto_advance` (compose_decision_output) avançava `suggested_category`
para além de p2 usando só o sinal `did_complete_phase` da Filha, sem consultar gatilhos
sequenciais pendentes em p2 — contornando silenciosamente `_enforce_apresentation_sales_flow_pending`,
que já protege o `route_to` da Mãe mas não este caminho. Ver decision_engine.py:
_phase_pending_sequential_triggers() e o gate em compose_decision_output()."""
from app.services import decision_engine


def _sales_flow_p2_pending() -> dict:
    return {
        "enabled": True,
        "phases": [
            {
                "id": "p2",
                "blocks": [
                    {
                        "id": "kw2",
                        "typeId": "kw_trigger",
                        "keywords": "detalhes tecnicos",
                        "fire_once": True,
                    }
                ],
            }
        ],
    }


def _context(*, triggers_fired: str, sales_flow: dict) -> dict:
    return {
        "lead": {"id": 20, "user_id": 99, "category": "apresentation", "triggers_fired": triggers_fired},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler", "sales_flow": sales_flow},
        "playbook": {},
        "metadata": {"inbound_message_text": "quero saber mais"},
        "history": [{"model": "outbound", "text": "Aqui está a apresentação do serviço."}],
    }


def _mock_mother(monkeypatch):
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_mother_route",
        lambda _p, **_kwargs: (
            '{"route_to":"apresentation","perceived_category":"apresentation",'
            '"confidence":0.9,"reason":"teste"}'
        ),
    )


def _mock_child_completes_phase(monkeypatch, *, recommended: str = "pre-agendamento"):
    monkeypatch.setattr(
        decision_engine.llm_service,
        "generate_child_result",
        lambda _route, _prompt, **_kwargs: (
            '{"message_text":"Combinado, vamos marcar um horário.","did_complete_phase":true,'
            f'"recommended_next_category":"{recommended}","outcome":null,'
            '"kanban_highlight":null,"signals":[],"confidence":0.8}'
        ),
    )


def test_p2_pending_trigger_blocks_apresentation_complete_auto_advance(monkeypatch):
    context = _context(triggers_fired="[]", sales_flow=_sales_flow_p2_pending())
    _mock_mother(monkeypatch)
    _mock_child_completes_phase(monkeypatch)

    decision = decision_engine.decide(context)

    assert decision.suggested_category == "apresentation"


def test_p2_trigger_already_fired_advances_normally(monkeypatch):
    context = _context(triggers_fired='["kw2"]', sales_flow=_sales_flow_p2_pending())
    _mock_mother(monkeypatch)
    _mock_child_completes_phase(monkeypatch)

    decision = decision_engine.decide(context)

    assert decision.suggested_category == "pre-agendamento"


def test_no_sequential_trigger_in_p2_behaves_like_baseline(monkeypatch):
    context = _context(
        triggers_fired="[]",
        sales_flow={"enabled": True, "phases": [{"id": "p2", "blocks": []}]},
    )
    _mock_mother(monkeypatch)
    _mock_child_completes_phase(monkeypatch)

    decision = decision_engine.decide(context)

    assert decision.suggested_category == "pre-agendamento"
