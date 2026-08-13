import json

from app.services import field_extractor


def _mock_llm(monkeypatch, extracted, confidence, evidence=None):
    payload = {
        "extracted": extracted,
        "confidence": confidence,
        "evidence": evidence or {},
    }
    monkeypatch.setattr(
        field_extractor.llm_service,
        "generate_decision_text",
        lambda _prompt: json.dumps(payload, ensure_ascii=False),
    )


def _context(qualification_fields=None, tolerance=None):
    ai_profile = {
        "niche": "",
        "target_audience": "",
        "qualification_fields": qualification_fields or [],
    }
    if tolerance is not None:
        ai_profile["qualification_extraction_tolerance"] = tolerance
    return {
        "metadata": {"inbound_message_text": "mensagem de teste"},
        "history": [],
        "ai_profile": ai_profile,
        "qualification_state": {"exists": True, "data_json": {}},
    }


def test_low_confidence_profile_field_is_filtered_out(monkeypatch):
    """Campo do perfil (fields_schema) com confidence abaixo de 0.4 não deve
    contar como preenchido — o gap que causava a alucinação do extractor."""
    _mock_llm(
        monkeypatch,
        extracted={"custom_pergunta_de_endereco": "orcamento detalhado"},
        confidence={"custom_pergunta_de_endereco": 0.2},
    )
    result = field_extractor.extract_fields_llm(
        _context(), {"custom_pergunta_de_endereco": "string|null"}
    )
    assert result["extracted"] == {}
    # confidence/evidence continuam intactos para observabilidade, mesmo filtrado.
    assert result["confidence"]["custom_pergunta_de_endereco"] == 0.2


def test_high_confidence_profile_field_is_kept(monkeypatch):
    _mock_llm(
        monkeypatch,
        extracted={"custom_uso_do_produto": "hospedagem de temporada"},
        confidence={"custom_uso_do_produto": 0.7},
    )
    result = field_extractor.extract_fields_llm(
        _context(), {"custom_uso_do_produto": "string|null"}
    )
    assert result["extracted"] == {"custom_uso_do_produto": "hospedagem de temporada"}


def test_missing_confidence_entry_is_filtered_out_fail_closed(monkeypatch):
    """Se a LLM extrai um valor mas não devolve confidence pra essa chave,
    trata como reprovado em vez de aceitar por omissão."""
    _mock_llm(
        monkeypatch,
        extracted={"custom_uso_do_produto": "uso diario"},
        confidence={},
    )
    result = field_extractor.extract_fields_llm(
        _context(), {"custom_uso_do_produto": "string|null"}
    )
    assert result["extracted"] == {}


def test_default_context_field_uses_higher_threshold(monkeypatch):
    """Campo de contexto padrão (fora do fields_schema recebido) usa o
    limiar 0.6, não o 0.4 dos campos configurados no perfil."""
    _mock_llm(
        monkeypatch,
        extracted={
            "service_interest": "abaixo do limiar",
            "urgency": "acima do limiar",
        },
        confidence={"service_interest": 0.5, "urgency": 0.6},
    )
    # fields_schema só tem o campo custom — service_interest/urgency vêm do
    # DEFAULT_FIELD_SCHEMA, não do que o perfil configurou.
    result = field_extractor.extract_fields_llm(
        _context(), {"custom_uso_do_produto": "string|null"}
    )
    assert "service_interest" not in result["extracted"]
    assert result["extracted"]["urgency"] == "acima do limiar"


def test_field_question_is_included_in_prompt(monkeypatch):
    """A pergunta configurada do campo (não só a key) deve chegar no prompt
    enviado à LLM — sem isso, a LLM só vê o nome da chave."""
    captured_prompt = {}

    def _fake_generate(prompt):
        captured_prompt["value"] = prompt
        return json.dumps({"extracted": {}, "confidence": {}, "evidence": {}})

    monkeypatch.setattr(field_extractor.llm_service, "generate_decision_text", _fake_generate)

    context = _context(
        qualification_fields=[
            {
                "key": "custom_pergunta_de_endereco",
                "label": "Endereco",
                "question": "Qual o endereco de entrega?",
                "mode": "required",
            }
        ]
    )
    field_extractor.extract_fields_llm(context, {"custom_pergunta_de_endereco": "string|null"})

    assert "Qual o endereco de entrega?" in captured_prompt["value"]


