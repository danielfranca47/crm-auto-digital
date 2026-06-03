"""Cliente Google Maps Places API.

Três modos de pesquisa, por prioridade:
  1. Proxy backend-core  — assinantes, chave API do owner, segura
  2. Direto Places API   — não-assinantes com chave própria configurada
  3. Selenium fallback   — não-assinantes sem chave (mais lento, pode falhar)
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable, Dict, Generator, List, Optional

import requests

from app.session import is_subscriber

logger = logging.getLogger(__name__)

_PLACES_TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
_PLACES_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"
_DETAILS_FIELDS = "name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,url"


class SearchError(Exception):
    pass


def search_leads(
    query: str,
    limit: int,
    session: dict,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Pesquisa leads no Google Maps. Retorna lista de dicts.
    progress_callback(current, total, message) é chamado periodicamente.

    Estratégia:
      - Assinante → proxy backend-core
      - Não-assinante com API key em session → Places API direto
      - Não-assinante sem key → Selenium fallback
    """
    from app.auth import _get_core_url

    if is_subscriber(session):
        return _search_via_proxy(query, limit, session, progress_callback)

    api_key = session.get("google_maps_api_key") or os.environ.get("GOOGLE_MAPS_API_KEY_USER")
    if api_key:
        return _search_direct(query, limit, api_key, progress_callback)

    return _search_selenium_fallback(query, limit, progress_callback)


# ── Modo 1: Proxy backend-core ──────────────────────────────────────────────

def _search_via_proxy(
    query: str,
    limit: int,
    session: dict,
    progress_cb: Optional[Callable],
) -> List[Dict[str, Any]]:
    from app.auth import _get_core_url

    _notify(progress_cb, 0, limit, "Conectando ao servidor...")
    token = session.get("access_token", "")
    base = _get_core_url()

    try:
        resp = requests.post(
            f"{base}/agent/maps-search",
            json={"query": query, "limit": limit},
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
    except requests.ConnectionError:
        raise SearchError("Não foi possível conectar ao servidor. Verifique a sua ligação.")
    except requests.Timeout:
        raise SearchError("O servidor demorou muito. Tente com um limite menor.")

    if resp.status_code == 403:
        raise SearchError("A sua assinatura expirou. Faça login novamente.")
    if resp.status_code == 503:
        raise SearchError("Servidor sem chave Google Maps configurada. Contacte o suporte.")
    if not resp.ok:
        raise SearchError(f"Erro do servidor ({resp.status_code}).")

    items = resp.json().get("items", [])
    _notify(progress_cb, len(items), len(items), f"{len(items)} leads encontrados")
    return items


# ── Modo 2: Places API direta (chave própria) ────────────────────────────────

def _search_direct(
    query: str,
    limit: int,
    api_key: str,
    progress_cb: Optional[Callable],
) -> List[Dict[str, Any]]:
    _notify(progress_cb, 0, limit, "Pesquisando no Google Maps...")

    place_ids: List[str] = []
    next_page_token: Optional[str] = None
    max_pages = min(3, (limit + 19) // 20)

    for page in range(max_pages):
        if len(place_ids) >= limit:
            break
        params: dict = {
            "query": query,
            "key": api_key,
            "language": "pt-BR",
            "region": "br",
        }
        if next_page_token:
            params["pagetoken"] = next_page_token
            time.sleep(2)

        try:
            resp = requests.get(_PLACES_TEXT_SEARCH, params=params, timeout=20)
            data = resp.json()
        except Exception as exc:
            raise SearchError(f"Erro na pesquisa: {exc}")

        status = data.get("status")
        if status == "REQUEST_DENIED":
            raise SearchError("Chave API inválida ou sem permissão. Verifique em Configurações.")
        if status == "INVALID_REQUEST":
            raise SearchError("Parâmetros de pesquisa inválidos.")
        if status not in ("OK", "ZERO_RESULTS"):
            break

        for r in data.get("results", []):
            if len(place_ids) >= limit:
                break
            if pid := r.get("place_id"):
                place_ids.append(pid)

        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break
        _notify(progress_cb, len(place_ids), limit, f"Página {page + 2}...")

    items: List[Dict[str, Any]] = []
    for i, place_id in enumerate(place_ids):
        _notify(progress_cb, i + 1, len(place_ids), f"Enriquecendo {i + 1}/{len(place_ids)}...")
        try:
            params = {
                "place_id": place_id,
                "fields": _DETAILS_FIELDS,
                "key": api_key,
                "language": "pt-BR",
            }
            resp = requests.get(_PLACES_DETAILS, params=params, timeout=15)
            detail = resp.json().get("result", {})
            items.append(_normalize_detail(detail, place_id))
        except Exception:
            continue

    _notify(progress_cb, len(items), len(items), f"{len(items)} leads encontrados")
    return items


# ── Modo 3: Selenium fallback ─────────────────────────────────────────────────

def _search_selenium_fallback(
    query: str,
    limit: int,
    progress_cb: Optional[Callable],
) -> List[Dict[str, Any]]:
    _notify(progress_cb, 0, limit, "Iniciando Chrome (modo gratuito)...")

    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from agent.config import AgentConfig
        from agent.maps_research_runner import MapsResearchRunner
    except ImportError as exc:
        raise SearchError(f"Selenium não disponível: {exc}")

    config = AgentConfig.load()
    runner = MapsResearchRunner(config)
    try:
        _notify(progress_cb, 0, limit, "Pesquisando no Google Maps (Selenium)...")
        result = runner.run_search_fallback({"query": query, "limit": limit})
        raw_items = result.get("items", [])

        _notify(progress_cb, len(raw_items) // 2, limit, f"Enriquecendo {len(raw_items)} resultados...")
        if raw_items:
            urls = [item["maps_url"] for item in raw_items if item.get("maps_url")][:limit]
            enriched = runner.run_enrich_fallback({"maps_urls": urls})
            items = enriched.get("items", raw_items)
        else:
            items = raw_items

        _notify(progress_cb, len(items), len(items), f"{len(items)} leads encontrados")
        return items
    finally:
        try:
            runner.close()
        except Exception:
            pass


# ── Helpers ────────────────────────────────────────────────────────────────────

def _normalize_detail(detail: dict, place_id: str) -> Dict[str, Any]:
    return {
        "name": detail.get("name", ""),
        "address": detail.get("formatted_address"),
        "phone": detail.get("formatted_phone_number"),
        "website": detail.get("website"),
        "rating": float(detail["rating"]) if detail.get("rating") else None,
        "reviews_count": int(detail["user_ratings_total"]) if detail.get("user_ratings_total") else None,
        "maps_url": detail.get("url") or f"https://www.google.com/maps/place/?q=place_id:{place_id}",
    }


def _notify(cb: Optional[Callable], current: int, total: int, message: str) -> None:
    if cb:
        try:
            cb(current, total, message)
        except Exception:
            pass
