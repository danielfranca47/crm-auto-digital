#!/usr/bin/env bash
# Aplica um configs/<versão>.json ao AI profile da conta (bancada.json) em produção. SÓ com o "sim" do utilizador.
# 1) backup do perfil atual (sem segredos) em <pasta>/ambiente/prod_backup_<data>.json — sem backup, nada é aplicado
# 2) PATCH /ai-profiles/patch-by-user/<user_id> DENTRO do container do backend-core
#    (o CORE_SERVICE_TOKEN fica no container — nunca é lido nem impresso aqui)
# Uso: bash aplicar_producao.sh .claude/agentes/<slug> configs/cNN-xxx.json
set -euo pipefail
PASTA="$(cd "$1" && pwd)"
CFG="$PASTA/$2"
[ -f "$CFG" ] || { echo "não existe: $CFG"; exit 1; }
UID_PROD=$(python -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))['conta']['prod_user_id'])" "$PASTA/bancada.json")
SVC=$(python -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))['prod'].get('core_service','backend-core'))" "$PASTA/bancada.json")
TS=$(date +%Y%m%d-%H%M%S)
cd "$(git -C "$PASTA" rev-parse --show-toplevel)"  # railway está ligado na raiz do repo

BACKUP_PY=$(cat <<EOF
import sqlite3, json
c = sqlite3.connect('file:/data/core.db?mode=ro', uri=True); c.row_factory = sqlite3.Row
a = dict(c.execute("select * from ai_profiles where user_id=$UID_PROD").fetchone())
a = {k: (None if any(s in k.lower() for s in ('secret', 'token', 'password', 'api_key')) else v) for k, v in a.items()}
print(json.dumps(a, ensure_ascii=False, default=str))
EOF
)
railway ssh -s "$SVC" "echo $(printf '%s' "$BACKUP_PY" | base64 -w0) | base64 -d | python" 2>/dev/null | grep '^{' > "$PASTA/ambiente/prod_backup_${TS}.json" || true
[ -s "$PASTA/ambiente/prod_backup_${TS}.json" ] || { echo "backup falhou — nada aplicado"; exit 1; }
echo "backup: $PASTA/ambiente/prod_backup_${TS}.json"

PATCH_PY=$(cat <<EOF
import os, json, base64, urllib.request
body = base64.b64decode("$(base64 -w0 "$CFG")")
req = urllib.request.Request("http://localhost:" + os.environ.get("PORT", "8000") + "/ai-profiles/patch-by-user/$UID_PROD",
                             data=body, method="PATCH",
                             headers={"Content-Type": "application/json", "x-service-token": os.environ["CORE_SERVICE_TOKEN"]})
r = json.loads(urllib.request.urlopen(req, timeout=60).read())
print("OK", {k: r.get(k) for k in ("agent_mode", "template_key", "llm_provider", "updated_at")})
EOF
)
railway ssh -s "$SVC" "echo $(printf '%s' "$PATCH_PY" | base64 -w0) | base64 -d | python" 2>&1 | grep -E "^OK|Error|error" | head -5
