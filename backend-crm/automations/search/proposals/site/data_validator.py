# modules/data_validator.py
import re
import unicodedata
from typing import List, Dict, Tuple
from urllib.parse import urlparse

def _strip_accents(s: str) -> str:
    try:
        return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    except Exception:
        return s

def _only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def _domain(url: str) -> str:
    if not url:
        return ""
    try:
        u = urlparse(url if "://" in url else "http://" + url)
        host = (u.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""

def _safe_float(x):
    try:
        return float(x)
    except Exception:
        return 0.0

def _safe_int(x):
    try:
        return int(x)
    except Exception:
        return 0

def _norm_name(s: str) -> str:
    s = _strip_accents((s or "").strip().lower())
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s

def _norm_addr(s: str) -> str:
    s = _strip_accents((s or "").strip().lower())
    s = re.sub(r"\s{2,}", " ", s)
    return s

def _score(item: Dict) -> float:
    has_site = 2.0 if item.get("website") else 0.0
    has_phone = 1.0 if item.get("phone") else 0.0
    return has_site + has_phone + _safe_int(item.get("reviews_count")) * 0.001 + _safe_float(item.get("rating")) * 0.1

def validate(items: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    Deduplica por telefone normalizado, domínio do site ou nome+endereço.
    Mantém o melhor registro (score). Retorna (lista_limpa, relatorio).
    """
    cleaned: List[Dict] = []
    seen_keys = {}
    kept = 0
    dropped = 0
    reasons = {"phone": 0, "site": 0, "name_addr": 0}

    for it in items:
        it = dict(it)

        phone_norm = _only_digits(it.get("phone", ""))
        site_domain = _domain(it.get("website", ""))
        name_norm = _norm_name(it.get("name", ""))
        addr_norm = _norm_addr(it.get("address", ""))

        it["_phone_norm"] = phone_norm
        it["_site_domain"] = site_domain
        it["_name_addr_key"] = f"{name_norm}|{addr_norm}" if name_norm and addr_norm else ""

        keys = []
        if phone_norm and len(phone_norm) >= 8:
            keys.append(("phone", phone_norm))
        if site_domain:
            keys.append(("site", site_domain))
        if it["_name_addr_key"]:
            keys.append(("name_addr", it["_name_addr_key"]))

        if not keys:
            cleaned.append(it); kept += 1
            continue

        inserted = False
        for ktype, kval in keys:
            cur_best_idx = seen_keys.get((ktype, kval))
            if cur_best_idx is None:
                cleaned.append(it)
                idx = len(cleaned) - 1
                seen_keys[(ktype, kval)] = idx
                kept += 1
                inserted = True
            else:
                old = cleaned[cur_best_idx]
                if _score(it) > _score(old):
                    cleaned[cur_best_idx] = it
                dropped += 1
                reasons[ktype] += 1
                inserted = True
            if inserted:
                break

        if not inserted:
            cleaned.append(it); kept += 1

    report = {
        "input": len(items),
        "kept": kept,
        "dropped": dropped,
        "reasons": reasons,
    }
    return cleaned, report
