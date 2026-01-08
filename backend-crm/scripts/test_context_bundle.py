"""
Helper script to manually exercise build_context_bundle without exposing a public endpoint.

Usage example:
    CORE_API_BASE=https://core.example.com \
    CORE_USER_TOKEN=... \
    PYTHONPATH=backend-crm \
    python backend-crm/scripts/test_context_bundle.py --lead-id 1 --message "Olá!" --user-id 123 --email user@example.com

The script calls backend-core to fetch the AI Profile and loads the lead from the local SQLite database.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict

from services.ai_orchestrator import build_context_bundle
from security_core import CurrentUser


def example_usage(args: argparse.Namespace) -> Dict[str, Any]:
    token = args.token or os.getenv("CORE_USER_TOKEN")
    if not token:
        raise SystemExit("Defina --token ou a variável de ambiente CORE_USER_TOKEN")

    entitlements = json.loads(args.entitlements_json) if args.entitlements_json else {}

    current_user = CurrentUser(
        id=args.user_id,
        email=args.email,
        status="active",
        token=token,
        entitlements=entitlements,
    )

    bundle = build_context_bundle(
        current_user=current_user,
        lead_id=args.lead_id,
        inbound_message_text=args.message,
        channel=args.channel,
    )
    return bundle.dict()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Teste manual do ContextBundle")
    parser.add_argument("--lead-id", type=int, required=True, help="ID do lead no SQLite")
    parser.add_argument("--message", type=str, required=True, help="Mensagem inbound de exemplo")
    parser.add_argument("--channel", type=str, default="whatsapp", help="Canal de origem")
    parser.add_argument("--user-id", type=int, default=1, help="ID do usuário dono do lead")
    parser.add_argument("--email", type=str, default="user@example.com", help="E-mail do usuário")
    parser.add_argument(
        "--token", type=str, default=None, help="Bearer token para consultar o backend-core",
    )
    parser.add_argument(
        "--entitlements-json",
        dest="entitlements_json",
        type=str,
        default="{}",
        help="JSON com entitlements simulados para o usuário",
    )

    args = parser.parse_args()
    bundle_dict = example_usage(args)
    print("ContextBundle gerado:\n")
    print(json.dumps(bundle_dict, ensure_ascii=False, indent=2))
