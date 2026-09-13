# services/upload_cleanup.py
import logging
import time
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

BASE = Path("data/uploads/ai")


def cleanup_stale_uploads(max_age_hours: int) -> Dict[str, int]:
    """Apaga arquivos de upload (data/uploads/ai/<user_id>/*) mais antigos que
    max_age_hours e remove diretórios de usuário que ficarem vazios."""
    result = {"scanned": 0, "deleted": 0, "errors": 0}

    if not BASE.exists():
        return result

    cutoff = time.time() - (max_age_hours * 3600)

    for user_dir in BASE.iterdir():
        if not user_dir.is_dir():
            continue

        for fp in user_dir.iterdir():
            if not fp.is_file():
                continue
            result["scanned"] += 1
            try:
                if fp.stat().st_mtime < cutoff:
                    fp.unlink()
                    result["deleted"] += 1
            except OSError as exc:
                result["errors"] += 1
                logger.warning("[upload_cleanup] falha ao apagar %s: %s", fp, exc)

        try:
            if not any(user_dir.iterdir()):
                user_dir.rmdir()
        except OSError as exc:
            logger.warning("[upload_cleanup] falha ao remover diretório vazio %s: %s", user_dir, exc)

    return result
