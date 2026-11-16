"""Monta a bancada de testes de uma conta em .claude/agentes/<slug>/ (genérico, qualquer conta).

Uso:
  python preparar_bancada.py <slug> --email E --prod-user-id N --prod-ai-profile-id M \
        [--agente NOME] [--negocio TXT] [--idioma TXT] [--agente-tipo 01-sdr-alto-ticket|02-vendedor-autonomo|03-assistente-comercial]
        → cria a pasta, bancada.json, cenarios.json, gerar_config.py, README.md e o ambiente isolado
  python preparar_bancada.py <slug> --so-snapshot     → só lê de produção o perfil e a Base de Conhecimento
  python preparar_bancada.py <slug> --copiar-prod     → snapshot + aplica-o à conta de teste LOCAL (backends da bancada ligados)
  python preparar_bancada.py <slug> --codigo-de REF   → recopia o código de REF (branch/commit) para ambiente/codigo/
  python preparar_bancada.py <slug> --colaborador [--agente ...] [--negocio ...] [--idioma ...] [--agente-tipo ...]
        → modo colaborador: bancada só com a conta de teste do login (.claude/agentes/_acesso.json),
          transporte http, sem ambiente local, sem Railway e sem .env; tira logo o snapshot

Ambiente isolado: código de `main` em ambiente/codigo/, cópias dos bancos, .env reescritos para as
portas da bancada (core 8101, crm 8100, executors 8102 por omissão) — não colide com backends de
outras sessões nas portas 8000–8002.
"""
import argparse
import io
import json
import re
import shutil
import sqlite3
import subprocess
import tarfile
from pathlib import Path

import requests

AQUI = Path(__file__).parent
REPO = AQUI.parents[3]
SERVICOS = ("backend-core", "backend-crm", "backend-executors")
# campos do perfil que não se copiam para a conta de teste (identidade, segredos, carimbos)
NAO_COPIAR = {"id", "user_id", "created_at", "updated_at", "payment_webhook_url", "payment_webhook_secret"}

GERAR_CONFIG = '''"""Gera configs/cNN-*.json (patch do AI profile) — uma hipótese por versão.

Cada versão é um dicionário de overrides; o histórico fica em configs/ e na tabela do README.
"""
import json
import sys
from pathlib import Path

AQUI = Path(__file__).parent
PROD = json.loads((AQUI / "ambiente" / "prod_ai_profile.json").read_text(encoding="utf-8"))

VERSOES = {
    # linha de base: a configuração atual de produção, sem mudanças
    "c00-base": lambda: {},
    # "c01-<o-que-muda>": lambda: {**VERSOES["c00-base"](), "campo": "valor"},
}

if __name__ == "__main__":
    nome = sys.argv[1]
    destino = AQUI / "configs" / f"{nome}.json"
    destino.write_text(json.dumps(VERSOES[nome](), ensure_ascii=False, indent=1), encoding="utf-8")
    print(destino)
'''

README = """# Agente {nome} — {slug}

Conta: `{email}` (produção: user_id {uid}, ai_profile {pid}). Pasta fora do git.
Skill: `diagnosticar-agente` (+ skill do agente). Scripts: `.claude/skills/diagnosticar-agente/scripts/`.

## Estado atual
(preencher)

## Onde retomamos
(preencher)

## Conversas de referência

## Roteiro observado

## Factos do negócio

## Limites

## Divergências (perguntar ao utilizador)

## Processo identificado

## Critérios de sucesso

## Triagem de falhas
| Falha | Classe | Evidência | Destino |
|---|---|---|---|

## Histórico de versões
| Versão | O que mudou | Resultado (bateria) |
|---|---|---|

## Produção (aplicações, backups, baterias PROD<n>)

## Itens de código registados (plans / implementations)
"""


