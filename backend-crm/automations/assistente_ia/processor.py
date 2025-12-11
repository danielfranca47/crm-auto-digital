# automations/assistente_ia/processor.py
from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from database import get_connection, get_user_profile  # 👈 novo import
from automations.assistente_ia.llm import LLMClient
from automations.assistente_ia.i18n import normalize_language          # 👈 novo
from automations.assistente_ia.text_renderer import (                  # 👈 novo
    interpolate, format_email, format_whatsapp_or_dm
)

# ----------------- Normalizadores & helpers -----------------
def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = re.sub(r"\D+", "", str(phone))
    return digits or None

def normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    email = str(email).strip()
    return email if re.match(r"[^@]+@[^@]+\.[^@]+", email) else None

def _split_semicolon(value: Optional[str]) -> list[str]:
    if value is None:
        return []
    s = str(value).strip()
    if not s:
        return []
    parts = re.split(r"[;,\n]+", s)
    return [p.strip() for p in parts if p.strip()]

def _pick_first_email(emails_val: Optional[str], single_email: Optional[str]) -> Optional[str]:
    em = normalize_email(single_email)
    if em:
        return em
    for e in _split_semicolon(emails_val):
        e = normalize_email(e)
        if e:
            return e
    return None

def _pick_phone(row_dict: dict) -> Optional[str]:
    p1 = normalize_phone(row_dict.get("phone"))
    if p1:
        return p1
    p2 = normalize_phone(row_dict.get("phone_site_norm"))
    if p2:
        return p2
    for p in _split_semicolon(row_dict.get("phones_site")):
        p = normalize_phone(p)
        if p:
            return p
    return None

def _priority_from_letter(val: Optional[str]) -> int:
    m = (str(val or "").strip().upper())
    return {"A": 1, "B": 2, "C": 3}.get(m, 3)

def _obs_bundle(row: dict) -> str:
    fields = []
    if row.get("website"): fields.append(f"website={row['website']}")
    if row.get("website_canonical"): fields.append(f"canonical={row['website_canonical']}")
    if row.get("instagram_handle") or row.get("instagram"):
        ih = row.get("instagram_handle") or row.get("instagram")
        fields.append(f"instagram={ih}")
    if row.get("whatsapp_link"): fields.append(f"whatsapp_link={row['whatsapp_link']}")
    if row.get("trust_score"): fields.append(f"trust={row['trust_score']}")
    if row.get("trust_score_adj"): fields.append(f"trust_adj={row['trust_score_adj']}")
    if row.get("next_action"): fields.append(f"next_action={row['next_action']}")
    if row.get("insights"): fields.append(f"insights={row['insights']}")
    if row.get("website_kind"): fields.append(f"site_kind={row['website_kind']}")
    if row.get("ssl_ok") is not None: fields.append(f"https={'ok' if row['ssl_ok'] else 'x'}")
    if row.get("mobile_ready") is not None: fields.append(f"mobile={'ok' if row['mobile_ready'] else 'x'}")
    if row.get("issues_count") is not None: fields.append(f"issues={row['issues_count']}")
    return "; ".join(fields)[:1000]

# ----------------- Leitura da planilha -----------------
class AssistIAProcessor:
    def read_table(self, file_path: Path, limit: Optional[int]) -> pd.DataFrame:
        if file_path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path)
        else:
            xls = pd.ExcelFile(file_path)
            sheet = "Leads" if "Leads" in xls.sheet_names else xls.sheet_names[0]
            df = pd.read_excel(xls, sheet_name=sheet)
        if limit:
            df = df.head(limit)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df

# ----------------- Mapeamento p/ tabela leads -----------------
def map_row_to_lead(row: pd.Series) -> Dict:
    d = {str(k).lower(): row[k] for k in row.index}
    company = (d.get("companyname") or d.get("name") or d.get("empresa") or "Sem nome")
    contact = d.get("contactname") or d.get("contato") or d.get("responsavel")
    email = _pick_first_email(d.get("emails"), d.get("email"))
    phone = _pick_phone(d)
    origin = (d.get("origin") or d.get("origem") or "Planilha")
    category = "to-prospect"
    priority = _priority_from_letter(d.get("priority"))
    observations = _obs_bundle(d)

    lead = {
        "companyName": company,
        "contactName": contact,
        "email": email,
        "phone": phone,
        "origin": origin,
        "category": category,
        "customMessage": None,
        "observations": observations,
        "priority": priority,
    }
    return lead

