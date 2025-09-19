# automations/search/proposals/site/pipeline.py
from __future__ import annotations
import os, datetime, re
from typing import Dict, Any, Tuple, List

from .maps_searcher import MapsSearcher
from .profile_extractor import ProfileExtractor
from .website_classifier import WebsiteClassifier
from .website_scraper import WebsiteScraper
from .site_audit import SiteAuditor
from .data_validator import validate
from .cross_validator import cross_validate
from .ai_summarizer import AISummarizer
from .data_exporter import export_csv, export_xlsx, export_xlsx_with_validation
from . import config


def _slugify(s: str) -> str:
    s = s or ""
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s[:60] or "job"

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _build_query(params: Dict[str, Any]) -> str:
    """
    Monta a consulta a partir dos campos do formulário.
    Ex.: setor='barbearias', bairro='Vila Mariana', cidade='São Paulo', estado='SP', pais='Brasil'
    -> "barbearias em Vila Mariana São Paulo SP Brasil"
    """
    setor  = (params.get("setor") or "").strip()
    bairro = (params.get("bairro") or "").strip()
    cidade = (params.get("cidade") or "").strip()
    estado = (params.get("estado") or "").strip()
    pais   = (params.get("pais") or "").strip()

    loc_parts = [p for p in [bairro, cidade, estado, pais] if p]
    if setor and loc_parts:
        return f"{setor} em {' '.join(loc_parts)}"
    return " ".join([p for p in [setor] + loc_parts if p])

def run(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orquestra a automação 'site'.

    Espera em params:
      - proposta: "site" (usado só para roteamento no backend)
      - pais, estado, cidade, (bairro opcional)
      - setor (ex.: 'barbearias', 'imobiliárias', etc.)
      - quantidade (5–25 no MVP)

    Retorna:
      {
        "job_id": "...",
        "query": "...",
        "found": int,
        "summary": {...},           # cross-validation aggregate
        "files": { "csv": "...", "xlsx": "...", "xlsx_validado": "..." },
        "output_dir": "..."
      }
    """
    # 1) preparar diretórios/identificadores
    query = _build_query(params)
    qtd = int(params.get("quantidade") or 10)

    jid = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _slugify(f"{params.get('setor','')}-{params.get('cidade','')}-{params.get('estado','')}-{params.get('pais','')}")
    job_id = f"{jid}-{slug}"

    base_out = os.path.join("data", "output", "search", job_id)
    _ensure_dir(base_out)

    # 2) pipeline
    ms = MapsSearcher()
    raw = ms.search_businesses(query, limit=qtd)

    pe = ProfileExtractor()
    enriched = pe.enrich(raw)

    wc = WebsiteClassifier()
    classified = wc.enrich(enriched)

    ws = WebsiteScraper()
    with_site = ws.enrich(classified)

    auditor = SiteAuditor()
    audited, issues_rows = auditor.audit(with_site)

    cleaned, dedup_report = validate(audited)
    validated, cv_summary = cross_validate(cleaned)

    ai = AISummarizer()
    final = ai.summarize(validated, issues_rows=issues_rows)

    # 3) exports
    path_csv  = os.path.join(base_out, "leads.csv")
    path_xlsx = os.path.join(base_out, "leads.xlsx")
    path_xval = os.path.join(base_out, "leads_validado.xlsx")

    export_csv(path_csv, final)
    export_xlsx(path_xlsx, final)
    export_xlsx_with_validation(path_xval, final, cv_summary, issues_rows=issues_rows)

    # 4) resposta para o backend/frontend
    return {
        "job_id": job_id,
        "query": query,
        "found": len(final),
        "dedup": dedup_report,
        "summary": cv_summary,
        "files": {
            "csv": path_csv,
            "xlsx": path_xlsx,
            "xlsx_validado": path_xval,
        },
        "output_dir": base_out,
    }

if __name__ == "__main__":
    # Pequeno teste manual (ajuste para sua cidade/setor)
    demo = dict(
        proposta="site",
        pais="Portugal",
        estado="Algarve",
        cidade="Portimao",
        bairro="",
        setor="barbearias",
        quantidade=5,
    )
    res = run(demo)
    print("OK:", res["job_id"], "found:", res["found"])
    print("Arquivos:", res["files"])
