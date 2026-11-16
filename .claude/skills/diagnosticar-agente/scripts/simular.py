"""Simula conversas no Playground (bancada local isolada ou produção) e mede o resultado.

Genérico para qualquer conta: tudo o que é próprio da conta vem de <pasta>/bancada.json.

Uso (<pasta> = .claude/agentes/<slug>):
  python simular.py <pasta> <cenario> <rotulo> [--prod]
  python simular.py <pasta> --bateria c1,c2,c3 <rotulo> [--prod]
  python simular.py <pasta> --resumo <rotulo>
  python simular.py <pasta> --aplicar configs/cNN.json      # PUT /ai-profiles/me na conta de teste LOCAL
  python simular.py <pasta> --perfil [campo ...]            # perfil LOCAL
  python simular.py <pasta> --prod-acao <acao> [json]       # perfil|conhecimento|sync|limpar em produção (só leitura, exceto limpar)

--prod usa o Playground de PRODUÇÃO da conta: nada é enviado por WhatsApp; as marcações
[Playground] do lead são apagadas no fim.
"""
import base64
import glob
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

AQUI = Path(__file__).parent
REPO = AQUI.parents[3]
CONTA_LOCAL = REPO / "docs" / "implementations" / "_conta-teste-local.md"
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


# ---------------------------------------------------------------- configuração da bancada

def bancada(pasta: Path) -> dict:
    return json.loads((pasta / "bancada.json").read_text(encoding="utf-8"))


def conta_local() -> dict:
    txt = CONTA_LOCAL.read_text(encoding="utf-8")
    campo = lambda rx: re.search(rx, txt).group(1)  # noqa: E731
    return {"email": campo(r"\|\s*Email\s*\|\s*`([^`]+)`"),
            "senha": campo(r"\|\s*Senha\s*\|\s*`([^`]+)`"),
            "user_id": int(campo(r"\|\s*user_id[^|]*\|\s*(\d+)")),
            "ai_profile_id": int(campo(r"\|\s*AI Profile[^|]*\|\s*id=(\d+)"))}


