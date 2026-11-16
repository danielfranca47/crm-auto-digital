# Corre DENTRO do container do backend-core em produção (via railway ssh) — ver simular.py::_prod.
# Cria uma sessão curta para a conta com a função de login do próprio core e chama o core/CRM de
# produção. O token nunca sai do container; os segredos do perfil são apagados antes de imprimir.
# Entrada: env ARGS_B64 = base64(JSON) com {"acao", "user_id", "email", "ai_profile_id", "crm_url", ...}
# Ações: perfil | conhecimento | chat | limpar | sync
import base64, json, os, sys, urllib.error, urllib.parse, urllib.request
from datetime import timedelta, datetime, timezone

sys.path.insert(0, os.getcwd())
from app.api.auth import create_access_token  # noqa: E402

args = json.loads(base64.b64decode(os.environ["ARGS_B64"]))
CRM = args["crm_url"].rstrip("/")
CORE = "http://localhost:" + os.environ.get("PORT", "8000")
tok = create_access_token({"sub": str(args["user_id"]), "email": args["email"]}, expires_delta=timedelta(minutes=30))
H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
     "User-Agent": "Mozilla/5.0 (diagnosticar-agente)"}  # Cloudflare bloqueia o UA do urllib (erro 1010)
SEGREDO = ("secret", "token", "password", "api_key", "apikey")


def call(method, url, body=None):
    req = urllib.request.Request(url, method=method, headers=H, data=json.dumps(body).encode() if body is not None else None)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=300).read() or b"null")
    except urllib.error.HTTPError as e:
        return {"_erro": e.code, "_corpo": e.read().decode()[:400]}


def sem_segredos(d):
    if isinstance(d, dict):
        return {k: (None if any(s in k.lower() for s in SEGREDO) else sem_segredos(v)) for k, v in d.items()}
    if isinstance(d, list):
        return [sem_segredos(x) for x in d]
    return d


acao = args["acao"]
if acao == "perfil":
    out = sem_segredos(call("GET", f"{CORE}/ai-profiles/me"))
elif acao == "conhecimento":
    out = {"itens": call("GET", f"{CRM}/api/knowledge"),
           "business_info": call("GET", f"{CRM}/api/knowledge/business-info")}
elif acao == "chat":
    body = {"ai_profile_id": args["ai_profile_id"], "message": args["message"], "lead_id": args.get("lead_id"),
            "reset": args.get("lead_id") is None, "scenario_type": "inbound"}
    if args.get("lead_id") is None:
        body["wa_display_name"] = args.get("wa_name")
    out = call("POST", f"{CRM}/api/playground/chat", body)
elif acao == "limpar":
    # apaga só as marcações do Playground desses leads (as reais e as do Google ficam)
    apagadas = []
    for lid in args.get("lead_ids", []):
        for a in call("GET", f"{CRM}/api/appointments/lead/{lid}") or []:
            if isinstance(a, dict) and a.get("source") == "playground":
                call("DELETE", f"{CRM}/api/appointments/{a['id']}")
                apagadas.append(a["id"])
    out = {"apagadas": apagadas}
elif acao == "sync":
    now = datetime.now(timezone.utc)
    s, e = now.isoformat(), (now + timedelta(days=21)).isoformat()
    r = call("POST", f"{CRM}/api/appointments/google-sync?start={urllib.parse.quote(s)}&end={urllib.parse.quote(e)}")
    if isinstance(r, list):
        g = [a for a in r if a.get("source") == "google"]
        out = {"total": len(r), "google": len(g), "google_horarios": sorted((a.get("start_at"), a.get("end_at")) for a in g)}
    else:
        out = r
else:
    out = {"_erro": "acao desconhecida", "_corpo": acao}
print("RESULT", json.dumps(out, ensure_ascii=False, default=str))
