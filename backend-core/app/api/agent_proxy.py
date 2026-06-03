"""Endpoint proxy para o agent-local standalone.

Assinantes chamam este endpoint para pesquisar no Google Maps usando
a chave API do owner — a chave nunca é exposta no executável do cliente.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.api.auth import get_current_user
from app.config import settings
from app.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent-proxy"])

_PLACES_TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
_PLACES_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"
_DETAILS_FIELDS = "name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,url"


class MapsSearchRequest(BaseModel):
    query: str
    limit: int = 20


class LeadItem(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    maps_url: Optional[str] = None


class MapsSearchResponse(BaseModel):
    items: List[LeadItem]
    total: int


@router.post("/maps-search", response_model=MapsSearchResponse)
def maps_search(
    payload: MapsSearchRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    api_key = settings.GOOGLE_MAPS_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Maps API não configurada no servidor",
        )

    active_sub = (
        db.query(models.Subscription)
        .filter(
            models.Subscription.user_id == current_user.id,
            models.Subscription.status == "active",
        )
        .first()
    )
    if not active_sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Funcionalidade exclusiva para assinantes ativos",
        )

    limit = max(1, min(payload.limit, 60))

    place_ids: List[str] = []
    next_page_token: Optional[str] = None

    with httpx.Client(timeout=30) as client:
        for page in range(3):
            if len(place_ids) >= limit:
                break

            params: dict = {
                "query": payload.query,
                "key": api_key,
                "language": "pt-BR",
                "region": "br",
            }
            if next_page_token:
                params["pagetoken"] = next_page_token
                import time; time.sleep(2)  # Google requires a short delay between paginated calls

            try:
                resp = client.get(_PLACES_TEXT_SEARCH, params=params)
                data = resp.json()
            except Exception as exc:
                logger.error("Falha na chamada Places Text Search: %s", exc)
                break

            if data.get("status") == "REQUEST_DENIED":
                logger.error("Places API negou request: %s", data.get("error_message"))
                raise HTTPException(status_code=502, detail="Chave da API inválida ou sem permissão")

            for result in data.get("results", []):
                if len(place_ids) >= limit:
                    break
                pid = result.get("place_id")
                if pid:
                    place_ids.append(pid)

            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break

        items: List[LeadItem] = []
        for place_id in place_ids:
            params = {
                "place_id": place_id,
                "fields": _DETAILS_FIELDS,
                "key": api_key,
                "language": "pt-BR",
            }
            try:
                resp = client.get(_PLACES_DETAILS, params=params)
                detail = resp.json().get("result", {})
                items.append(
                    LeadItem(
                        name=detail.get("name", ""),
                        address=detail.get("formatted_address"),
                        phone=detail.get("formatted_phone_number"),
                        website=detail.get("website"),
                        rating=float(detail["rating"]) if detail.get("rating") else None,
                        reviews_count=int(detail["user_ratings_total"]) if detail.get("user_ratings_total") else None,
                        maps_url=detail.get("url") or f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                    )
                )
            except Exception as exc:
                logger.warning("Falha ao obter detalhes do place %s: %s", place_id, exc)
                continue

    logger.info(
        "maps_search: user=%s query=%r limit=%d results=%d",
        current_user.id, payload.query, limit, len(items),
    )
    return MapsSearchResponse(items=items, total=len(items))
