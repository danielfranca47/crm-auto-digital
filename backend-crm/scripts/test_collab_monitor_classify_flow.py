"""
Script de validação ponta a ponta (Cenário C1/C2 de
docs/implementations/monitoramento-colaborador-classificacao-ia.md).

Roda contra um sqlite temporário (nunca o banco real de dev) com o schema
real das tabelas envolvidas. Simula mensagens inbound de um lead monitorado
e valida:
  - C1: avanço de estágio ponta a ponta (monitoring -> qualification ->
        apresentation -> closing), com job + log de auditoria por avanço.
  - C2: guardrail de retrocesso — depois de closing, uma classificação que
        sugere um estágio anterior é ignorada.

O classificador (chamada LLM real) é mockado para tornar o teste
determinístico — isso valida o mecanismo (fila, guardrail, atualização de
categoria, log), não o julgamento do LLM em si (esse é validado manualmente/
ao vivo, conforme _guia-documentar-implementacao.md).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402

_SCHEMA = """
CREATE TABLE leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    companyName TEXT,
    contactName TEXT,
    phone TEXT,
    email TEXT,
    origin TEXT DEFAULT 'Manual',
    category TEXT DEFAULT 'to-prospect',
    wa_display_name TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    lastMovement DATETIME DEFAULT CURRENT_TIMESTAMP,
    bot_disabled INTEGER NOT NULL DEFAULT 0,
    bot_disabled_reason TEXT,
    is_playground INTEGER NOT NULL DEFAULT 0,
    collab_monitor_instance_id TEXT NULL
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('email','whatsapp','instagram','call')),
    subject TEXT,
    body TEXT NOT NULL,
    model TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    message_type TEXT DEFAULT 'text'
);

CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT NOT NULL,
    payload TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','failed')),
    priority INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    assigned_agent_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    scheduled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    result TEXT,
    error TEXT
);

CREATE TABLE prospection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    lead_id INTEGER NOT NULL,
    channel TEXT NULL,
    message_id INTEGER NULL,
    action TEXT NOT NULL,
    notes TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE collab_monitor_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    instance_id TEXT NOT NULL UNIQUE,
    collaborator_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

USER_ID = 7
INSTANCE_ID = "test-instance-1"
PHONE = "+5511999999999"


def _setup_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT INTO collab_monitor_instances (user_id, instance_id, collaborator_name, status, created_at, updated_at) "
        "VALUES (?, ?, 'Colaborador Teste', 'connected', datetime('now'), datetime('now'))",
        (USER_ID, INSTANCE_ID),
    )
    conn.commit()
    conn.close()


def _get_lead_category(lead_id: int) -> str:
    conn = database.get_connection()
    try:
        row = conn.execute("SELECT category FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return row["category"]
    finally:
        conn.close()


def _count_category_logs(lead_id: int) -> int:
    conn = database.get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) as c FROM prospection_logs WHERE lead_id = ? AND action = 'collab_monitor_category_changed'",
            (lead_id,),
        ).fetchone()["c"]
    finally:
        conn.close()


def _inbound(text: str) -> dict:
    from services.collab_monitor.monitor_inbound_handler import handle_monitor_inbound

    return handle_monitor_inbound(
        {
            "instance_id": INSTANCE_ID,
            "from": PHONE,
            "message_text": text,
            "message_id": f"msg-{text[:10]}",
            "from_me": False,
            "wa_display_name": "Lead Teste",
        }
    )


def _run_worker_with_suggestion(suggested_category, category_reason="motivo de teste"):
    from services.collab_monitor import classify_worker

    with patch(
        "services.collab_monitor.classifier.classify_monitor_lead",
        return_value={"suggested_category": suggested_category, "category_reason": category_reason},
    ):
        return classify_worker.process_pending_collab_monitor_classify_jobs()


def main() -> None:
    tmp_dir = tempfile.mkdtemp(prefix="collab_monitor_classify_test_")
    db_path = os.path.join(tmp_dir, "test_crm.db")
    _setup_db(db_path)
    database.DB_PATH = db_path

    print(f"[setup] banco temporário: {db_path}")

    # --- Cenário C1: avanço ponta a ponta ---
    result = _inbound("Oi, vi o anúncio de vocês")
    lead_id = result["lead_id"]
    assert result["status"] == "ok", result
    print(f"[C1] lead criado lead_id={lead_id} category inicial={_get_lead_category(lead_id)!r}")
    assert _get_lead_category(lead_id) == "monitoring"

    worker_result = _run_worker_with_suggestion("qualification")
    assert worker_result["processed"] == 1, worker_result
    assert _get_lead_category(lead_id) == "qualification"
    assert _count_category_logs(lead_id) == 1
    print("[C1] monitoring -> qualification OK (1 job processado, 1 log de auditoria)")

    _inbound("Quero saber o preço do plano X")
    worker_result = _run_worker_with_suggestion("apresentation")
    assert worker_result["processed"] == 1, worker_result
    assert _get_lead_category(lead_id) == "apresentation"
    assert _count_category_logs(lead_id) == 2
    print("[C1] qualification -> apresentation OK")

    _inbound("Fechado, pode me mandar o link de pagamento")
    worker_result = _run_worker_with_suggestion("closing")
    assert worker_result["processed"] == 1, worker_result
    assert _get_lead_category(lead_id) == "closing"
    assert _count_category_logs(lead_id) == 3
    print("[C1] apresentation -> closing OK")

    # --- Cenário C2: guardrail de retrocesso ---
    _inbound("Deixa eu pensar melhor sobre isso")
    worker_result = _run_worker_with_suggestion("qualification")
    assert worker_result["processed"] == 1, worker_result  # job roda e completa, só não aplica
    assert _get_lead_category(lead_id) == "closing", "retrocesso deveria ter sido bloqueado"
    assert _count_category_logs(lead_id) == 3, "não deveria ter criado novo log de mudança"
    print("[C2] retrocesso closing -> qualification BLOQUEADO corretamente (categoria permanece closing)")

    # --- Extra: suggested_category=None não altera nada ---
    _inbound("oi")
    worker_result = _run_worker_with_suggestion(None)
    assert worker_result["processed"] == 1, worker_result
    assert _get_lead_category(lead_id) == "closing"
    assert _count_category_logs(lead_id) == 3
    print("[extra] suggested_category=null não altera categoria OK")

    print("\nTODOS OS CENÁRIOS PASSARAM")


if __name__ == "__main__":
    main()
