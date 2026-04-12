"""
Detetor de idioma heurístico para mensagens WhatsApp inbound.
Suporta: pt (Português), en (English), es (Español).
Devolve None se a confiança for baixa.
"""
import re
from typing import Optional

_PT_MARKERS = {
    "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite",
    "obrigado", "obrigada", "obrigados", "quero", "preciso", "gostaria",
    "quanto", "valor", "preço", "preco", "como", "onde", "quando",
    "não", "nao", "sim", "você", "voce", "tudo bem", "tudo certo",
    "pode", "consegue", "adorei", "perfeito", "ótimo", "otimo",
    "me chamo", "meu nome", "minha", "meu", "estou", "queria",
    "boa", "bom", "oi tudo", "oi tudo bem",
}

_EN_MARKERS = {
    "hello", "hi", "good morning", "good afternoon", "good evening",
    "thanks", "thank you", "i want", "i need", "i would like", "i'd like",
    "how much", "price", "where", "when", "can you", "please",
    "yes", "no", "okay", "ok", "what", "hey", "dear",
    "i am", "my name", "i'm", "looking for", "interested",
}

_ES_MARKERS = {
    "hola", "buenos días", "buenas tardes", "buenas noches",
    "gracias", "quiero", "necesito", "quisiera", "me gustaría",
    "cuánto", "precio", "dónde", "cuándo", "sí", "si",
    "puedes", "por favor", "me llamo", "estoy", "busco",
    "buenas", "buen día",
}


def detect_language(text: str) -> Optional[str]:
    """
    Devolve 'pt', 'en', 'es', ou None se inconclusivo.
    Estratégia: contagem ponderada de palavras/expressões marcadoras.
    """
    if not text or len(text.strip()) < 3:
        return None

    normalized = text.lower().strip()
    clean = re.sub(r"[^\w\s]", " ", normalized)
    words = clean.split()
    full = clean

    def _score(markers: set) -> int:
        score = 0
        for marker in markers:
            if " " in marker:
                if marker in full:
                    score += 2
            elif marker in words:
                score += 1
        return score

    pt = _score(_PT_MARKERS)
    en = _score(_EN_MARKERS)
    es = _score(_ES_MARKERS)

    best = max(pt, en, es)
    if best == 0:
        return None

    scores = sorted([pt, en, es], reverse=True)
    # Requer vantagem clara sobre o segundo melhor
    if scores[0] - scores[1] < 1:
        return None

    if best == pt:
        return "pt"
    if best == en:
        return "en"
    return "es"
