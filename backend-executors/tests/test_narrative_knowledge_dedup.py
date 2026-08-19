"""Dedup de knowledge narrativo (social_proof / pitch_script / product_details): essas
categorias devem aparecer no prompt da filha no máximo 1x por lead — reproduz o bug real
observado em teste manual: social_proof repetindo em 3 turnos seguidos da fase apresentation,
mesmo com instrução "usar apenas quando o lead demonstrar hesitação" (soft, sem estado).

Categorias reativas/FAQ (objections_faq, service_faq, guarantee_policy,
service_pricing_table, commercial_objections, service_differentials, active_promotion,
payment_policy, pre_commitment_faq) NUNCA passam por este mecanismo — continuam disponíveis
em todo turno, já que são condicionadas a "usar apenas se o lead perguntar X" e o lead pode
perguntar a qualquer momento (ver test_apresentation_ondemand_commercial_knowledge.py)."""

import json

from app.services.decision_engine import (
    _build_child_prompt_apresentation,
    _build_child_prompt_follow_up,
    _evaluate_narrative_knowledge_dedup,
    compose_decision_output,
)
from app.services.orchestrator_models import ChildResult, MotherDecision

_SOCIAL = "Trabalhei com mais de 50 clientes da área de massoterapia."
_PITCH = "1. Apresente o problema. 2. Mostre a solução. 3. Feche com CTA."
_PRODUCT = "Sessão inclui óleos essenciais e ambiente climatizado."


# ---------- 1. função pura (unit, sem prompt/MotherDecision) ----------

def test_dedup_new_category_appears_and_is_marked_new():
    context = {"lead": {"knowledge_categories_shown": "[]"}}
    knowledge_items = {"social_proof": _SOCIAL}

    result = _evaluate_narrative_knowledge_dedup(context, "apresentation", knowledge_items)

    assert result["content"]["social_proof"] == _SOCIAL
    assert result["new_categories"] == ["social_proof"]
    assert result["suppressed_categories"] == []


def test_dedup_already_shown_category_is_omitted():
    context = {"lead": {"knowledge_categories_shown": '["social_proof"]'}}
    knowledge_items = {"social_proof": _SOCIAL}

    result = _evaluate_narrative_knowledge_dedup(context, "apresentation", knowledge_items)

    assert result["content"]["social_proof"] is None
    assert result["new_categories"] == []
    assert result["suppressed_categories"] == ["social_proof"]


def test_dedup_covers_all_three_apresentation_categories_independently():
    context = {"lead": {"knowledge_categories_shown": '["pitch_script"]'}}
    knowledge_items = {
        "social_proof": _SOCIAL,
        "pitch_script": _PITCH,
        "product_details": _PRODUCT,
    }

    result = _evaluate_narrative_knowledge_dedup(context, "apresentation", knowledge_items)

    assert result["content"]["social_proof"] == _SOCIAL
    assert result["content"]["pitch_script"] is None
    assert result["content"]["product_details"] == _PRODUCT
    assert set(result["new_categories"]) == {"social_proof", "product_details"}
    assert result["suppressed_categories"] == ["pitch_script"]


def test_dedup_follow_up_only_covers_social_proof():
    context = {"lead": {"knowledge_categories_shown": "[]"}}
    knowledge_items = {"social_proof": _SOCIAL, "pitch_script": _PITCH}

    result = _evaluate_narrative_knowledge_dedup(context, "follow-up", knowledge_items)

    # pitch_script não é candidato em follow-up — nem aparece no dict de conteúdo.
    assert "pitch_script" not in result["content"]
    assert result["content"]["social_proof"] == _SOCIAL


def test_dedup_reactive_faq_categories_are_never_touched():
    """objections_faq nem é candidato deste mecanismo — mesmo com o mesmo nome presente
    em knowledge_categories_shown (o que este mecanismo nunca escreveria sozinho), a
    categoria não é afetada porque nunca é avaliada por _evaluate_narrative_knowledge_dedup."""
    context = {"lead": {"knowledge_categories_shown": '["objections_faq"]'}}
    knowledge_items = {"objections_faq": "Resposta padrão de objeção de preço."}

    result = _evaluate_narrative_knowledge_dedup(context, "apresentation", knowledge_items)

    assert result["content"] == {"social_proof": None, "pitch_script": None, "product_details": None}
    assert "objections_faq" not in result["content"]


def test_dedup_unknown_phase_returns_empty():
    context = {"lead": {"knowledge_categories_shown": "[]"}}
    result = _evaluate_narrative_knowledge_dedup(context, "qualification", {"social_proof": _SOCIAL})
    assert result == {"content": {}, "new_categories": [], "suppressed_categories": []}


def test_dedup_malformed_json_falls_back_to_empty_shown_set():
    context = {"lead": {"knowledge_categories_shown": "{not valid json"}}
    result = _evaluate_narrative_knowledge_dedup(context, "apresentation", {"social_proof": _SOCIAL})
    assert result["content"]["social_proof"] == _SOCIAL


def test_dedup_missing_category_content_is_none_and_not_new():
    context = {"lead": {"knowledge_categories_shown": "[]"}}
    result = _evaluate_narrative_knowledge_dedup(context, "apresentation", {})
    assert result["content"] == {"social_proof": None, "pitch_script": None, "product_details": None}
    assert result["new_categories"] == []
    assert result["suppressed_categories"] == []