# ----------------- Dedup & CRUD no banco -----------------
def find_existing_lead(conn, companyName: str, email: Optional[str], phone: Optional[str], *, user_id: int) -> Optional[int]:
    cur = conn.cursor()
    if phone:
        cur.execute("SELECT id FROM leads WHERE phone = ? AND user_id = ? LIMIT 1", (phone, user_id))
        r = cur.fetchone()
        if r: return r["id"] if isinstance(r, dict) else r[0]
    if email:
        cur.execute("SELECT id FROM leads WHERE email = ? AND user_id = ? LIMIT 1", (email, user_id))
        r = cur.fetchone()
        if r: return r["id"] if isinstance(r, dict) else r[0]
    if companyName and companyName != "Sem nome":
        cur.execute("SELECT id FROM leads WHERE companyName = ? AND user_id = ? LIMIT 1", (companyName, user_id))
        r = cur.fetchone()
        if r: return r["id"] if isinstance(r, dict) else r[0]
    return None

def create_lead(conn, data: Dict, *, user_id: int) -> int:
    payload = {"user_id": user_id, **data}
    cols = ",".join(payload.keys())
    qs = ",".join(["?"] * len(payload))
    cur = conn.cursor()
    cur.execute(f"INSERT INTO leads ({cols}) VALUES ({qs})", tuple(payload.values()))
    return cur.lastrowid

def update_lead_light(conn, lead_id: int, new_data: Dict, *, user_id: int):
    cur = conn.cursor()
    new_data = {k: v for k, v in new_data.items() if k != "user_id"}
    cur.execute("""
        SELECT companyName, contactName, email, phone, origin, category,
               customMessage, observations, priority
        FROM leads WHERE id = ? AND user_id = ?
    """, (lead_id, user_id))
    row = cur.fetchone()
    if not row:
        return
    columns = ["companyName","contactName","email","phone","origin","category","customMessage","observations","priority"]
    current = {k: row[k] for k in columns}
    merged = current.copy()
    for k, v in new_data.items():
        if v and (not current.get(k)):
            merged[k] = v
    sets = ", ".join([f"{k} = ?" for k in merged.keys()])
    cur.execute(f"UPDATE leads SET {sets} WHERE id = ? AND user_id = ?", (*merged.values(), lead_id, user_id))