def env_set(path: Path, chaves: dict) -> None:
    txt = path.read_text(encoding="utf-8") if path.exists() else ""
    for k, v in chaves.items():
        if re.search(rf"^{k}=", txt, re.M):
            txt = re.sub(rf"^{k}=.*$", f"{k}={v}", txt, flags=re.M)
        else:
            txt += f"\n{k}={v}"
    path.write_text(txt.strip() + "\n", encoding="utf-8")


def copiar_codigo(pasta: Path, ref: str) -> None:
    destino = pasta / "ambiente" / "codigo"
    tar = subprocess.run(["git", "archive", "--format=tar", ref, *SERVICOS], cwd=REPO, capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(destino, filter="data")
    print(f"código de {ref} → {destino}")


def montar_ambiente(pasta: Path, b: dict) -> None:
    amb = pasta / "ambiente"
    amb.mkdir(parents=True, exist_ok=True)
    copiar_codigo(pasta, "main")
    cod = amb / "codigo"
    for s in SERVICOS:
        for nome in (".env", ".env.local"):
            if (REPO / s / nome).exists():
                shutil.copy2(REPO / s / nome, cod / s / nome)
    porta = {k: v.rsplit(":", 1)[1] for k, v in b["local"].items()}
    core_db, crm_db = (amb / "core.db").as_posix(), (amb / "crm.db").as_posix()
    env_set(cod / "backend-core" / ".env", {"DATABASE_URL": f"sqlite:///{core_db}",
                                            "EXECUTORS_BASE_URL": b["local"]["executors"]})
    crm_vars = {"CORE_API_BASE": b["local"]["core"], "EXECUTORS_BASE_URL": b["local"]["executors"], "CRM_DB_PATH": crm_db}
    env_set(cod / "backend-crm" / ".env", crm_vars)
    if (cod / "backend-crm" / ".env.local").exists():  # .env.local tem override=True — tem de levar as mesmas portas
        env_set(cod / "backend-crm" / ".env.local", crm_vars)
    env_set(cod / "backend-executors" / ".env", {"CRM_API_BASE": b["local"]["crm"], "CORE_API_BASE": b["local"]["core"]})
    # a bancada nunca envia nada para fora: o core manda emails de assinatura ao arrancar e o
    # core/crm falam com a UazAPI (WhatsApp) — apontar para endereços mortos
    sem_envio = {"SMTP_HOST": "127.0.0.1", "SMTP_PORT": "9", "SMTP_USER": "", "SMTP_PASS": "",
                 "UAZAPI_BASE_URL": "http://127.0.0.1:9", "UAZAPI_ADMIN_TOKEN": ""}
    env_set(cod / "backend-core" / ".env", sem_envio)
    env_set(cod / "backend-crm" / ".env", sem_envio)
    if (cod / "backend-crm" / ".env.local").exists():
        env_set(cod / "backend-crm" / ".env.local", sem_envio)
    # cópia com a API de backup do sqlite (inclui o WAL; copiar o ficheiro perde escritas recentes)
    for origem, dest in ((REPO / "backend-core" / "core.db", amb / "core.db"),
                         (REPO / "backend-crm" / "database" / "crm.db", amb / "crm.db")):
        src, dst = sqlite3.connect(origem), sqlite3.connect(dest)
        src.backup(dst)
        src.close()
        dst.close()
    # PYTHONUTF8=1: os backends imprimem emojis no arranque e, com a saída num ficheiro, o Windows usa cp1252 e rebenta
    print("\nArrancar (bash, em fundo, core primeiro; logs em ambiente/):")
    print(f'  cd "{cod / "backend-core"}" && PYTHONUTF8=1 python -m uvicorn app.main:app --port {porta["core"]} > ../../core.log 2>&1')
    print(f'  cd "{cod / "backend-crm"}" && PYTHONUTF8=1 python -m uvicorn app:app --port {porta["crm"]} > ../../crm.log 2>&1')
    print(f'  cd "{cod / "backend-executors"}" && PYTHONUTF8=1 python -m uvicorn app.main:app --port {porta["executors"]} > ../../executors.log 2>&1')


def snapshot(pasta: Path) -> tuple[dict, dict]:
    import simular  # mesmo diretório
    b = simular.bancada(pasta)
    p = simular.prod(b, {"acao": "perfil"})
    k = simular.prod(b, {"acao": "conhecimento"})
    if "_erro" in p:
        raise SystemExit(f"perfil de produção: {p}")
    (pasta / "ambiente").mkdir(parents=True, exist_ok=True)
    (pasta / "ambiente" / "prod_ai_profile.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    (pasta / "ambiente" / "prod_knowledge.json").write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"snapshot: agent_mode={p.get('agent_mode')} template_key={p.get('template_key')} "
          f"llm_provider={p.get('llm_provider')} updated_at={p.get('updated_at')} itens_conhecimento={len(k.get('itens') or [])}")
    return p, k


def copiar_para_local(pasta: Path) -> None:
    import simular
    b = simular.bancada(pasta)
    p, k = snapshot(pasta)
    tk = simular.token(b)
    h = {"Authorization": f"Bearer {tk}"}
    core, crm = b["local"]["core"], b["local"]["crm"]
    patch = {c: v for c, v in p.items() if c not in NAO_COPIAR and v is not None}
    r = requests.put(f"{core}/ai-profiles/me", json=patch, headers=h, timeout=60)
    print("perfil →", r.status_code, r.text[:200] if r.status_code != 200 else "ok")
    # Base de Conhecimento: substitui os itens da conta de teste (só na cópia local)
    for it in requests.get(f"{crm}/api/knowledge", headers=h, timeout=30).json():
        requests.delete(f"{crm}/api/knowledge/{it['id']}", headers=h, timeout=30)
    ok = 0
    for it in k.get("itens") or []:
        texto = it.get("content_text") or ""
        if len(texto) < 20 or len(it.get("title") or "") < 3:
            continue  # itens só de mídia/ficheiro não passam no POST manual
        r = requests.post(f"{crm}/api/knowledge", headers=h, timeout=30,
                          json={"title": it["title"], "content_text": texto, "category": it.get("category"),
                                "active_in_funnel": it.get("active_in_funnel", 1)})
        ok += r.status_code == 200
    print(f"conhecimento → {ok}/{len(k.get('itens') or [])} itens de texto copiados (mídias continuam nos URLs de produção)")
    locais = {f["field_key"]: f for f in requests.get(f"{crm}/api/knowledge/business-info", headers=h, timeout=30).json()}
    n = 0
    for f in k.get("business_info") or []:
        alvo = locais.get(f.get("field_key"))
        if alvo:
            requests.put(f"{crm}/api/knowledge/business-info/{alvo['id']}", headers=h, timeout=30,
                         json={"value": f.get("value"), "enabled": f.get("enabled", 1)})
            n += 1
        elif f.get("value"):
            requests.post(f"{crm}/api/knowledge/business-info", headers=h, timeout=30,
                          json={"field_key": f["field_key"], "label": f["label"]})
            print(f"  campo personalizado criado: {f['field_key']} — volta a correr --copiar-prod para lhe pôr o valor")
    print(f"informações do negócio → {n} campos")


def bancada_colaborador(pasta: Path, a) -> None:
    """Bancada do modo colaborador: a conta de trabalho é a do login; tudo por rotas públicas."""
    import prod_http
    conta = prod_http.executar({"agente": {}}, {"acao": "conta"})
    email = prod_http.acesso()["email"]
    for sub in ("configs", "tentativas", "referencias", "ambiente", "entrega"):
        (pasta / sub).mkdir(parents=True, exist_ok=True)
    bj = pasta / "bancada.json"
    b = json.loads(bj.read_text(encoding="utf-8")) if bj.exists() else {}
    b.update({
        "slug": a.slug,
        "transporte": "http",
        "conta": {"email": email, "prod_user_id": conta["user_id"], "prod_ai_profile_id": conta["ai_profile_id"]},
        "agente": b.get("agente") or {"nome": a.agente, "negocio": a.negocio, "idioma": a.idioma},
        "agente_tipo": b.get("agente_tipo") or a.agente_tipo,
        "prod": {"core_url": prod_http.CORE_URL, "crm_http_url": prod_http.CRM_URL},
    })
    bj.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    for nome, conteudo in (("cenarios.json", "{}\n"), ("gerar_config.py", GERAR_CONFIG),
                           ("README.md", README.format(nome=a.agente, slug=a.slug, email=email,
                                                       uid=conta["user_id"], pid=conta["ai_profile_id"]))):
        if not (pasta / nome).exists():
            (pasta / nome).write_text(conteudo, encoding="utf-8")
    print(f"bancada (colaborador): {pasta} — conta {conta['user_id']}, plano {conta['planos']}, "
          f"ai_profile {conta['ai_profile_id'] or 'ainda não criado'}")
    if conta["ai_profile_id"]:
        snapshot(pasta)


def main() -> None:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")  # consola do Windows (cp1252)
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--email")
    ap.add_argument("--prod-user-id", type=int)
    ap.add_argument("--prod-ai-profile-id", type=int)
    ap.add_argument("--agente", default="o agente")
    ap.add_argument("--negocio", default="(descrever o negócio)")
    ap.add_argument("--idioma", default="português")
    ap.add_argument("--agente-tipo", default="(por identificar)")
    ap.add_argument("--so-snapshot", action="store_true")
    ap.add_argument("--copiar-prod", action="store_true")
    ap.add_argument("--codigo-de")
    ap.add_argument("--sem-ambiente", action="store_true")
    ap.add_argument("--colaborador", action="store_true")
    ap.add_argument("--portas", default="8101,8100,8102", help="core,crm,executors — mudar se outra bancada já estiver ligada")
    a = ap.parse_args()
    pasta = REPO / ".claude" / "agentes" / a.slug
    if a.so_snapshot:
        return snapshot(pasta) and None
    if a.copiar_prod:
        return copiar_para_local(pasta)
    if a.codigo_de:
        return copiar_codigo(pasta, a.codigo_de)
    if a.colaborador:
        return bancada_colaborador(pasta, a)
    if not (a.email and a.prod_user_id and a.prod_ai_profile_id):
        raise SystemExit("para criar a bancada: --email, --prod-user-id e --prod-ai-profile-id")
    for sub in ("configs", "tentativas", "referencias", "ambiente"):
        (pasta / sub).mkdir(parents=True, exist_ok=True)
    bj = pasta / "bancada.json"
    pc, pr, pe = a.portas.split(",")
    if not bj.exists():
        bj.write_text(json.dumps({
            "slug": a.slug,
            "conta": {"email": a.email, "prod_user_id": a.prod_user_id, "prod_ai_profile_id": a.prod_ai_profile_id},
            "agente": {"nome": a.agente, "negocio": a.negocio, "idioma": a.idioma},
            "agente_tipo": a.agente_tipo,
            "prod": {"crm_url": "https://api.danielfranca.pt", "core_service": "backend-core"},
            "local": {"core": f"http://localhost:{pc}", "crm": f"http://localhost:{pr}", "executors": f"http://localhost:{pe}"},
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    for nome, conteudo in (("cenarios.json", "{}\n"), ("gerar_config.py", GERAR_CONFIG),
                           ("README.md", README.format(nome=a.agente, slug=a.slug, email=a.email,
                                                       uid=a.prod_user_id, pid=a.prod_ai_profile_id))):
        if not (pasta / nome).exists():
            (pasta / nome).write_text(conteudo, encoding="utf-8")
    print(f"bancada: {pasta}")
    if not a.sem_ambiente:
        montar_ambiente(pasta, json.loads(bj.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
