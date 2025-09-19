# modules/cross_validator.py
import re
import unicodedata
import difflib
from urllib.parse import urlparse
from typing import List, Dict, Tuple

def _strip_accents(s: str) -> str:
    try:
        return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    except Exception:
        return s or ""

def _norm_text(s: str) -> str:
    s = _strip_accents((s or "").strip().lower())
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s

def _only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def _domain(url: str) -> str:
    """Extrai host normalizado."""
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

def _host_label(host: str) -> str:
    # rótulo principal do domínio (antes do TLD)
    if not host:
        return ""
    parts = host.split(".")
    return parts[-2] if len(parts) >= 2 else parts[0]

def _name_similarity(name: str, website: str) -> float:
    """Similaridade do nome com o label do domínio (0..1)."""
    n = _norm_text(name)
    d = _host_label(_domain(website))
    d = _norm_text(d.replace("-", " "))
    if not n or not d:
        return 0.0
    return difflib.SequenceMatcher(None, n, d).ratio()

def _phone_match(gmaps_phone: str, phones_site: List[str], phone_site_norm: str) -> bool:
    g = _only_digits(gmaps_phone)
    if not g:
        return False
    # considera match se o site contiver o mesmo número ou o mesmo SUFIXO de 8–9 dígitos
    suffixes = [g[-8:], g[-9:]] if len(g) >= 9 else [g]
    candidates = set(_only_digits(p) for p in (phones_site or []))
    if phone_site_norm:
        candidates.add(_only_digits(phone_site_norm))
    for c in list(candidates):
        if not c:
            continue
        if c == g:
            return True
        if any(c.endswith(suf) or g.endswith(suf) for suf in suffixes):
            return True
    return False

def _token_set(s: str) -> set:
    return set(_norm_text(s).split())

def _address_match(addr_g: str, addr_s: str) -> bool:
    """Jaccard simples entre tokens; considera match se ≥ 0.35."""
    if not addr_g or not addr_s:
        return False
    A, B = _token_set(addr_g), _token_set(addr_s)
    if not A or not B:
        return False
    inter = len(A & B)
    union = len(A | B)
    j = inter / union if union else 0.0
    return j >= 0.35

def _domain_match(website: str, canonical: str) -> bool:
    d1, d2 = _domain(website), _domain(canonical)
    if not d1 or not d2:
        return False
    return d1 == d2 or d1.endswith("." + d2) or d2.endswith("." + d1)

def _trust_score(flags: Dict, name_sim: float, rating, reviews) -> int:
    """Score 0..100 com pesos simples e transparentes."""
    r = float(rating or 0.0); rv = int(reviews or 0)
    score = 0.0
    score += 40.0 if flags.get("domain_match") else 0.0
    score += 30.0 if flags.get("phone_match") else 0.0
    score += 20.0 if flags.get("address_match") else 0.0
    score += 10.0 * max(0.0, min(1.0, name_sim))   # 0..10
    score += min(10.0, (r/5.0)*10.0)               # até +10 por rating
    score += min(10.0, rv/500.0*10.0)              # até +10 por reviews (500+)
    return int(round(min(100.0, score)))

def cross_validate(items: List[Dict]) -> Tuple[List[Dict], Dict]:
    validated: List[Dict] = []
    agg = {
        "total": len(items),
        "domain_match": 0,
        "phone_match": 0,
        "address_match": 0,
        "high_trust_80+": 0,
        "no_website": 0,
    }

    for it in items:
        website     = (it.get("website") or "").strip()
        canonical   = (it.get("website_canonical") or "").strip()
        own         = bool(it.get("own_domain"))
        no_own_site = bool(it.get("no_own_site"))

        # ✅ domain_match só quando é domínio PRÓPRIO e temos ambos URLs
        f_domain = _domain_match(website, canonical) if (own and website and canonical) else False

        # demais flags
        phone_g        = it.get("phone", "")
        phones_site    = it.get("phones_site", []) or []
        phone_site_norm= it.get("phone_site_norm", "")
        addr_g         = it.get("address", "")
        addr_s         = it.get("address_site", "")

        f_phone = _phone_match(phone_g, phones_site, phone_site_norm) if phone_g else False
        f_addr  = _address_match(addr_g, addr_s) if (addr_g and addr_s) else False
        n_sim   = _name_similarity(it.get("name",""), website or canonical)

        flags = {
            "domain_match":  f_domain,
            "phone_match":   f_phone,
            "address_match": f_addr,
            "name_similarity": round(n_sim, 3),
        }

        score = _trust_score(flags, n_sim, it.get("rating"), it.get("reviews_count"))

        # discrepâncias (só acusa domínio diferente quando deveria comparar domínio próprio)
        disc = []
        if own and website and canonical and not f_domain:
            disc.append("dominio_diferente")
        if phone_g and not f_phone:
            disc.append("telefone_divergente")
        if addr_g and addr_s and not f_addr:
            disc.append("endereco_divergente")
        if n_sim < 0.35:
            disc.append("nome_pouco_similar")

        # ✅ contar "sem site" para quem não tem domínio próprio ou não tem URL
        if no_own_site or not website:
            agg["no_website"] += 1

        # agregados
        if f_domain: agg["domain_match"] += 1
        if f_phone:  agg["phone_match"]  += 1
        if f_addr:   agg["address_match"]+= 1
        if score >= 80: agg["high_trust_80+"] += 1

        enriched = {
            **it,
            "cv_domain_match":     f_domain,
            "cv_phone_match":      f_phone,
            "cv_address_match":    f_addr,
            "cv_name_similarity":  round(n_sim, 3),
            "trust_score":         score,
            "discrepancies":       ", ".join(disc),
        }
        validated.append(enriched)

    return validated, agg