# ---------- 2. integração com o prompt da apresentação ----------

def _apres_context(shown="[]"):
    return {
        "lead": {"id": 1, "category": "apresentation", "knowledge_categories_shown": shown},
        "ai_profile": {"agent_mode": "agenda", "template_key": "sdr_padrao"},
        "playbook": {"template_key": "sdr_padrao"},
        "metadata": {"inbound_message_text": "me fala mais sobre o serviço"},
        "history": [{"model": "outbound", "text": "Oi!"}, {"model": "inbound", "text": "oi"}],
        "knowledge_items": {"social_proof": _SOCIAL, "pitch_script": _PITCH},
        "knowledge_media": {},
        "lead_detected_language": "pt",
    }


def _mother_apres():
    return MotherDecision(
        route_to="apresentation", perceived_category="apresentation",
        confidence=0.9, reason="turno de apresentação",
    )


def test_apresentation_prompt_includes_social_proof_first_turn():
    prompt = _build_child_prompt_apresentation(_apres_context(), "oi", _mother_apres())
    assert _SOCIAL in prompt


def test_apresentation_prompt_omits_social_proof_after_shown():
    prompt = _build_child_prompt_apresentation(
        _apres_context(shown='["social_proof"]'), "oi", _mother_apres()
    )
    assert _SOCIAL not in prompt
    assert _PITCH in prompt  # pitch_script continua novo, não afetado


def test_apresentation_prompt_keeps_reactive_faq_regardless_of_shown_state():
    context = _apres_context(shown='["social_proof", "pitch_script"]')
    context["knowledge_items"]["objections_faq"] = "Resposta X de objeção."
    prompt = _build_child_prompt_apresentation(context, "oi", _mother_apres())
    assert "Resposta X de objeção." in prompt


# ---------- 3. integração com o prompt de follow-up ----------

def test_followup_prompt_omits_social_proof_after_shown():
    context = {
        "lead": {"id": 1, "category": "follow-up", "knowledge_categories_shown": '["social_proof"]'},
        "ai_profile": {"agent_mode": "agenda"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi"},
        "history": [],
        "knowledge_items": {"social_proof": _SOCIAL, "objections_faq": "resposta X"},
        "knowledge_media": {},
        "lead_detected_language": "pt",
    }
    mother = MotherDecision(
        route_to="follow-up", perceived_category="follow-up",
        confidence=0.9, reason="turno de follow-up",
    )
    prompt = _build_child_prompt_follow_up(context, "oi", mother)
    assert _SOCIAL not in prompt
    assert "resposta X" in prompt  # FAQ reativo continua disponível


def test_followup_prompt_includes_social_proof_first_turn():
    context = {
        "lead": {"id": 1, "category": "follow-up", "knowledge_categories_shown": "[]"},
        "ai_profile": {"agent_mode": "agenda"},
        "playbook": {},
        "metadata": {"inbound_message_text": "oi"},
        "history": [],
        "knowledge_items": {"social_proof": _SOCIAL},
        "knowledge_media": {},
        "lead_detected_language": "pt",
    }
    mother = MotherDecision(
        route_to="follow-up", perceived_category="follow-up",
        confidence=0.9, reason="turno de follow-up",
    )
    prompt = _build_child_prompt_follow_up(context, "oi", mother)
    assert _SOCIAL in prompt


# ---------- 4. system_action mark_knowledge_shown (compose_decision_output) ----------

def _child_result():
    return ChildResult(message_text="Olá! Deixa te contar...", confidence=0.9)


def test_compose_decision_output_emits_mark_knowledge_shown_for_new_categories():
    context = _apres_context()

    decision = compose_decision_output(
        context=context,
        mother_decision=_mother_apres(),
        child_result=_child_result(),
    )

    actions = [a for a in (decision.system_actions or []) if a["type"] == "mark_knowledge_shown"]
    assert len(actions) == 1
    assert set(actions[0]["categories"]) == {"social_proof", "pitch_script"}


def test_compose_decision_output_no_action_when_nothing_new():
    context = _apres_context(shown='["social_proof", "pitch_script"]')

    decision = compose_decision_output(
        context=context,
        mother_decision=_mother_apres(),
        child_result=_child_result(),
    )

    actions = [a for a in (decision.system_actions or []) if a["type"] == "mark_knowledge_shown"]
    assert actions == []


def test_compose_decision_output_no_action_outside_apresentation_or_followup():
    context = {
        "lead": {"category": "closing", "knowledge_categories_shown": "[]"},
        "ai_profile": {"agent_mode": "agenda"},
        "playbook": {},
        "metadata": {"inbound_message_text": "fechado"},
        "history": [],
        "knowledge_items": {"social_proof": _SOCIAL},
        "knowledge_media": {},
        "lead_detected_language": "pt",
    }
    mother = MotherDecision(
        route_to="closing", perceived_category="closing", confidence=0.9, reason="fechamento",
    )

    decision = compose_decision_output(
        context=context, mother_decision=mother, child_result=_child_result(),
    )

    actions = [a for a in (decision.system_actions or []) if a["type"] == "mark_knowledge_shown"]
    assert actions == []
