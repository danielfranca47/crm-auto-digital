# modules/data_exporter.py
import os
import re
import json
import datetime
from typing import List, Dict

import pandas as pd

DEFAULT_COLUMNS = [
    "name", "address", "phone", "website", "rating", "reviews_count",
    "place_id", "maps_url", "types",
    # Website + scraping
    "website_canonical", "emails", "phones_site", "phone_site_norm",
    "address_site", "services_keywords", "pages_crawled",
    "facebook", "instagram", "linkedin", "youtube", "tiktok", "whatsapp",
    # Classificação de website
    "website_domain", "website_kind", "website_provider", "own_domain", "no_own_site",
    "skip_reason", "whatsapp_link", "instagram_handle",
    # Auditoria
    "ssl_ok", "mobile_ready", "cms_guess", "issues_count",
    # Scores/Prioridade (mantém os dois)
    "trust_score", "trust_score_adj", "priority", "next_action", "insights",
]

def _ensure_outdir(path: str):
    outdir = os.path.dirname(path)
    if outdir and not os.path.exists(outdir):
        os.makedirs(outdir, exist_ok=True)

def _to_dataframe(items: List[Dict]) -> pd.DataFrame:
    df = pd.DataFrame(items)
    # garante colunas e ordem básicas
    for col in DEFAULT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[DEFAULT_COLUMNS]

def export_csv(path: str, items: List[Dict]):
    _ensure_outdir(path)
    df = _to_dataframe(items)
    df.to_csv(path, index=False, encoding="utf-8-sig")

def export_xlsx(path: str, items: List[Dict]):
    _ensure_outdir(path)
    df = _to_dataframe(items)
    try:
        df.to_excel(path, index=False)
    except PermissionError:
        base, ext = os.path.splitext(path)
        alt = f"{base}_{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}{ext}"
        df.to_excel(alt, index=False)
        print(f"[export] Arquivo em uso. Salvo como: {alt}")

def export_xlsx_with_validation(path: str, items: List[Dict], summary: Dict, issues_rows: List[Dict] | None = None):
    _ensure_outdir(path)

    def norm_list(v):
        if isinstance(v, list):
            return ";".join(map(str, v))
        return v

    # Aba "Leads"
    df_leads = pd.DataFrame(items)
    for col in DEFAULT_COLUMNS:
        if col not in df_leads.columns:
            df_leads[col] = ""
    for col in ["emails", "phones_site", "types", "services_keywords"]:
        if col in df_leads.columns:
            df_leads[col] = df_leads[col].apply(norm_list)

    # Colunas extras possíveis (caso venham do pipeline)
    for extra in [
        "ssl_ok","mobile_ready","cms_guess","issues_count",
        "priority","next_action","insights",
        "trust_score","trust_score_adj",
        "cv_domain_match","cv_phone_match","cv_address_match","cv_name_similarity","discrepancies"
    ]:
        if extra not in df_leads.columns:
            df_leads[extra] = ""

    # Aba "Validacao"
    cols_val = [
        "name","website","website_canonical",
        "phone","phones_site","phone_site_norm","cv_phone_match",
        "address","address_site","cv_address_match",
        "cv_domain_match","cv_name_similarity",
        "rating","reviews_count","trust_score","trust_score_adj","discrepancies",
        "ssl_ok","mobile_ready","cms_guess","issues_count","priority","next_action",
    ]
    for c in cols_val:
        if c not in df_leads.columns:
            df_leads[c] = ""
    df_val = df_leads[cols_val].copy()

    # Aba "Estatisticas"
    df_stats = pd.DataFrame([summary])

    # Aba "Issues" (opcional; aceita colunas novas)
    df_issues = pd.DataFrame(issues_rows or [])

    try:
        with pd.ExcelWriter(path) as w:
            df_leads.to_excel(w, sheet_name="Leads", index=False)
            df_val.to_excel(w, sheet_name="Validacao", index=False)
            df_stats.to_excel(w, sheet_name="Estatisticas", index=False)
            if not df_issues.empty:
                df_issues.to_excel(w, sheet_name="Issues", index=False)
    except PermissionError:
        base, ext = os.path.splitext(path)
        alt = f"{base}_{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}{ext}"
        with pd.ExcelWriter(alt) as w:
            df_leads.to_excel(w, sheet_name="Leads", index=False)
            df_val.to_excel(w, sheet_name="Validacao", index=False)
            df_stats.to_excel(w, sheet_name="Estatisticas", index=False)
            if not df_issues.empty:
                df_issues.to_excel(w, sheet_name="Issues", index=False)
        print(f"[export] Arquivo em uso. Salvo como: {alt}")

# ---------- Export JSON por lead (para CRM) ----------

def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "lead"

def export_json_per_lead(output_dir: str, items: List[Dict], issues_rows: List[Dict] | None = None):
    """
    Grava arquivos JSON por lead em <output_dir>/<slug>.json, contendo:
      - todos os campos do lead
      - issues desse lead (filtradas por lead_name ou website)
    Retorna lista de caminhos salvos.
    """
    os.makedirs(output_dir, exist_ok=True)

    # index por (lead_name, website) para facilitar o filtro
    issues_by_lead = {}
    for r in issues_rows or []:
        key = ((r.get("lead_name") or "").strip(), (r.get("website") or "").strip())
        issues_by_lead.setdefault(key, []).append(r)

    saved = []
    for it in items:
        name = (it.get("name") or "").strip()
        website = (it.get("website") or it.get("website_canonical") or "").strip()
        domain = (it.get("website_domain") or "").strip()

        # monta um slug estável: nome + domínio (ou place_id)
        tail = domain or it.get("place_id") or "sem-dominio"
        slug = _slugify(f"{name}-{tail}") if name else _slugify(tail)

        key1 = (name, website)
        key2 = (name, "")  # fallback se website vier vazio
        lead_issues = issues_by_lead.get(key1, []) or issues_by_lead.get(key2, [])

        payload = {
            "exported_at": datetime.datetime.now().isoformat(),
            "lead": it,
            "issues": lead_issues,
        }

        path = os.path.join(output_dir, f"{slug}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        saved.append(path)

    print(f"[export] JSON por lead salvo em: {output_dir} ({len(saved)} itens)")
    return saved
