"""_load_knowledge_reference: categorias de referência sem bloco próprio + conteúdo extra
sem categoria chegam ao ContextBundle (knowledge_reference); roteiros, categorias já lidas
por bloco próprio e itens inactivos ficam de fora. Ver docs/architecture/knowledge-base.md."""

import os
import sqlite3
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ai_orchestrator import orchestrator
from services.ai_orchestrator.orchestrator import (
    ContextBundle,
    _load_knowledge_reference,
    enrich_context_bundle,
)


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE knowledge_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'manual',
            content_text TEXT NOT NULL,
            category TEXT NULL,
            active_in_funnel INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT '2026-09-23',
            updated_at TEXT NOT NULL DEFAULT '2026-09-23'
        );
        CREATE TABLE business_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, field_key TEXT, label TEXT, value TEXT,
            enabled INTEGER, sort_order INTEGER
        );
        """
    )


class LoadKnowledgeReferenceTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _create_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _insert(self, title, content, category=None, user_id=1, active=1, updated_at="2026-09-23"):
        self.conn.execute(
            "INSERT INTO knowledge_items (user_id, title, content_text, category, active_in_funnel, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, title, content, category, active, updated_at),
        )
        self.conn.commit()

    def _load(self, user_id=1):
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            return _load_knowledge_reference(user_id)

    def test_reference_category_uses_label_as_heading(self):
        self._insert("Perfil da Empresa", "Somos a Clínica Exemplo.", "company_profile")
        self.assertEqual(self._load(), [{"heading": "Perfil da Empresa", "content": "Somos a Clínica Exemplo."}])

    def test_custom_title_is_appended_to_label(self):
        self._insert("Unidade Centro", "Rua A, 10.", "company_profile")
        self.assertEqual(self._load()[0]["heading"], "Perfil da Empresa — Unidade Centro")

    def test_extra_content_without_category_included_after_guided(self):
        self._insert("Domicílio", "Atendemos ao domicílio.", None, updated_at="2026-09-24")
        self._insert("Política de Preço", "Não citar preço antes da reunião.", "price_policy")
        self.assertEqual(
            [i["heading"] for i in self._load()],
            ["Política de Preço", "Domicílio"],
        )

    def test_all_items_of_same_category_included(self):
        self._insert("FAQ Pré-Reunião", "Dura 30 min.", "pre_meeting_faq", updated_at="2026-09-20")
        self._insert("FAQ Pré-Reunião", "É online.", "pre_meeting_faq", updated_at="2026-09-21")
        self.assertEqual([i["content"] for i in self._load()], ["É online.", "Dura 30 min."])

    def test_excludes_scripts_categories_with_own_block_inactive_empty_and_other_users(self):
        self._insert("Script", "Recupere o carrinho assim…", "cart_recovery_scripts")
        self._insert("FAQ", "Já lida por bloco próprio.", "service_faq")
        self._insert("Inactivo", "Não usar.", "company_profile", active=0)
        self._insert("Áudio", "", None)
        self._insert("Outro user", "Não é meu.", "company_profile", user_id=2)
        self.assertEqual(self._load(), [])

    def test_truncates_at_char_budget(self):
        self._insert("A", "x" * 30, "company_profile", updated_at="2026-09-23")
        self._insert("B", "y" * 30, "price_policy", updated_at="2026-09-22")
        with patch.object(orchestrator, "_KNOWLEDGE_REFERENCE_MAX_CHARS", 50):
            items = self._load()
        self.assertEqual([i["content"] for i in items], ["x" * 30])

    def test_enrich_context_bundle_sets_knowledge_reference(self):
        self._insert("Perfil da Empresa", "Somos a Clínica Exemplo.", "company_profile")
        bundle = ContextBundle(user_id=1, playbook={}, lead={}, history=[], metadata={})
        with patch("services.ai_orchestrator.orchestrator.get_connection", return_value=self.conn):
            enriched = enrich_context_bundle(bundle, 1)
        self.assertEqual(enriched.knowledge_reference[0]["content"], "Somos a Clínica Exemplo.")


if __name__ == "__main__":
    unittest.main()
