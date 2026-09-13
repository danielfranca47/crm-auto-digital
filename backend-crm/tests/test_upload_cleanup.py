import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.upload_cleanup import cleanup_stale_uploads


class _ChdirTestCase(unittest.TestCase):
    """Roda cada teste dentro de um cwd temporário, já que `services/upload_cleanup.py`
    resolve `data/uploads/ai/...` como caminho relativo ao processo (mesmo comportamento
    de produção)."""

    def setUp(self):
        self._original_cwd = os.getcwd()
        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


def _touch(fp: Path, age_hours: float) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_bytes(b"conteudo")
    mtime = time.time() - (age_hours * 3600)
    os.utime(fp, (mtime, mtime))


class UploadCleanupTest(_ChdirTestCase):
    def test_old_file_is_deleted(self):
        fp = Path("data/uploads/ai/1/old-upload.xlsx")
        _touch(fp, age_hours=48)

        result = cleanup_stale_uploads(max_age_hours=24)

        self.assertFalse(fp.exists())
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["errors"], 0)

    def test_recent_file_is_kept(self):
        fp = Path("data/uploads/ai/1/recent-upload.xlsx")
        _touch(fp, age_hours=1)

        result = cleanup_stale_uploads(max_age_hours=24)

        self.assertTrue(fp.exists())
        self.assertEqual(result["deleted"], 0)

    def test_empty_user_dir_is_removed_after_cleanup(self):
        fp = Path("data/uploads/ai/7/old-upload.csv")
        _touch(fp, age_hours=48)

        cleanup_stale_uploads(max_age_hours=24)

        self.assertFalse(fp.parent.exists())

    def test_user_dir_kept_when_a_recent_file_remains(self):
        old_fp = Path("data/uploads/ai/9/old-upload.csv")
        recent_fp = Path("data/uploads/ai/9/recent-upload.csv")
        _touch(old_fp, age_hours=48)
        _touch(recent_fp, age_hours=1)

        cleanup_stale_uploads(max_age_hours=24)

        self.assertFalse(old_fp.exists())
        self.assertTrue(recent_fp.exists())
        self.assertTrue(recent_fp.parent.exists())

    def test_missing_base_dir_returns_zeroed_counters_without_error(self):
        result = cleanup_stale_uploads(max_age_hours=24)

        self.assertEqual(result, {"scanned": 0, "deleted": 0, "errors": 0})


if __name__ == "__main__":
    unittest.main()
