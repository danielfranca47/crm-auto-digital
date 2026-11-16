"""Acesso à produção pelas rotas públicas, com o login da própria conta (sem Railway, sem .env).

É o transporte `"http"` do `bancada.json` (modo colaborador). Faz as mesmas ações que o
`prod_turno.py` faz dentro do container, com o mesmo formato de saída, e mais `aplicar`, `treino`, `mensagens`, `conta`
e `pedido`/`pedidos` (pedidos de correção para o Daniel).

Credenciais: `.claude/agentes/_acesso.json` = {"email": ..., "senha": ...} (fora do git). A senha e
o token nunca são impressos.

Trava: só trabalha na conta do login. Se `bancada.json` apontar para outro `prod_user_id`, recusa
— assim a bancada de um colaborador nunca escreve na conta de um cliente.
"""
import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests

AQUI = Path(__file__).parent
REPO = AQUI.parents[3]
ACESSO = REPO / ".claude" / "agentes" / "_acesso.json"
# URLs públicas de produção (as mesmas do frontend-crm/.env.production); as variáveis servem para
# testar este transporte contra backends locais
CORE_URL = os.getenv("DIAG_CORE_URL", "https://backend-core-production-863b.up.railway.app")
CRM_URL = os.getenv("DIAG_CRM_URL", "https://backend-crm-production-a702.up.railway.app")
UA = {"User-Agent": "Mozilla/5.0 (diagnosticar-agente)"}  # Cloudflare bloqueia o UA por omissão (erro 1010)
SEGREDO = ("secret", "token", "password", "api_key", "apikey")

_sessao: dict = {}


class AcessoErro(RuntimeError):
    """Problema de acesso explicado em linguagem simples (o colaborador lê esta mensagem)."""


def sem_segredos(d):
    if isinstance(d, dict):
        return {k: (None if any(s in k.lower() for s in SEGREDO) else sem_segredos(v)) for k, v in d.items()}
    if isinstance(d, list):
        return [sem_segredos(x) for x in d]
    return d


def urls(b: dict) -> tuple[str, str]:
    p = b.get("prod") or {}
    return p.get("core_url", CORE_URL).rstrip("/"), p.get("crm_http_url", CRM_URL).rstrip("/")


def acesso() -> dict:
    if not ACESSO.exists():
        raise AcessoErro("Falta o ficheiro de acesso da tua conta de teste (.claude/agentes/_acesso.json).")
    a = json.loads(ACESSO.read_text(encoding="utf-8"))
    if not a.get("email") or not a.get("senha"):
        raise AcessoErro("O ficheiro de acesso não tem o email e a senha da conta de teste.")
    return a


def _user_id_do_token(tok: str) -> int:
    payload = tok.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return int(json.loads(base64.urlsafe_b64decode(payload))["sub"])


def login(b: dict) -> tuple[str, int]:
    """(token, user_id) da conta do ficheiro de acesso. Uma vez por processo."""
    if "token" in _sessao:
        return _sessao["token"], _sessao["user_id"]
    core, _ = urls(b)
    a = acesso()
    r = requests.post(f"{core}/auth/login", json={"email": a["email"], "password": a["senha"]}, headers=UA, timeout=30)
    if r.status_code == 401:
        raise AcessoErro("O email ou a senha da conta de teste não estão certos.")
    r.raise_for_status()
    tok = r.json()["access_token"]
    _sessao.update(token=tok, user_id=_user_id_do_token(tok))
    return _sessao["token"], _sessao["user_id"]


def _trava(b: dict, user_id: int) -> None:
    esperado = (b.get("conta") or {}).get("prod_user_id")
    if esperado is not None and int(esperado) != user_id:
        raise AcessoErro(
            f"Esta bancada é da conta {esperado}, mas o login é da conta {user_id}. "
            "Por segurança só se trabalha na conta de teste do login.")


