"""Pacote de serviços auxiliares do backend.

Evita imports pesados no import do pacote para não acoplar módulos opcionais em tempo de carga.
"""

import importlib

__all__ = ["jobs_service"]


def __getattr__(name: str):
    if name == "jobs_service":
        module = importlib.import_module(".jobs_service", __name__)
        globals()[name] = module
        return module
    raise AttributeError(name)
