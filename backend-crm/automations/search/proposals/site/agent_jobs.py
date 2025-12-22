import time
from typing import Any, Dict, List

from fastapi import HTTPException

from services import jobs_service, rate_limit_service

DEFAULT_TIMEOUT = 120
POLL_INTERVAL = 2


def _poll_job_result(job_id: int, timeout: int = DEFAULT_TIMEOUT, *, user_id: int | None = None) -> Dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = jobs_service.get_job(job_id, user_id=user_id)
        if not job:
            raise HTTPException(status_code=500, detail=f"Job {job_id} não encontrado")

        status = job.get("status")
        if status == jobs_service.JOB_STATUS_COMPLETED:
            return job.get("result") or {}
        if status == jobs_service.JOB_STATUS_FAILED:
            error = job.get("error") or "execução falhou"
            raise HTTPException(status_code=500, detail=f"Job {job_id} falhou: {error}")

        time.sleep(POLL_INTERVAL)

    raise HTTPException(status_code=500, detail=f"Job {job_id} expirou aguardando conclusão")


def run_maps_search_fallback_via_agent(
    query: str,
    limit: int,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    user_id: int | None = None,
    entitlements: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    rate_limit_service.ensure_daily_limit(
        job_type=jobs_service.TYPE_MAPS_SEARCH,
        user_id=user_id,
        entitlements=entitlements,
    )

    job = jobs_service.create_job(
        job_type=jobs_service.TYPE_MAPS_SEARCH, payload={"query": query, "limit": limit}, user_id=user_id
    )
    result = _poll_job_result(job_id=job["id"], timeout=timeout, user_id=user_id)

    items = []
    for raw in (result.get("items") or []):
        items.append(
            {
                "place_id": raw.get("place_id", ""),
                "name": raw.get("name", ""),
                "rating": raw.get("rating", 0),
                "address": raw.get("address", ""),
                "types": raw.get("types") or [],
                "maps_url": raw.get("maps_url", ""),
            }
        )
    return items


def run_maps_enrich_fallback_via_agent(
    maps_urls: List[str],
    *,
    timeout: int = DEFAULT_TIMEOUT,
    user_id: int | None = None,
    entitlements: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    rate_limit_service.ensure_daily_limit(
        job_type=jobs_service.TYPE_MAPS_ENRICH,
        user_id=user_id,
        entitlements=entitlements,
    )

    job = jobs_service.create_job(
        job_type=jobs_service.TYPE_MAPS_ENRICH, payload={"maps_urls": maps_urls}, user_id=user_id
    )
    result = _poll_job_result(job_id=job["id"], timeout=timeout, user_id=user_id)

    enriched: List[Dict[str, Any]] = []
    for raw in (result.get("items") or []):
        enriched.append(
            {
                "name": raw.get("name", ""),
                "address": raw.get("address", ""),
                "phone": raw.get("phone", ""),
                "website": raw.get("website", ""),
                "rating": raw.get("rating", 0),
                "reviews_count": raw.get("reviews_count", 0),
                "maps_url": raw.get("maps_url", ""),
            }
        )
    return enriched


__all__ = [
    "run_maps_search_fallback_via_agent",
    "run_maps_enrich_fallback_via_agent",
]
