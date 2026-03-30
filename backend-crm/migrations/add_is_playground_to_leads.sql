-- Adiciona flag is_playground à tabela leads para isolamento de leads sandbox (Playground de Testes).
-- Leads com is_playground=1 não aparecem no Kanban, não consomem quota Orion e não disparam follow-up.
-- Idempotente: ALTER TABLE só é necessário uma vez; o init_db() chama ensure_column() no startup.

ALTER TABLE leads ADD COLUMN is_playground INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_leads_playground ON leads (user_id, is_playground);
