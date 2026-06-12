"""
Converts raw session messages into a compact summary dict.
Only the summary is sent to the LLM — not full message content.
"""
from datetime import datetime
from typing import Dict, Any, List


_FILE_TOOLS = {"Edit", "Write", "MultiEdit"}
_READ_TOOLS = {"Read", "Glob", "Grep"}
_EXEC_TOOLS = {"Bash", "PowerShell"}


def summarize_session(session: Dict[str, Any]) -> Dict[str, Any]:
    messages: List[Dict] = session.get("messages", [])

    first_request = _extract_first_request(messages)
    files_modified = _extract_modified_files(messages)
    commands_run = _extract_commands(messages)
    tools_used = _extract_tools(messages)
    areas = _infer_areas(files_modified)

    started_at = session.get("started_at", "")
    date_str = _format_date(started_at)

    return {
        "date": date_str,
        "branch": session.get("branch", ""),
        "request": first_request[:600] if first_request else "(sem descrição)",
        "files_modified": files_modified[:15],
        "commands_run": commands_run[:5],
        "tools_used": sorted(tools_used),
        "areas": areas,
        "message_count": len(messages),
    }


def _extract_first_request(messages: List[Dict]) -> str:
    for msg in messages:
        if msg.get("type") != "user":
            continue
        content = msg.get("message", {}).get("content", [])
        if isinstance(content, str):
            return content.strip()
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "").strip()
                # Skip IDE context injections
                if text and not text.startswith("<ide_"):
                    return text
    return ""


def _extract_modified_files(messages: List[Dict]) -> List[str]:
    files = []
    seen = set()
    for msg in messages:
        content = msg.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            tool_name = block.get("name", "")
            if tool_name not in _FILE_TOOLS:
                continue
            inp = block.get("input", {})
            path = inp.get("file_path", "")
            if path and path not in seen:
                seen.add(path)
                # Shorten to relative if possible
                for prefix in (r"c:\crm-auto-digital\\", "c:/crm-auto-digital/"):
                    if path.lower().startswith(prefix.lower()):
                        path = path[len(prefix):]
                        break
                files.append(path)
    return files


def _extract_commands(messages: List[Dict]) -> List[str]:
    commands = []
    for msg in messages:
        content = msg.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("name") not in _EXEC_TOOLS:
                continue
            cmd = block.get("input", {}).get("command", "")
            if cmd:
                commands.append(cmd[:200])
    return commands


def _extract_tools(messages: List[Dict]) -> set:
    tools = set()
    for msg in messages:
        content = msg.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                name = block.get("name", "")
                if name:
                    tools.add(name)
    return tools


def _infer_areas(files: List[str]) -> List[str]:
    area_keywords = {
        "backend-crm": "Backend CRM",
        "backend-core": "Backend Core",
        "backend-executors": "Backend Executors",
        "frontend-crm": "Frontend CRM",
        "frontend-admin": "Frontend Admin",
        "website": "Website",
        "agent-local": "Agent Local",
        "advisor-agent": "Advisor Agent",
        "docs/": "Documentação",
    }
    found = set()
    for f in files:
        for key, label in area_keywords.items():
            if key in f.replace("\\", "/").lower():
                found.add(label)
    return sorted(found) if found else ["Geral"]


def _format_date(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str[:16] if iso_str else "data desconhecida"
