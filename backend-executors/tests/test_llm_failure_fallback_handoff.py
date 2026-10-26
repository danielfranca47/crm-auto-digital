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


def _disable_bot_context(llm_failure_final):
    context = _context(history=[])
    context["lead"] = {"category": "recepcao", "id": 7, "user_id": 3}
    context["job"] = {"id": 11}
    context["ai_profile"] = {**context["ai_profile"], "handoff_policy": "disable_bot"}
    if llm_failure_final is not None:
        context["llm_failure_final"] = llm_failure_final
    return context


def _record_handoff_side_effects(monkeypatch):
    calls = []
    monkeypatch.setattr(
        decision_engine.handoff_policy.crm_client,
        "set_lead_bot_disabled",
        lambda *args, **kwargs: calls.append("set_lead_bot_disabled"),
    )
    monkeypatch.setattr(
        decision_engine.handoff_policy.crm_client,
        "log_handoff_requested",
        lambda *args, **kwargs: calls.append("log_handoff_requested"),
    )
    return calls


def test_llm_failure_on_non_final_job_attempt_defers_handoff(monkeypatch):
    """Worker vai repetir o job: o bot não pode ficar desligado por uma falha passageira."""
    monkeypatch.setattr(decision_engine.llm_service, "generate_mother_route", _raise_llm_error)
    calls = _record_handoff_side_effects(monkeypatch)

    result = decision_engine.decide(_disable_bot_context(llm_failure_final=False), logger=None)

    assert result.reason == "llm_failure"
    assert result.message_text == ""
    assert calls == []


def test_llm_failure_on_final_job_attempt_applies_handoff(monkeypatch):
    monkeypatch.setattr(decision_engine.llm_service, "generate_mother_route", _raise_llm_error)
    calls = _record_handoff_side_effects(monkeypatch)

    result = decision_engine.decide(_disable_bot_context(llm_failure_final=True), logger=None)

    assert result.next_action == "handoff"
    assert result.message_text
    assert calls == ["set_lead_bot_disabled", "log_handoff_requested"]


def test_llm_failure_without_job_signal_applies_handoff(monkeypatch):
    """Playground não passa o sinal: handoff imediato, como antes."""
    monkeypatch.setattr(decision_engine.llm_service, "generate_mother_route", _raise_llm_error)
    calls = _record_handoff_side_effects(monkeypatch)

    result = decision_engine.decide(_disable_bot_context(llm_failure_final=None), logger=None)

    assert result.next_action == "handoff"
    assert calls == ["set_lead_bot_disabled", "log_handoff_requested"]


def test_runner_marks_only_last_job_attempt_as_final():
    from app.runners import whatsapp

    assert whatsapp._llm_failure_will_retry(None) is True
    assert whatsapp._llm_failure_will_retry(1) is True
    assert whatsapp._llm_failure_will_retry(whatsapp.JOB_MAX_ATTEMPTS - 1) is True
    assert whatsapp._llm_failure_will_retry(whatsapp.JOB_MAX_ATTEMPTS) is False


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
