# automations/assistente_ia/i18n.py
from typing import Optional

_MAP = {
    "pt": "pt-PT",
    "pt-pt": "pt-PT",
    "português": "pt-PT",
    "portugues": "pt-PT",
    "português de portugal": "pt-PT",
    "portugues de portugal": "pt-PT",
    "português portugal": "pt-PT",

    "pt-br": "pt-BR",
    "português do brasil": "pt-BR",
    "portugues do brasil": "pt-BR",
    "brasileiro": "pt-BR",

    "en": "en",
    "english": "en",
    "inglês": "en",
    "ingles": "en",

    "es": "es",
    "espanhol": "es",
    "español": "es",
    "castelhano": "es",
}

def normalize_language(lang: Optional[str]) -> Optional[str]:
    if not lang:
        return None
    key = str(lang).strip().lower()
    return _MAP.get(key, lang)
