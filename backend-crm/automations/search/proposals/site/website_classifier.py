# modules/website_classifier.py
import re
from typing import List, Dict
from urllib.parse import urlparse, parse_qs

# Redes sociais (link não é domínio próprio)
SOCIAL = {
    "facebook.com", "m.facebook.com", "instagram.com", "linkedin.com",
    "youtube.com", "youtu.be", "tiktok.com", "twitter.com", "x.com",
}

# Mensageria
MESSAGING = {"wa.me", "api.whatsapp.com", "m.me", "t.me", "telegram.me"}

# Google Maps / shorteners de mapas
MAPS_HOSTS = {"g.page", "goo.gl", "maps.app.goo.gl"}

# Diretórios/portais (não é site próprio)
DIRECTORIES = {
    "google.com", "bing.com", "apple.com", "waze.com", "tripadvisor.com",
    "yelp.com", "foursquare.com",
}

# Agregadores de link (bio link)
LINK_AGG = {"linktr.ee", "beacons.ai", "campsite.bio", "bit.ly", "tinyurl.com"}

# Builders hospedados sem domínio próprio
BUILDER_HOSTED = {
    # Google / Business
    "business.site", "site.google.com",
    # WordPress.com / Blogger
    "wordpress.com", "blogspot.com",
    # Wix / Webflow / Squarespace / Weebly / Jimdo
    "wixsite.com", "webflow.io", "squarespace.com", "weebly.com", "jimdosite.com",
    # Outros comuns
    "godaddysites.com", "netlify.app", "github.io", "canva.site", "carrd.co",
    "webnode.page", "biosites.com"
}

def _clean_google_redirect(url: str) -> str:
    """Remove wrapper do Google (?q=<real_url>)."""
    try:
        u = urlparse(url)
        if u.netloc.endswith("google.com") and u.path.startswith("/url"):
            q = parse_qs(u.query)
            real = q.get("q", [""])[0]
            return real or url
    except Exception:
        pass
    return url

def _host(url: str) -> str:
    if not url:
        return ""
    u = urlparse(url if "://" in url else "http://" + url)
    h = (u.netloc or "").lower()
    if h.startswith("www."):
        h = h[4:]
    return h

def _is_maps(u) -> bool:
    return (u.netloc.endswith("google.com") and "/maps" in u.path.lower()) or (u.netloc in MAPS_HOSTS)

def _normalize_wa(url: str) -> str:
    """Normaliza links de WhatsApp para https://wa.me/<digits> quando possível."""
    try:
        u = urlparse(url if "://" in url else "http://" + url)
        host = (u.netloc or "").lower()
        path = u.path or ""
        q = parse_qs(u.query)
        if host == "wa.me":
            digits = re.sub(r"\D+", "", path)
            return f"https://wa.me/{digits}" if digits else url
        if host == "api.whatsapp.com":
            phone = re.sub(r"\D+", "", q.get("phone", [""])[0])
            if phone:
                return f"https://wa.me/{phone}"
    except Exception:
        pass
    return url

def _instagram_handle_from_url(url: str) -> str:
    """Extrai @handle de instagram.com/<handle> (ignora /p/, /reel/, /stories/...)."""
    try:
        u = urlparse(url if "://" in url else "http://" + url)
        if u.netloc.endswith("instagram.com"):
            parts = [p for p in (u.path or "").split("/") if p]
            if parts:
                first = parts[0]
                if first not in {"p", "reel", "reels", "stories", "explore", "accounts"}:
                    return first.lstrip("@")
    except Exception:
        pass
    return ""

def classify(url: str) -> Dict:
    """
    Classifica a URL como:
      - own (domínio próprio)  -> own_domain=True, no_own_site=False
      - social / messaging / maps / directory / link_aggregator / builder_hosted
        -> own_domain=False, no_own_site=True, skip_reason preenchido
    Também extrai instagram_handle e whatsapp_link quando aplicável.
    """
    base = {
        "website_domain": "",
        "website_kind": "unknown",
        "website_provider": "",
        "own_domain": False,
        "no_own_site": True,
        "skip_reason": "",
        # extras úteis ao comercial:
        "instagram_handle": "",
        "whatsapp_link": "",
        # campos de rede
        "facebook": "",
        "instagram": "",
        "linkedin": "",
        "youtube": "",
        "tiktok": "",
    }

    url = (url or "").strip()
    if not url:
        base["skip_reason"] = "no_url"
        return base

    url = _clean_google_redirect(url)
    u = urlparse(url if "://" in url else "http://" + url)
    host = (u.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]

    base["website_domain"] = host

    # categorias especiais (não-site)
    if host in SOCIAL:
        kind = "social"
        base.update({
            "website_kind": kind,
            "website_provider": host.split(".")[0],
            "own_domain": False,
            "no_own_site": True,
            "skip_reason": "social_link",
        })
        # preencher campos específicos
        if "instagram.com" in host:
            base["instagram"] = url
            base["instagram_handle"] = _instagram_handle_from_url(url)
        elif "facebook.com" in host:
            base["facebook"] = url
        elif "linkedin.com" in host:
            base["linkedin"] = url
        elif "youtube.com" in host or "youtu.be" in host:
            base["youtube"] = url
        elif "tiktok.com" in host:
            base["tiktok"] = url
        return base

    if host in MESSAGING:
        kind = "messaging"
        wa = _normalize_wa(url)
        base.update({
            "website_kind": kind,
            "website_provider": host.split(".")[0],
            "own_domain": False,
            "no_own_site": True,
            "skip_reason": "whatsapp",
            "whatsapp_link": wa,
        })
        return base

    if _is_maps(u):
        base.update({
            "website_kind": "maps",
            "website_provider": "google_maps",
            "own_domain": False,
            "no_own_site": True,
            "skip_reason": "maps_profile",
        })
        return base

    if host in DIRECTORIES:
        base.update({
            "website_kind": "directory",
            "website_provider": host.split(".")[0],
            "own_domain": False,
            "no_own_site": True,
            "skip_reason": "directory_link",
        })
        return base

    if host in LINK_AGG:
        base.update({
            "website_kind": "link_aggregator",
            "website_provider": host.split(".")[0],
            "own_domain": False,
            "no_own_site": True,
            "skip_reason": "link_in_bio",
        })
        return base

    if host in BUILDER_HOSTED:
        base.update({
            "website_kind": "builder_hosted",
            "website_provider": host.split(".")[0],
            "own_domain": False,
            "no_own_site": True,
            "skip_reason": "builder_subdomain",
        })
        return base

    # caso geral: domínio parece próprio
    base.update({
        "website_kind": "own",
        "website_provider": "",
        "own_domain": True,
        "no_own_site": False,
        "skip_reason": "",
    })
    return base


class WebsiteClassifier:
    """Enriquece a lista com campos de classificação de website."""
    def enrich(self, items: List[Dict]) -> List[Dict]:
        out: List[Dict] = []
        for it in items:
            w = (it.get("website") or it.get("website_canonical") or "").strip()
            info = classify(w)
            # não sobrescreve valores existentes do item com vazios da classificação
            merged = {**it, **{k: v for k, v in info.items() if (k not in it) or (it[k] in (None, "", [], {}))}}
            out.append(merged)
        return out
