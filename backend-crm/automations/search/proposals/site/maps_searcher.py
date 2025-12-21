# modules/maps_searcher.py
import time

from typing import Any, Dict, List

import googlemaps
from . import config
from .agent_jobs import run_maps_search_fallback_via_agent


class MapsSearcher:
    def __init__(self, *, user_id: int | None = None, entitlements: Dict[str, Any] | None = None):
        self.gmaps_client = None
        self.api_quota_available = True
        self.user_id = user_id
        self.entitlements = entitlements
        api_key = getattr(config, "GOOGLE_MAPS_API_KEY", "")
        if api_key:
            self.gmaps_client = googlemaps.Client(key=api_key)

    def search_businesses(self, query: str, limit: int = 50):
        """
        Busca híbrida: tenta API (Places/legacy); se falhar ou não houver chave, delega ao agente local.
        Retorna lista de dicts com campos básicos.
        """
        if self.gmaps_client and self.api_quota_available:
            try:
                return self._search_via_api(query, limit)
            except Exception as e:
                print(f"[MapsSearcher] API falhou: {e}. Usando agente local...")
                self.api_quota_available = False

        return self._search_via_selenium(query, limit)

    def _search_via_api(self, query: str, limit: int):
        """Busca usando Google Maps API (Places Text Search legacy)."""
        results = []
        resp = self.gmaps_client.places(query=query, type="establishment")
        results.extend(resp.get("results", []))
        while "next_page_token" in resp and len(results) < limit:
            time.sleep(2)
            resp = self.gmaps_client.places(page_token=resp["next_page_token"])
            results.extend(resp.get("results", []))
        businesses = []
        for place in results[:limit]:
            pid = place.get("place_id", "")
            businesses.append({
                "place_id": pid,
                "name": place.get("name", ""),
                "rating": place.get("rating", 0),
                "address": place.get("formatted_address", ""),
                "types": place.get("types", []),
                # maps_url canônica pelo place_id (boa para abrir/testar)
                "maps_url": f"https://www.google.com/maps/place/?q=place_id:{pid}" if pid else "",
            })
        return businesses

    def _search_via_selenium(self, query: str, limit: int):
        """
        Fallback: cria job para o agente local executar a busca via Selenium.
        Retorna itens equivalentes ao fluxo antigo.
        """
        print("[MapsSearcher] Usando fallback via agente local...")
        return run_maps_search_fallback_via_agent(query, limit, user_id=self.user_id, entitlements=self.entitlements)
