# modules/profile_extractor.py
import re
from typing import List, Dict
from urllib.parse import urlparse, parse_qs

import googlemaps
from . import config
from .agent_jobs import run_maps_enrich_fallback_via_agent


class ProfileExtractor:
    def __init__(self):
        self.gmaps_client = None
        api_key = getattr(config, "GOOGLE_MAPS_API_KEY", "")
        if api_key:
            self.gmaps_client = googlemaps.Client(key=api_key)

    # ---------- API (Places Details) ----------

    def _enrich_via_api(self, place_id: str) -> Dict:
        """Busca detalhes do lugar pela Places Details (legacy)."""
        if not self.gmaps_client or not place_id:
            return {}
        fields = [
            "name",
            "formatted_address",
            "formatted_phone_number",
            "international_phone_number",
            "website",
            "rating",
            "user_ratings_total",
            "url",
            #"type" opcional ; geralmente não precisa
        ]
        resp = self.gmaps_client.place(place_id=place_id, fields=fields)
        result = resp.get("result", {}) if resp else {}
        phone = (
            result.get("formatted_phone_number")
            or result.get("international_phone_number")
            or ""
        )

        website = self._clean_google_redirect(result.get("website", ""))
        rating = self._norm_rating(str(result.get("rating", "")))
        reviews = self._norm_reviews(str(result.get("user_ratings_total", "")))

        return {
            "name": result.get("name", ""),
            "address": result.get("formatted_address", ""),
            "phone": phone,
            "website": result.get("website", ""),
            "rating": result.get("rating", 0),
            "reviews_count": result.get("user_ratings_total", 0),
            "types": result.get("types", []),  # se vier, ótimo
            "maps_url": result.get("url", ""),
        }

    # ---------- Fallback via agente (Selenium) ----------

    def _enrich_via_selenium(self, maps_url: str) -> Dict:
        """Delegação da coleta Selenium para o agente local via jobs."""
        if not maps_url:
            return {}
        enriched = run_maps_enrich_fallback_via_agent([maps_url])
        return enriched[0] if enriched else {}

    # ---------- Orquestração ----------

    def enrich(self, items: List[Dict]) -> List[Dict]:
        """Enriquece cada item, preferindo API quando houver place_id; caso contrário, agente local."""
        enriched = []
        for it in items:
            details = {}
            pid = it.get("place_id") or ""
            if pid and self.gmaps_client:
                try:
                    details = self._enrich_via_api(pid)
                except Exception as e:
                    print(f"[ProfileExtractor] API details falhou ({pid}): {e}")
            if not details:
                try:
                    details = self._enrich_via_selenium(it.get("maps_url", ""))
                except Exception as e:
                    print(f"[ProfileExtractor] Selenium details falhou: {e}")
            # merge: detalhes sobrescrevem campos vazios do item
            merged = {**it, **{k: v for k, v in details.items() if v}}
            enriched.append(merged)
        return enriched

    #Limpeza dos dados vindos do Selenium (site/rating/reviews/telefone)
    def _clean_google_redirect(self, url: str) -> str:
        """Tira o wrapper do Google (https://www.google.com/url?q=...) e devolve o destino real."""
        if not url:
            return ""
        try:
            u = urlparse(url)
            if u.netloc.endswith("google.com") and u.path.startswith("/url"):
                q = parse_qs(u.query)
                real = q.get("q", [""])[0]
                return real or url
        except Exception:
            pass
        return url

    def _norm_rating(self, txt: str) -> float | str:
        """Converte '4,7' -> 4.7 ; mantém vazio se não deu."""
        if not txt:
            return ""
        try:
            txt2 = txt.strip().replace(",", ".")
            # pega primeiro número com ponto opcional
            m = re.search(r"\d+(?:[.,]\d+)?", txt2)
            return float(m.group(0).replace(",", ".")) if m else ""
        except Exception:
            return ""

    def _norm_reviews(self, txt: str) -> int | str:
        if not txt:
            return ""
        try:
            m = re.search(r"\d+", txt.replace(".", ""))
            return int(m.group(0)) if m else ""
        except Exception:
            return ""

    def _norm_phone(self, txt: str) -> str:
        if not txt:
            return ""
        digits = re.sub(r"\D+", "", txt)
        return digits or txt
