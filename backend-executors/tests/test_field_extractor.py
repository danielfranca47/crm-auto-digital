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


def _context(qualification_fields=None):
    return {
        "metadata": {"inbound_message_text": "mensagem de teste"},
        "history": [],
        "ai_profile": {
            "niche": "",
            "target_audience": "",
            "qualification_fields": qualification_fields or [],
        },
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
