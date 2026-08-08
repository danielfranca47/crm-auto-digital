"""Garante que uma falha da LLM Mae (erro de rede/API/parsing) sempre resulta em
handoff (mensagem de handoff + notificacao/pausa conforme a politica), mesmo
quando a falha acontece nos primeiros turnos de uma conversa nova. Antes desta
mudanca, esse caso especifico (historico <= 2) retornava next_action="ignore"
com mensagem vazia, sem passar por handoff_policy.apply() -- o lead ficava sem
nenhuma resposta e ninguem era avisado.

Ver docs/implementations/fix-handoff-silencio-primeira-mensagem.md."""

from app.services import decision_engine


def _context(history):
    return {
        "lead": {"category": "recepcao"},
        "ai_profile": {"agent_mode": "agenda", "template_key": "hybrid_scheduler"},
        "playbook": {"template_key": "hybrid_scheduler"},
        "metadata": {"inbound_message_text": "Quero falar com a profissional diretamente"},
        "job": {},
        "history": history,
        "knowledge_items": {},
        "knowledge_media": {},
        "lead_detected_language": "pt",
    }


def _raise_llm_error(*_args, **_kwargs):
    raise RuntimeError("llm boom")


def test_llm_failure_short_history_goes_to_handoff(monkeypatch):
    monkeypatch.setattr(decision_engine.llm_service, "generate_mother_route", _raise_llm_error)
    context = _context(history=[])

    result = decision_engine.decide(context, logger=None)

    assert result.next_action == "handoff"
    assert result.message_text


def test_llm_failure_normal_history_still_goes_to_handoff(monkeypatch):
    monkeypatch.setattr(decision_engine.llm_service, "generate_mother_route", _raise_llm_error)
    context = _context(
        history=[
            {"model": "outbound", "text": "Oi! Seja bem-vindo(a)."},
            {"model": "inbound", "text": "Oi"},
            {"model": "outbound", "text": "Como posso ajudar?"},
            {"model": "inbound", "text": "Quero falar com a profissional diretamente"},
        ]
    )

    result = decision_engine.decide(context, logger=None)

    assert result.next_action == "handoff"
    assert result.message_text