def token(b: dict) -> str:
    c = conta_local()
    r = requests.post(f"{b['local']['core']}/auth/login", json={"email": c["email"], "password": c["senha"]}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


# ---------------------------------------------------------------- produção (railway ssh)

def prod(b: dict, args: dict) -> dict:
    """Corre prod_turno.py dentro do container do backend-core e devolve o RESULT."""
    args = {"user_id": b["conta"]["prod_user_id"], "email": b["conta"]["email"],
            "ai_profile_id": b["conta"]["prod_ai_profile_id"], "crm_url": b["prod"]["crm_url"], **args}
    s = base64.b64encode((AQUI / "prod_turno.py").read_bytes()).decode()
    a = base64.b64encode(json.dumps(args, ensure_ascii=False).encode()).decode()
    cmd = f"echo {s} | base64 -d > /tmp/prod_turno.py && ARGS_B64={a} python /tmp/prod_turno.py 2>/dev/null"
    for tentativa in range(3):  # railway ssh devolve vazio de vez em quando
        out = subprocess.run([shutil.which("railway") or "railway", "ssh", "-s", b["prod"].get("core_service", "backend-core"), cmd],
                             capture_output=True, text=True, encoding="utf-8", timeout=600, cwd=REPO).stdout
        linha = next((l for l in out.splitlines() if l.startswith("RESULT ")), None)
        if linha:
            return json.loads(linha[7:])
        time.sleep(5 * (tentativa + 1))
    raise RuntimeError(f"sem RESULT: {out[-400:]}")


# ---------------------------------------------------------------- conversa

def bloco_bot(resp: dict) -> list[str]:
    linhas = []
    for it in resp.get("auto_items") or []:
        linhas.append(f"🖼️ [mídia automática] {it.get('media_url', '')[-40:]}" if it.get("type") == "media"
                      else f"🤖 [auto] {it.get('content', '')}")
    for m in resp.get("pre_send_media") or []:
        linhas.append(f"🖼️ [mídia LLM] {m.get('media_url', '')[-40:]}")
    for p in resp.get("message_parts") or ([resp["message_to_send"]] if resp.get("message_to_send") else []):
        linhas.append(f"🤖 {p}")
    for it in resp.get("requeue_items") or []:
        linhas.append(f"🖼️ [mídia 2ª decisão] {it.get('media_url', '')[-40:]}" if it.get("type") == "media"
                      else f"🤖 [2ª decisão] {it.get('content') or it.get('text') or it}")
    return linhas or ["🤖 (sem resposta)"]


def _llm_key(pasta: Path) -> str:
    env = (pasta / "ambiente" / "codigo" / "backend-executors" / ".env")
    if not env.exists():
        env = REPO / "backend-executors" / ".env"
    return re.search(r"^LLM_API_KEY=(.+)$", env.read_text(encoding="utf-8"), re.M).group(1).strip()


def cliente_ia(pasta: Path, b: dict, persona: str, conversa: list[tuple[str, str]]) -> str:
    """Próxima mensagem do cliente simulado (gpt-4o-mini) a partir da persona do cenário."""
    ag = b["agente"]
    hist = "\n".join(f"{'CLIENTE' if q == 'c' else ag['nome'].upper()}: {t}" for q, t in conversa)
    prompt = (
        f"Você faz o papel de um CLIENTE a conversar no WhatsApp com {ag['nome']}, atendente de: {ag['negocio']}.\n"
        f"PERSONA E OBJETIVO: {persona}\n\n"
        f"Escreva só a próxima mensagem do cliente: curta e informal, como no WhatsApp, em {ag.get('idioma', 'português')}, "
        f"e responda ao que {ag['nome']} perguntou. Siga o que a persona diz para cada situação. "
        "Não invente que recebeu algo que não foi enviado. Quando o objetivo estiver concluído (ou a persona desistir) "
        "e não tiver mais nada a dizer, responda exatamente FIM.\n\n"
        f"CONVERSA ATÉ AGORA:\n{hist}\n\nCLIENTE:"
    )
    r = requests.post("https://api.openai.com/v1/chat/completions", timeout=60,
                      headers={"Authorization": f"Bearer {_llm_key(pasta)}"},
                      json={"model": "gpt-4o-mini", "temperature": 0.4, "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip().strip('"')


def simular(pasta: Path, cenario: str, rotulo: str, em_prod: bool = False) -> Path:
    b = bancada(pasta)
    c = json.loads((pasta / "cenarios.json").read_text(encoding="utf-8"))[cenario]
    persona = c.get("persona")
    msgs = [c["primeira"]] if persona else list(c["mensagens"])
    conversa: list[tuple[str, str]] = []
    if em_prod:
        h, ai_profile_id = {}, b["conta"]["prod_ai_profile_id"]
    else:
        cl = conta_local()
        h, ai_profile_id = {"Authorization": f"Bearer {token(b)}"}, cl["ai_profile_id"]
        # agenda limpa a cada simulação: marcações do Playground ficam ligadas ao lead (user_id NULL)
        db = sqlite3.connect(pasta / "ambiente" / "crm.db")
        db.execute("delete from appointments where user_id=? or lead_id in (select id from leads where user_id=?)",
                   (cl["user_id"], cl["user_id"]))
        db.commit()
        db.close()
    lead_id = None
    brutos = []
    out = [f"# {rotulo} — cenário `{cenario}` ({'PRODUÇÃO' if em_prod else 'local'})", "",
           f"Data: {datetime.now():%Y-%m-%d %H:%M}", "", f"Esperado / origem: {c.get('origem', '')}", "", "## Conversa", ""]
    trace = ["", "## Rasto de decisão (por turno)", "",
             "| # | Mãe → efetiva | categoria | guardrails | em falta | evento agenda |", "|---|---|---|---|---|---|"]
    i = 0
    while i < len(msgs):
        msg = msgs[i]
        i += 1
        t0 = time.time()
        if em_prod:
            resp = prod(b, {"acao": "chat", "message": msg, "lead_id": lead_id, "wa_name": c.get("wa_name")})
        else:
            body = {"ai_profile_id": ai_profile_id, "message": msg, "lead_id": lead_id, "reset": lead_id is None,
                    "scenario_type": "inbound"}
            if lead_id is None:
                body["wa_display_name"] = c.get("wa_name")
            r = requests.post(f"{b['local']['crm']}/api/playground/chat", json=body, headers=h, timeout=300)
            resp = r.json() if r.status_code == 200 else {"_erro": r.status_code, "_corpo": r.text[:300]}
        if "_erro" in resp:
            out.append(f"**👤 {msg}**\n\n⚠️ erro {resp['_erro']}: {resp.get('_corpo')}\n")
            brutos.append({"_mensagem": msg, **resp})
            break
        lead_id = resp["lead_id"]
        out.append(f"**👤 Cliente:** {msg}\n")
        out += [f"> {l}".replace("\n", "\n> ") for l in bloco_bot(resp)]
        out.append("")
        dt = resp.get("decision_trace") or {}
        ev = resp.get("appointment_event")
        trace.append(f"| {i} | {dt.get('mother_route')} → {dt.get('effective_route')} | {resp['lead_state']['category']} | "
                     f"{', '.join(dt.get('guardrails_applied') or [])} | {', '.join(dt.get('missing_fields') or [])} | "
                     f"{json.dumps(ev, ensure_ascii=False) if ev else ''} |")
        print(f"[{cenario} {i}] {time.time() - t0:.0f}s  {dt.get('effective_route')}  {resp['lead_state']['category']}")
        brutos.append({"_mensagem": msg, **resp})
        if persona:
            conversa.append(("c", msg))
            conversa.append(("a", " / ".join(l.replace("🤖 ", "") for l in bloco_bot(resp))))
            if i < c.get("max_turnos", 14):
                prox = cliente_ia(pasta, b, persona, conversa)
                if "FIM" in prox:
                    break
                msgs.append(prox)
    if em_prod and lead_id is not None:
        # marcações [Playground] aparecem na agenda real da conta — apagar no fim
        out.append(f"_Limpeza da agenda de produção: {prod(b, {'acao': 'limpar', 'lead_ids': [lead_id]})}_\n")
    (pasta / "tentativas").mkdir(exist_ok=True)
    destino = pasta / "tentativas" / f"{datetime.now():%Y%m%d-%H%M}-{rotulo}-{cenario}.md"
    destino.write_text("\n".join(out + trace) + "\n", encoding="utf-8")
    destino.with_suffix(".json").write_text(json.dumps(brutos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(destino)
    return destino


# ---------------------------------------------------------------- medição

def _dia(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f"{DIAS[d.weekday()]} {d:%d/%m %H:%M}"
    except Exception:
        return iso


def _dias_semana(texto: str) -> set[str]:
    """Dias da semana citados (pt), sem acentos/maiúsculas a contar; 'terça-feira' → 'terça'."""
    base = {"segunda": "segunda", "terca": "terça", "terça": "terça", "quarta": "quarta", "quinta": "quinta",
            "sexta": "sexta", "sabado": "sábado", "sábado": "sábado", "domingo": "domingo"}
    return {base[m] for m in re.findall(r"\b(segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)\b", texto.lower())}


def resumo(pasta: Path, rotulo: str) -> str:
    linhas = [f"# Resumo — {rotulo}", "",
              "| cenário | turnos | rotas | categoria final | falhas IA / erros | mídias | links | em falta (fim) | agenda (dia real) | dia divergente (escrito / proposto / pedido vs. gravado) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for f in sorted(glob.glob(str(pasta / "tentativas" / f"*-{rotulo}-*.json"))):
        cen = Path(f).stem.split(f"-{rotulo}-", 1)[1]
        turnos = json.loads(Path(f).read_text(encoding="utf-8"))
        rotas, falhas, midias, links, agenda, divergencias = [], [], 0, 0, [], []
        pedidos_cliente: set[str] = set()
        texto_turno = texto_anterior = ""
        cat, falta = "", ""
        for n, t in enumerate(turnos, 1):
            if "_erro" in t:
                falhas.append(f"T{n} erro {t['_erro']}")
                continue
            dt = t.get("decision_trace") or {}
            r = dt.get("effective_route")
            if r and (not rotas or rotas[-1] != r):
                rotas.append(r)
            g = [x for x in dt.get("guardrails_applied") or [] if re.search(r"fail|handoff|invalid", x, re.I)]
            if g:
                falhas.append(f"T{n} {','.join(g)}")
            midias += sum(1 for it in (t.get("auto_items") or []) + (t.get("requeue_items") or []) if it.get("type") == "media")
            midias += len(t.get("pre_send_media") or [])
            texto = " ".join(t.get("message_parts") or [t.get("message_to_send") or ""])
            links += len(re.findall(r"https?://", texto))
            cat = (t.get("lead_state") or {}).get("category", cat)
            falta = ",".join(dt.get("missing_fields") or [])
            texto_anterior, texto_turno = texto_turno, texto
            pedidos_cliente |= _dias_semana(t.get("_mensagem") or "")
            ev = t.get("appointment_event")
            if ev and ev.get("start_at"):
                agenda.append(f"T{n} {ev.get('action')} {_dia(ev['start_at'])}")
                gravada = datetime.fromisoformat(ev["start_at"].replace("Z", "+00:00"))
                dia_gravado = DIAS[gravada.weekday()]
                escritas = {(int(d), int(m)) for d, m in re.findall(r"\b(\d{1,2})/(\d{1,2})\b", texto)}
                if escritas and (gravada.day, gravada.month) not in escritas:
                    divergencias.append(f"T{n}: escreveu {sorted(escritas)}, gravou {gravada:%d/%m}")
                escritos = _dias_semana(texto)
                if escritos and dia_gravado not in escritos:
                    divergencias.append(f"T{n}: escreveu {'/'.join(sorted(escritos))}, gravou {dia_gravado}")
                proposta = _dias_semana(texto_anterior)
                if len(proposta) == 1 and dia_gravado not in proposta:
                    divergencias.append(f"T{n}: última proposta foi {proposta.pop()}, gravou {dia_gravado}")
                if pedidos_cliente and dia_gravado not in pedidos_cliente:
                    divergencias.append(f"T{n}: cliente falou em {'/'.join(sorted(pedidos_cliente))}, gravou {dia_gravado} (confirmar se aceitou outro dia)")
        linhas.append(f"| {cen} | {len(turnos)} | {' → '.join(rotas)} | {cat} | {'; '.join(falhas)} | {midias} | {links} | "
                      f"{falta} | {'; '.join(agenda)} | {'; '.join(divergencias)} |")
    txt = "\n".join(linhas) + "\n"
    (pasta / "tentativas" / f"resumo-{rotulo}.md").write_text(txt, encoding="utf-8")
    return txt


# ---------------------------------------------------------------- perfil local

def aplicar(pasta: Path, patch_path: str) -> None:
    b = bancada(pasta)
    patch = json.loads((pasta / patch_path).read_text(encoding="utf-8"))
    r = requests.put(f"{b['local']['core']}/ai-profiles/me", json=patch, headers={"Authorization": f"Bearer {token(b)}"}, timeout=60)
    print(r.status_code, r.text[:300])
    r.raise_for_status()


def perfil(pasta: Path) -> dict:
    b = bancada(pasta)
    r = requests.get(f"{b['local']['core']}/ai-profiles/me", headers={"Authorization": f"Bearer {token(b)}"}, timeout=30)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # consola do Windows (cp1252) não imprime ≠, emojis
    pasta = Path(sys.argv[1]).resolve()
    a = sys.argv[2:]
    em_prod = "--prod" in a
    a = [x for x in a if x != "--prod"]
    if a[0] == "--aplicar":
        aplicar(pasta, a[1])
    elif a[0] == "--perfil":
        p = perfil(pasta)
        print(json.dumps({k: p.get(k) for k in a[1:]} if len(a) > 1 else p, ensure_ascii=False, indent=1))
    elif a[0] == "--prod-acao":
        print(json.dumps(prod(bancada(pasta), {"acao": a[1], **(json.loads(a[2]) if len(a) > 2 else {})}), ensure_ascii=False, indent=1))
    elif a[0] == "--resumo":
        print(resumo(pasta, a[1]))
    elif a[0] == "--bateria":
        for cen in a[1].split(","):
            try:
                simular(pasta, cen, a[2], em_prod)
            except Exception as e:  # um cenário partido não pára a bateria
                print(f"[{cen}] FALHOU: {e}")
        print(resumo(pasta, a[2]))
    else:
        simular(pasta, a[0], a[1], em_prod)
