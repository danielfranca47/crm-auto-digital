"""
Reads project context: CLAUDE.md summary, architecture docs list, git log.
"""
import os
import subprocess
from pathlib import Path
from typing import List

PROJECT_DIR = Path(os.getenv("PROJECT_DIR", r"c:\crm-auto-digital"))


def get_project_context() -> str:
    parts = []

    claude_md = _read_claude_md()
    if claude_md:
        parts.append("## CLAUDE.md (visão geral do projecto)\n" + claude_md)

    arch_docs = _list_architecture_docs()
    if arch_docs:
        parts.append("## Documentação de arquitectura disponível\n" + "\n".join(arch_docs))

    git_log = _get_git_log(days=14)
    if git_log:
        parts.append("## Git log (últimos 14 dias)\n" + git_log)

    return "\n\n".join(parts)


def _read_claude_md() -> str:
    path = PROJECT_DIR / "CLAUDE.md"
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        # Keep first 4000 chars — enough for full context without being wasteful
        return text[:4000]
    except Exception:
        return ""


def _list_architecture_docs() -> List[str]:
    docs_dir = PROJECT_DIR / "docs" / "architecture"
    if not docs_dir.exists():
        return []
    items = []
    for md in sorted(docs_dir.glob("*.md")):
        items.append(f"  - {md.name}")
    return items


def _get_git_log(days: int = 14) -> str:
    try:
        result = subprocess.run(
            [
                "git", "-C", str(PROJECT_DIR),
                "log",
                f"--since={days} days ago",
                "--oneline",
                "--no-merges",
                "--format=%ci %s",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()[:3000]
    except Exception:
        return ""