def insert_message(conn, lead_id: int, channel: str, subject: Optional[str], body: str, model: Optional[str]):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages (lead_id, channel, subject, body, model)
        VALUES (?, ?, ?, ?, ?)
    """, (lead_id, channel, subject, body, model))

# ----------------- Pipeline principal -----------------
class AssistIAProcessadorErro(Exception):
    pass

def to_bool_safe(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    if isinstance(val, str):
        return val.strip().lower() in ["1", "true", "yes", "sim"]
    return bool(val)

class AssistIAProcessor:
    def read_table(self, file_path: Path, limit: Optional[int]) -> pd.DataFrame:
        if file_path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path)
        else:
            xls = pd.ExcelFile(file_path)
            sheet = "Leads" if "Leads" in xls.sheet_names else xls.sheet_names[0]
            df = pd.read_excel(xls, sheet_name=sheet)
        if limit:
            df = df.head(limit)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df

    def process(
        self,
        file_path: Path,
        create_cards: bool,
        generate_copys: bool,
        channels: List[str],
        overwrite: str,            # "skip" | "update" | "duplicate"
        limit: Optional[int],
        tone: Optional[str],
        language: Optional[str],
        user_id: int,
    ) -> Dict:
        if not file_path.exists():
            raise AssistIAProcessadorErro("Arquivo de upload não encontrado.")

        df = self.read_table(file_path, limit)
        stats = {"created": 0, "updated": 0, "skipped": 0, "messages": 0}
        errors: List[str] = []
        created_ids: List[int] = []

        with get_connection() as conn:
            # 👇 carrega perfil do remetente
            profile = get_user_profile(conn)
            sender_ctx = {
                "name": profile.get("sender_name") or "",
                "company": profile.get("sender_company") or "",
                "email": profile.get("sender_email") or "",
                "phone": profile.get("sender_phone") or "",
                "signature": profile.get("sender_signature") or "",
            }

            # resolve idioma (UI pode mandar texto livre; se vazio, cair no default do perfil)
            lang = language or profile.get("default_language") or "pt-PT"
            lang = normalize_language(lang)

            # resolve tom (UI > default perfil > fallback)
            tone_resolved = tone or profile.get("default_tone") or "profissional e próximo"

            llm = LLMClient()

            for idx, row in df.iterrows():
                try:
                    lead_data = map_row_to_lead(row)
                    existing_id = find_existing_lead(
                        conn, lead_data["companyName"], lead_data["email"], lead_data["phone"], user_id=user_id
                    )

                    # criar/atualizar/duplicar
                    if existing_id is None:
                        new_id = create_lead(conn, lead_data, user_id=user_id)
                        stats["created"] += 1
                        created_ids.append(new_id)
                        lead_id = new_id
                    else:
                        if overwrite == "skip":
                            stats["skipped"] += 1
                            lead_id = existing_id
                        elif overwrite == "update":
                            update_lead_light(conn, existing_id, lead_data, user_id=user_id)
                            stats["updated"] += 1
                            lead_id = existing_id
                        else:
                            new_id = create_lead(conn, lead_data, user_id=user_id)
                            stats["created"] += 1
                            created_ids.append(new_id)
                            lead_id = new_id

                    # contexto vindo da planilha
                    row_dict = {str(k).lower(): row[k] for k in row.index}
                    context = {
                        "website": row_dict.get("website") or row_dict.get("website_canonical"),
                        "own_domain": to_bool_safe(row_dict.get("own_domain")),
                        "no_own_site": to_bool_safe(row_dict.get("no_own_site")),
                        "website_kind": row_dict.get("website_kind") or "",
                        "instagram_handle": row_dict.get("instagram_handle") or "",
                        "whatsapp_link": row_dict.get("whatsapp_link") or "",
                        "services_keywords": row_dict.get("services_keywords") or "",
                        "pages_crawled": int(row_dict.get("pages_crawled") or 0),
                        "ssl_ok": to_bool_safe(row_dict.get("ssl_ok")),
                        "mobile_ready": to_bool_safe(row_dict.get("mobile_ready")),
                        "cms_guess": row_dict.get("cms_guess") or "",
                        "issues_count": int(row_dict.get("issues_count") or 0),
                        "trust_score": int(row_dict.get("trust_score") or 0),
                        "trust_score_adj": int(row_dict.get("trust_score_adj") or 0),
                        "next_action": row_dict.get("next_action") or "",
                        "insights": row_dict.get("insights") or "",
                    }

                    # --- GERAÇÃO OPCIONAL ---
                    if generate_copys and channels:
                        lead_view = {
                            "id": lead_id,
                            "companyName": lead_data["companyName"],
                            "contactName": lead_data["contactName"],
                            "email": lead_data["email"],
                            "phone": lead_data["phone"],
                            "category": lead_data["category"],
                        }

                        generated = llm.generate_for_lead(
                            lead_view,
                            channels,
                            tone=tone_resolved,
                            language=lang,
                            context=context,
                            sender=sender_ctx,  # 👈 envia remetente ao LLM
                        )

                        # render por canal (interpolação + respiro) e salvar
                        for ch, payload in generated.items():
                            subj = payload.get("subject")
                            body = payload.get("body") or ""

                            # interpolação de variáveis
                            body = interpolate(body, lead_view, profile)

                            # respiro por canal
                            if ch == "email":
                                body = format_email(body)
                            elif ch in ("whatsapp", "instagram"):
                                body = format_whatsapp_or_dm(body)

                            insert_message(
                                conn, lead_id, ch, subj, body, payload.get("model")
                            )
                            stats["messages"] += 1

                except Exception as e:
                    errors.append(f"linha {idx+1}: {e}")

        return {"stats": stats, "errors": errors, "lead_ids": created_ids}
