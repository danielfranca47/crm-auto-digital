import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import services.deploy_version as dv


class _Resp:
    def __init__(self, status, data):
        self.status_code = status
        self._data = data

    def json(self):
        return self._data


class DeployVersionTest(unittest.TestCase):
    def test_versoes_junta_os_tres_servicos(self):
        def fake_get(url, timeout):
            return _Resp(200, {"commit": "core123"}) if url.endswith("/version") else _Resp(200, {"commit": "exe456"})

        env = {"RAILWAY_GIT_COMMIT_SHA": "crm789", "EXECUTORS_BASE_URL": "http://exe", "CORE_API_BASE": "http://core"}
        with patch.dict(os.environ, env), patch.object(dv, "_get_core_base", return_value="http://core"), \
                patch.object(dv.httpx, "get", side_effect=fake_get) as g:
            v = dv.versoes()
        self.assertEqual(v, {"crm": "crm789", "core": "core123", "executors": "exe456"})
        self.assertEqual([c.args[0] for c in g.call_args_list], ["http://core/version", "http://exe/health"])

    def test_servico_em_baixo_da_none(self):
        with patch.dict(os.environ, {"RAILWAY_GIT_COMMIT_SHA": "", "EXECUTORS_BASE_URL": ""}), \
                patch.object(dv, "_get_core_base", return_value="http://core"), \
                patch.object(dv.httpx, "get", side_effect=RuntimeError("down")):
            v = dv.versoes()
        self.assertEqual(v, {"crm": None, "core": None, "executors": None})


if __name__ == "__main__":
    unittest.main()