def _call(method: str, url: str, tok: str, body=None, timeout: int = 300):
    r = requests.request(method, url, json=body, timeout=timeout,
                         headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json", **UA})
    if r.status_code >= 400:
        return {"_erro": r.status_code, "_corpo": r.text[:400]}
    return r.json() if r.content else None


def executar(b: dict, args: dict) -> dict:
    """Mesmas ações e mesma saída que prod_turno.py, mais as do modo colaborador (ver o topo)."""
    tok, uid = login(b)
    _trava(b, uid)
    core, crm = urls(b)
    acao = args["acao"]
    if acao == "perfil":
        return sem_segredos(_call("GET", f"{core}/ai-profiles/me", tok))
    if acao == "conhecimento":
        return {"itens": _call("GET", f"{crm}/api/knowledge", tok),
                "business_info": _call("GET", f"{crm}/api/knowledge/business-info", tok)}
    if acao == "chat":
        body = {"ai_profile_id": args["ai_profile_id"], "message": args["message"], "lead_id": args.get("lead_id"),
                "reset": args.get("lead_id") is None, "scenario_type": "inbound"}
        if args.get("lead_id") is None:
            body["wa_display_name"] = args.get("wa_name")
        return _call("POST", f"{crm}/api/playground/chat", tok, body)
    if acao == "limpar":
        # apaga só as marcações do Playground desses leads (as reais e as do Google ficam)
        apagadas = []
        for lid in args.get("lead_ids", []):
            for a in _call("GET", f"{crm}/api/appointments/lead/{lid}", tok) or []:
                if isinstance(a, dict) and a.get("source") == "playground":
                    _call("DELETE", f"{crm}/api/appointments/{a['id']}", tok)
                    apagadas.append(a["id"])
        return {"apagadas": apagadas}
    if acao == "sync":
        now = datetime.now(timezone.utc)
        s, e = now.isoformat(), (now + timedelta(days=21)).isoformat()
        r = _call("POST", f"{crm}/api/appointments/google-sync?start={quote(s)}&end={quote(e)}", tok)
        if isinstance(r, list):
            g = [a for a in r if a.get("source") == "google"]
            return {"total": len(r), "google": len(g),
                    "google_horarios": sorted((a.get("start_at"), a.get("end_at")) for a in g)}
        return r
    if acao == "aplicar":
        # atualização parcial: só os campos do patch mudam (PATCH /ai-profiles/me)
        r = _call("PATCH", f"{core}/ai-profiles/me", tok, args["patch"], timeout=60)
        return r if isinstance(r, dict) and "_erro" in r else {
            k: (r or {}).get(k) for k in ("id", "agent_mode", "template_key", "llm_provider", "updated_at")}
    if acao == "treino":
        op = args.get("op", "listar")
        if op == "listar":
            return _call("GET", f"{crm}/api/playground/training/export", tok)
        if op == "adicionar":
            return _call("POST", f"{crm}/api/playground/training", tok, {"ai_profile_id": args["ai_profile_id"], **args["item"]})
        if op == "zerar":
            return _call("DELETE", f"{crm}/api/playground/training", tok)
        return {"_erro": "op desconhecida", "_corpo": op}
    if acao == "pedido":
        # pedido de correção do sistema para o Daniel (o que a configuração não resolve)
        campos = ("titulo", "sintoma", "evidencia", "cenarios_json", "bancada")
        return _call("POST", f"{crm}/api/suporte/pedidos-correcao", tok, {k: args.get(k) for k in campos}, timeout=60)
    if acao == "pedidos":
        return _call("GET", f"{crm}/api/suporte/pedidos-correcao", tok)
    if acao == "mensagens":
        return _call("GET", f"{crm}/api/assistente-ia/messages/{args['lead_id']}", tok)
    if acao == "conta":
        ent = _call("GET", f"{core}/me/entitlements", tok)
        p = _call("GET", f"{core}/ai-profiles/me", tok)
        return {"user_id": uid, "subscription_status": (ent or {}).get("subscription_status"),
                "planos": [x.get("plan_code") for x in (ent or {}).get("products") or []],
                "ai_profile_id": p.get("id") if isinstance(p, dict) and "_erro" not in p else None}
    return {"_erro": "acao desconhecida", "_corpo": acao}


def cliente_simulado(b: dict, persona: str, conversa: list[tuple[str, str]]) -> str:
    """Próxima fala do cliente de teste, gerada no servidor (POST /api/playground/simulated-client)."""
    tok, _ = login(b)
    _, crm = urls(b)
    ag = b["agente"]
    body = {"persona": persona, "agente": {"nome": ag["nome"], "negocio": ag["negocio"], "idioma": ag.get("idioma")},
            "conversa": [{"de": "cliente" if q == "c" else "agente", "texto": t[:4000]} for q, t in conversa][-40:]}
    r = _call("POST", f"{crm}/api/playground/simulated-client", tok, body, timeout=120)
    if isinstance(r, dict) and "_erro" in r:
        raise RuntimeError(f"cliente simulado: {r['_erro']} {r.get('_corpo')}")
    return "FIM" if r.get("fim") else r["mensagem"]
