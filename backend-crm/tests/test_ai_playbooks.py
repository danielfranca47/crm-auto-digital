import importlib.util
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PLAYBOOKS_PATH = os.path.join(PROJECT_ROOT, "services", "ai_playbooks", "__init__.py")
spec = importlib.util.spec_from_file_location("ai_playbooks", PLAYBOOKS_PATH)
ai_playbooks = importlib.util.module_from_spec(spec)
sys.modules["ai_playbooks"] = ai_playbooks
spec.loader.exec_module(ai_playbooks)
get_playbook = ai_playbooks.get_playbook


class PlaybookSelectionTests(unittest.TestCase):
    def test_get_playbook_returns_closer_template(self):
        playbook = get_playbook("closer_agressivo")
        self.assertEqual(playbook.get("response_style"), "direct")
        self.assertEqual(playbook.get("max_chars"), 350)


if __name__ == "__main__":
    unittest.main()
