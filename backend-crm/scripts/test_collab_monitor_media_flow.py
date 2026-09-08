"""
Script de validação ponta a ponta (Cenários C1-C4 de
docs/implementations/monitoramento-colaborador-midia.md).

Roda contra um sqlite temporário (nunca o banco real de dev) com o schema
real das tabelas envolvidas. Simula mensagens inbound de mídia (áudio,
imagem, vídeo) de um lead monitorado e valida:
  - C1: áudio é transcrito via job assíncrono e o job de classificação só é
        criado depois da transcrição.
  - C2: imagem é descrita via job assíncrono, mesmo princípio de C1.
  - C3: vídeo (sem processamento de IA) salva um placeholder imediatamente,
        sem job de mídia, com o job de classificação já criado na hora.
  - C4: toggle audio_transcription_enabled=False bloqueia a chamada real ao
        Whisper e salva um placeholder explicando o motivo.

As chamadas de IA/UazAPI (Whisper, visão, download de mídia, AI Profile) são
mockadas para tornar o teste determinístico — isso valida o mecanismo (fila,
placeholders, atualização de mensagem, encadeamento com a classificação), não
o resultado real do modelo (esse é validado manualmente/ao vivo, conforme
_guia-documentar-implementacao.md).
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
    message_type TEXT DEFAULT 'text',
    media_url TEXT
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


def _get_message(message_id: int) -> dict:
    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT id, body, message_type, media_url FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def _count_jobs(job_type: str) -> int:
    conn = database.get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) as c FROM jobs WHERE type = ?", (job_type,)
        ).fetchone()["c"]
    finally:
        conn.close()


def _inbound(*, message_type: str, message_text: str = "", media_url: str = "") -> dict:
    from services.collab_monitor.monitor_inbound_handler import handle_monitor_inbound

    return handle_monitor_inbound(
        {
            "instance_id": INSTANCE_ID,
            "from": PHONE,
            "message_text": message_text,
            "message_type": message_type,
            "media_url": media_url,
            "message_id": f"wa-msg-{message_type}",
            "from_me": False,
            "wa_display_name": "Lead Teste",
        }
    )


def main() -> None:
    tmp_dir = tempfile.mkdtemp(prefix="collab_monitor_media_test_")
    db_path = os.path.join(tmp_dir, "test_crm.db")
    _setup_db(db_path)
    database.DB_PATH = db_path

    print(f"[setup] banco temporário: {db_path}")

    from services.collab_monitor import media_worker

    # --- Cenário C1: áudio transcrito ---
    result = _inbound(message_type="audio", media_url="https://uazapi.example/audio.ogg")
    lead_id = result["lead_id"]
    msg = _get_message(result["message_id"])
    assert msg["body"] == "[Áudio] (processando…)", msg
    assert msg["message_type"] == "audio"
    assert _count_jobs("collab_monitor.media.process") == 1
    assert _count_jobs("collab_monitor.classify.local") == 0, "classify não deve rodar antes da transcrição"
    print("[C1] mensagem salva com placeholder de processamento, job de mídia criado, sem job de classify ainda")

    with patch.object(media_worker, "fetch_core_ai_profile_resolve", return_value={"audio_transcription_enabled": True}), \
         patch.object(media_worker, "fetch_core_whatsapp_token", return_value="fake-token"), \
         patch.object(media_worker, "download_audio_url_from_uazapi", return_value="https://uazapi.example/resolved.ogg"), \
         patch.object(media_worker, "transcribe_audio_from_url", return_value="Quero fechar o contrato, pode mandar o link de pagamento"):
        worker_result = media_worker.process_pending_collab_monitor_media_jobs()
    assert worker_result["processed"] == 1, worker_result
    msg = _get_message(result["message_id"])
    assert msg["body"] == "[Áudio]: Quero fechar o contrato, pode mandar o link de pagamento", msg
    assert msg["media_url"] == "https://uazapi.example/resolved.ogg", "media_url deveria ser atualizado com a URL resolvida via UazAPI"
    assert _count_jobs("collab_monitor.classify.local") == 1, "classify deveria ter sido enfileirado após a transcrição"
    print("[C1] áudio transcrito com sucesso, media_url resolvido persistido, job de classify enfileirado após a transcrição — OK")

    # --- Cenário C2: imagem descrita ---
    result = _inbound(message_type="image", media_url="https://uazapi.example/foto.jpg")
    msg = _get_message(result["message_id"])
    assert msg["body"] == "[Imagem] (processando…)", msg
    assert _count_jobs("collab_monitor.media.process") == 2

    with patch.object(media_worker, "describe_image_from_url", return_value="Print de comprovante de pagamento de R$ 500"):
        worker_result = media_worker.process_pending_collab_monitor_media_jobs()
    assert worker_result["processed"] == 1, worker_result
    msg = _get_message(result["message_id"])
    assert msg["body"] == "[Imagem]: Print de comprovante de pagamento de R$ 500", msg
    assert _count_jobs("collab_monitor.classify.local") == 2
    print("[C2] imagem descrita com sucesso, job de classify enfileirado — OK")

    # --- Cenário C3: vídeo (sem IA), placeholder imediato ---
    result = _inbound(message_type="video", media_url="https://uazapi.example/video.mp4")
    msg = _get_message(result["message_id"])
    assert msg["body"] == "[Vídeo]", msg
    assert _count_jobs("collab_monitor.media.process") == 2, "vídeo não deveria criar job de mídia"
    assert _count_jobs("collab_monitor.classify.local") == 3, "classify deveria ser enfileirado na hora para vídeo"
    print("[C3] vídeo salvo com placeholder imediato, sem job de mídia, classify já enfileirado — OK")

    # --- Cenário C4: toggle audio_transcription_enabled=False ---
    result = _inbound(message_type="audio", media_url="https://uazapi.example/audio2.ogg")
    with patch.object(media_worker, "fetch_core_ai_profile_resolve", return_value={"audio_transcription_enabled": False}), \
         patch.object(media_worker, "transcribe_audio_from_url") as mock_transcribe:
        worker_result = media_worker.process_pending_collab_monitor_media_jobs()
    assert worker_result["processed"] == 1, worker_result
    msg = _get_message(result["message_id"])
    assert msg["body"] == "[Áudio] (transcrição desativada nas configurações da conta)", msg
    mock_transcribe.assert_not_called()
    print("[C4] toggle desligado bloqueia a chamada real ao Whisper e salva placeholder — OK")

    print("\nTODOS OS CENÁRIOS PASSARAM")


if __name__ == "__main__":
    main()
