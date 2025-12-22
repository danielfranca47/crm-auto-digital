# automations/search/proposals/site/runner.py
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json
import re
from typing import Dict, Any  # (List não estava sendo usado)

from . import config
from services import rate_limit_service
from .maps_searcher import MapsSearcher
from .profile_extractor import ProfileExtractor
from .website_classifier import WebsiteClassifier
from .website_scraper import WebsiteScraper
from .site_audit import SiteAuditor
from .data_validator import validate
from .cross_validator import cross_validate
from .ai_summarizer import AISummarizer
from .data_exporter import export_csv, export_xlsx, export_xlsx_with_validation


def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\-_.]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "execucao"

def _build_query(sector: str, country: str, state: str, city: str, neighborhood: str | None) -> str:
    # Ex.: "barbearia em Vila Madalena, São Paulo, São Paulo, Brasil"
    parts = []
    if sector:
        parts.append(sector)
    loc = ", ".join([p for p in [neighborhood, city, state, country] if p])
    if loc:
        parts.append(f"em {loc}")
    return " ".join(parts)

def run_site_search(
    payload: Dict[str, Any], *, user_id: int | None = None, entitlements: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """
    payload esperado:
    {
      "proposal": "site",
      "country": "Brasil",
      "state": "São Paulo",
      "city": "São Paulo",
      "neighborhood": "Vila Madalena",   # opcional
      "sector": "barbearia",
      "quantity": 20
    }
    """
    country      = (payload.get("country") or "").strip()
    state        = (payload.get("state") or "").strip()
    city         = (payload.get("city") or "").strip()
    neighborhood = (payload.get("neighborhood") or "").strip()
    sector       = (payload.get("sector") or "").strip()
    quantity     = int(payload.get("quantity") or 20)

    query = _build_query(sector, country, state, city, neighborhood)
    slug  = _slugify(f"{sector}-{city}-{state}-{country}")
    ts    = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = f"{slug}-{ts}"

    # Diretório base desta execução
    out_dir: Path = config.OUTPUT_DIR / "search" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Busca inicial
    ms = MapsSearcher(user_id=user_id, entitlements=entitlements)
    raw = ms.search_businesses(query, limit=quantity)

    rate_limit_service.consume_daily_units(
        limit_key="max_prospects_daily",
        amount=len(raw),
        user_id=user_id,
        entitlements=entitlements,
        label="prospecção",
    )

    # 2) Enriquecimento inicial (Maps detail)
    pe = ProfileExtractor(user_id=user_id, entitlements=entitlements)
    enriched = pe.enrich(raw)

    # 3) Classificação de website (próprio x social etc.)
    wc = WebsiteClassifier()
    classified = wc.enrich(enriched)

    # 4) Raspa sites próprios (pula sociais/diretórios)
    ws = WebsiteScraper()
    with_site = ws.enrich(classified)

    # 5) Auditoria de páginas (issues)
    auditor = SiteAuditor()
    audited, issues_rows = auditor.audit(with_site)

    # 6) Dedup / normalização
    cleaned, dedup_report = validate(audited)

    # 7) Cross-Validation + score  **(corrigido: usar cleaned)**
    validated, cv_summary = cross_validate(cleaned)

    # 8) Síntese "IA"
    ai = AISummarizer()
    final = ai.summarize(validated, issues_rows=issues_rows)

    # 9) Exports
    csv_path   = out_dir / "leads.csv"
    xlsx_path  = out_dir / "leads.xlsx"
    xlsxv_path = out_dir / "leads_validado.xlsx"

    export_csv(str(csv_path), final)
    export_xlsx(str(xlsx_path), final)
    export_xlsx_with_validation(str(xlsxv_path), final, cv_summary, issues_rows=issues_rows)

    # 10) Manifesto (inclui dedup_report para facilitar debug/monitoramento)
    manifest = {
        "run_id": run_id,
        "query": query,
        "params": {
            "country": country, "state": state, "city": city,
            "neighborhood": neighborhood, "sector": sector, "quantity": quantity
        },
        "files": {
            "csv": str(csv_path),
            "xlsx": str(xlsx_path),
            "xlsx_validado": str(xlsxv_path)
        },
        "dedup": dedup_report,          # <- adicionado
        "summary": cv_summary,
        "counts": {
            "found": len(raw),
            "final": len(final),
            "issues": len(issues_rows or []),
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
