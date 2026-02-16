"""Limpeza de telefones BR em leads para canônico E.164 com regra do 9º dígito móvel.

Uso:
    cd backend-crm
    python scripts/normalize_br_phones.py
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database import get_connection

NORMALIZER_PATH = BASE_DIR / "services" / "phone_normalizer.py"
spec = importlib.util.spec_from_file_location("phone_normalizer_module", NORMALIZER_PATH)
phone_normalizer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(phone_normalizer)

PhoneNormalizationError = phone_normalizer.PhoneNormalizationError
normalize_to_e164 = phone_normalizer.normalize_to_e164


@dataclass
class MigrationStats:
    scanned: int = 0
    updated: int = 0
    unchanged: int = 0
    conflicts: int = 0
    invalid: int = 0


def run() -> MigrationStats:
    stats = MigrationStats()

    with get_connection() as conn:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, user_id, phone
              FROM leads
             WHERE phone LIKE '+55%'
               AND length(replace(phone, '+', '')) = 12
            ORDER BY id ASC
            """
        ).fetchall()

        for row in rows:
            stats.scanned += 1
            lead_id = int(row["id"])
            user_id = int(row["user_id"]) if row["user_id"] is not None else None
            phone = row["phone"]

            try:
                canonical = normalize_to_e164(phone)
            except PhoneNormalizationError:
                stats.invalid += 1
                print(f"[INVALID] lead_id={lead_id} user_id={user_id} phone={phone}")
                continue

            if canonical == phone:
                stats.unchanged += 1
                continue

            conflict = cur.execute(
                """
                SELECT id
                  FROM leads
                 WHERE user_id IS ?
                   AND phone = ?
                   AND id != ?
                 LIMIT 1
                """,
                (user_id, canonical, lead_id),
            ).fetchone()

            if conflict:
                stats.conflicts += 1
                print(
                    f"[CONFLICT] user_id={user_id} lead_id={lead_id} phone={phone} "
                    f"canonical={canonical} existing_lead_id={int(conflict['id'])}"
                )
                continue

            cur.execute("UPDATE leads SET phone = ? WHERE id = ?", (canonical, lead_id))
            stats.updated += 1
            print(f"[UPDATED] lead_id={lead_id} user_id={user_id} {phone} -> {canonical}")

        conn.commit()

    return stats


if __name__ == "__main__":
    result = run()
    print(
        "[DONE] "
        f"scanned={result.scanned} updated={result.updated} unchanged={result.unchanged} "
        f"conflicts={result.conflicts} invalid={result.invalid}"
    )