def test_missing_tolerance_defaults_to_equilibrado(monkeypatch):
    """Perfil sem qualification_extraction_tolerance configurado (caso de todo
    perfil existente antes desta fase) deve manter o comportamento 0.4/0.6 já
    validado em produção — sem regressão para quem não escolher outro nível."""
    _mock_llm(
        monkeypatch,
        extracted={"custom_uso_do_produto": "resposta ok"},
        confidence={"custom_uso_do_produto": 0.4},
    )
    result = field_extractor.extract_fields_llm(
        _context(), {"custom_uso_do_produto": "string|null"}
    )
    assert result["extracted"] == {"custom_uso_do_produto": "resposta ok"}


def test_invalid_tolerance_value_falls_back_to_equilibrado(monkeypatch):
    """Valor inesperado (perfil corrompido ou de uma versão futura) não deve
    quebrar o extractor — cai no default seguro em vez de propagar KeyError."""
    _mock_llm(
        monkeypatch,
        extracted={"custom_uso_do_produto": "resposta ok"},
        confidence={"custom_uso_do_produto": 0.3},
    )
    result = field_extractor.extract_fields_llm(
        _context(tolerance="valor_invalido"), {"custom_uso_do_produto": "string|null"}
    )
    assert result["extracted"] == {}


def test_flexivel_tolerance_accepts_lower_confidence(monkeypatch):
    """Tolerância 'flexivel' baixa o limiar do campo do perfil — uma confidence
    que seria reprovada em 'equilibrado' (0.4) passa a ser aceita."""
    _mock_llm(
        monkeypatch,
        extracted={"custom_uso_do_produto": "resposta informal"},
        confidence={"custom_uso_do_produto": 0.3},
    )
    result = field_extractor.extract_fields_llm(
        _context(tolerance="flexivel"), {"custom_uso_do_produto": "string|null"}
    )
    assert result["extracted"] == {"custom_uso_do_produto": "resposta informal"}


def test_rigoroso_tolerance_rejects_confidence_that_equilibrado_accepts(monkeypatch):
    """Tolerância 'rigoroso' sobe o limiar do campo do perfil — uma confidence
    que seria aceita em 'equilibrado' (0.4) passa a ser reprovada."""
    _mock_llm(
        monkeypatch,
        extracted={"custom_uso_do_produto": "resposta ambigua"},
        confidence={"custom_uso_do_produto": 0.5},
    )
    result = field_extractor.extract_fields_llm(
        _context(tolerance="rigoroso"), {"custom_uso_do_produto": "string|null"}
    )
    assert result["extracted"] == {}


def test_flexivel_tolerance_loosens_closed_enum_schema(monkeypatch):
    """No nível 'flexivel', enums fechados do DEFAULT_FIELD_SCHEMA (ex.: decision_role)
    viram 'string|null' no schema enviado à LLM — não travam a extração ao vocabulário
    exato do enum."""
    captured_prompt = {}

    def _fake_generate(prompt):
        captured_prompt["value"] = prompt
        return json.dumps({"extracted": {}, "confidence": {}, "evidence": {}})

    monkeypatch.setattr(field_extractor.llm_service, "generate_decision_text", _fake_generate)

    field_extractor.extract_fields_llm(_context(tolerance="flexivel"), {})

    assert '"decision_role": "string|null"' in captured_prompt["value"]
    assert "owner|partner|employee" not in captured_prompt["value"]


def test_equilibrado_tolerance_keeps_closed_enum_schema(monkeypatch):
    """Fora do nível 'flexivel', o schema de enums fechados permanece intacto —
    só 'flexivel' afrouxa o vocabulário aceito."""
    captured_prompt = {}

    def _fake_generate(prompt):
        captured_prompt["value"] = prompt
        return json.dumps({"extracted": {}, "confidence": {}, "evidence": {}})

    monkeypatch.setattr(field_extractor.llm_service, "generate_decision_text", _fake_generate)

    field_extractor.extract_fields_llm(_context(), {})

    assert "owner|partner|employee|other|null" in captured_prompt["value"]
