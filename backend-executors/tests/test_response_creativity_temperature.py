"""Temperatura da Filha (ai_profile.response_creativity) e orientação "seguir à risca"
(bloco orientacao com strict=True). Ver docs/architecture/llm-architecture.md e
docs/architecture/sales-flow.md."""

from app.services import llm_service
from app.services.decision_engine import _evaluate_sales_flow_phases


def _cfg(name: str) -> llm_service._ProviderConfig:
    return llm_service._ProviderConfig(name=name, api_base="http://x", api_key="k", model="m")


# ── Payload ───────────────────────────────────────────────────────────────────────────


def test_payload_without_temperature_has_no_key_both_providers():
    for provider in (llm_service.PROVIDER_OPENAI, llm_service.PROVIDER_OPENROUTER):
        payload = llm_service._build_payload(_cfg(provider), "p", json_mode=True)
        assert "temperature" not in payload


def test_payload_with_temperature_both_providers():
    for provider in (llm_service.PROVIDER_OPENAI, llm_service.PROVIDER_OPENROUTER):
        payload = llm_service._build_payload(_cfg(provider), "p", json_mode=True, temperature=0.2)
        assert payload["temperature"] == 0.2


# ── Resolução do nível ────────────────────────────────────────────────────────────────


def test_resolve_levels():
    assert llm_service.resolve_child_temperature({"response_creativity": "creative"}) == 0.9
    assert llm_service.resolve_child_temperature({"response_creativity": "balanced"}) == 0.5
    assert llm_service.resolve_child_temperature({"response_creativity": "strict"}) == 0.2


def test_resolve_default_and_unknown_is_none():
    assert llm_service.resolve_child_temperature(None) is None
    assert llm_service.resolve_child_temperature({}) is None
    assert llm_service.resolve_child_temperature({"response_creativity": None}) is None
    assert llm_service.resolve_child_temperature({"response_creativity": "xyz"}) is None


def test_override_wins_over_profile_level():
    profile = {"response_creativity": "creative"}
    assert llm_service.resolve_child_temperature(profile, 0.2) == 0.2


def test_generate_child_result_sends_profile_temperature(monkeypatch):
    sent = {}

    def _fake_post(payload, *, api_base, api_key):
        sent.update(payload)
        return {"output_text": "{}"}

    monkeypatch.setattr(llm_service.settings, "llm_api_key", "k")
    monkeypatch.setattr(llm_service, "_post_with_retry", _fake_post)
    monkeypatch.setattr(llm_service, "_extract_output_text", lambda cfg, payload: "{}")

    llm_service.generate_child_result("recepcao", "p", ai_profile={"response_creativity": "balanced"})
    assert sent["temperature"] == 0.5

    sent.clear()
    llm_service.generate_child_result("recepcao", "p", ai_profile={})
    assert "temperature" not in sent


# ── Orientação estrita no Fluxo de Venda ─────────────────────────────────────────────


def _context(sales_flow: dict, phases_triggered: str = "[]") -> dict:
    return {
        "lead": {
            "category": "qualification",
            "triggers_fired": "[]",
            "branches_selected": "{}",
            "phases_triggered": phases_triggered,
        },
        "ai_profile": {"agent_mode": "agenda", "sales_flow": sales_flow},
    }


def _p0_flow(strict: bool, priority: str = "normal") -> dict:
    return {
        "enabled": True,
        "phases": [{
            "id": "p0",
            "blocks": [
                {"id": "pt", "typeId": "phase_trigger"},
                {
                    "id": "or-1", "typeId": "orientacao", "priority": priority,
                    "content": "Pergunte qual terapeuta: Val ou Daniel", "strict": strict,
                },
            ],
        }],
    }


def test_strict_orientation_sets_flag_and_literal_label():
    result = _evaluate_sales_flow_phases(
        _context(_p0_flow(strict=True)), effective_route_to="recepcao",
        message_text="ola", is_phase_entry=True,
    )
    assert result.get("strict_active") is True
    injections = "\n".join(result["prompt_injections"])
    assert "SEGUIR À RISCA" in injections
    assert "Pergunte qual terapeuta: Val ou Daniel" in injections


def test_normal_orientation_keeps_old_label_and_no_flag():
    result = _evaluate_sales_flow_phases(
        _context(_p0_flow(strict=False)), effective_route_to="recepcao",
        message_text="ola", is_phase_entry=True,
    )
    assert not result.get("strict_active")
    injections = "\n".join(result["prompt_injections"])
    assert "SEGUIR À RISCA" not in injections
    assert "INSTRUÇÃO DE FLUXO DE VENDA:\nPergunte qual terapeuta" in injections


def test_strict_orientation_not_active_when_trigger_did_not_fire():
    """Fora da entrada da fase o phase_trigger não dispara — a orientação não entra no
    prompt, então a temperatura do turno não deve baixar."""
    result = _evaluate_sales_flow_phases(
        _context(_p0_flow(strict=True)), effective_route_to="recepcao",
        message_text="ola", is_phase_entry=False,
    )
    assert not result.get("strict_active")


def test_strict_critical_permanent_reinjection_uses_normal_label():
    """Reinjeção permanente de orientação crítica (segunda passagem) não é literal —
    senão a Filha repetiria a mesma frase em todo turno da fase."""
    result = _evaluate_sales_flow_phases(
        _context(_p0_flow(strict=True, priority="critical"), phases_triggered='["p0"]'),
        effective_route_to="recepcao", message_text="ola", is_phase_entry=False,
    )
    assert not result.get("strict_active")
    injections = "\n".join(result["prompt_injections"])
    assert "em vigor nesta etapa" in injections
    assert "SEGUIR À RISCA" not in injections


def test_strict_orientation_in_unchosen_branch_not_active():
    sales_flow = {
        "enabled": True,
        "phases": [{
            "id": "p2",
            "blocks": [
                {"id": "pt", "typeId": "phase_trigger"},
                {
                    "id": "cond", "typeId": "condicao",
                    "branches": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                },
                {
                    "id": "or-a", "typeId": "orientacao", "content": "texto A", "strict": True,
                    "branch_group_id": "cond", "branch_id": "a",
                },
                {
                    "id": "or-b", "typeId": "orientacao", "content": "texto B",
                    "branch_group_id": "cond", "branch_id": "b",
                },
            ],
        }],
    }
    result = _evaluate_sales_flow_phases(
        _context(sales_flow), effective_route_to="apresentation", message_text="nao",
        is_phase_entry=True, branch_selections={"cond": "b"},
    )
    assert not result.get("strict_active")
    assert "texto A" not in "\n".join(result["prompt_injections"])
