import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydantic import ValidationError

from app.services.orchestrator_models import MotherDecision

_BASE_PAYLOAD = {"confidence": 0.9, "reason": "test"}


def main() -> None:
    # Alias já existente (typo recorrente: falta o "a-" de "apresentation")
    decision = MotherDecision.model_validate({**_BASE_PAYLOAD, "route_to": "presentation"})
    assert decision.route_to == "apresentation"

    # Alias novo: grafia PT sem cedilha (achado ao vivo em 23/08/2026)
    decision = MotherDecision.model_validate({**_BASE_PAYLOAD, "route_to": "qualificacao"})
    assert decision.route_to == "qualification"

    # Valor realmente desconhecido continua a falhar alto (comportamento preservado)
    try:
        MotherDecision.model_validate({**_BASE_PAYLOAD, "route_to": "foobar"})
        raise AssertionError("esperava ValidationError para route_to desconhecido")
    except ValidationError:
        pass

    print("OK: aliases de route_to normalizados; valor desconhecido ainda levanta ValidationError")


if __name__ == "__main__":
    main()
