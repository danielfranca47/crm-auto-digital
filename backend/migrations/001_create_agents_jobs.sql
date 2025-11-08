-- Criação inicial das tabelas de agentes e jobs para o Agente Local
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    token TEXT NOT NULL,
    last_seen DATETIME,
    status TEXT DEFAULT 'inactive' CHECK (status IN ('active','inactive')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','in_progress','completed','failed')),
    priority INTEGER DEFAULT 0,
    result TEXT,
    error TEXT,
    agent_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    finished_at DATETIME,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created
    ON jobs(status, created_at);

CREATE INDEX IF NOT EXISTS idx_jobs_agent_status
    ON jobs(agent_id, status);

COMMIT;
