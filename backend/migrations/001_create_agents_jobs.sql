-- Cria tabelas para o Agente Local (agents, jobs)
-- Script idempotente para execução manual, se necessário.

BEGIN;

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT,
    token TEXT,
    status TEXT NOT NULL DEFAULT 'offline' CHECK (status IN ('offline','online','disabled')),
    capabilities TEXT,
    version TEXT,
    last_seen DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    error TEXT,
    FOREIGN KEY (assigned_agent_id) REFERENCES agents(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_type ON jobs(status, type, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_jobs_assigned ON jobs(assigned_agent_id, status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);

COMMIT;
