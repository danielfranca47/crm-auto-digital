"""Casos do verificador de comandos. Só passam texto — nenhum comando é executado."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "verificar_comando.py"
sys.path.insert(0, str(SCRIPT.parent))

import verificar_comando as vc  # noqa: E402


def decisao(comando, ferramenta="Bash", cwd=None):
    resultado = vc.avaliar(comando, ferramenta, cwd)
    return resultado[0] if resultado else None


# --------------------------------------------------------------------------
# git push forçado -> recusar
# --------------------------------------------------------------------------

PUSH_FORCADO = [
    # forma habitual (já coberta pelas regras deny)
    "git push --force",
    "git push -f origin main",
    "git push origin main --force",
    "git push --force-with-lease origin main",
    "git push --force-with-lease=main:abc origin main",
    "cd backend-crm && git push --force",
    # opções antes do subcomando
    "git -C . push -f",
    "git -C backend-crm push origin main --force",
    "git -c push.default=current push --force",
    "git --git-dir=.git --work-tree=. push -f",
    "git --git-dir .git push -f",
    "git --no-pager push -f",
    # outro nome do executável
    "git.exe push -f",
    "/usr/bin/git push --force",
    '"C:\\Program Files\\Git\\cmd\\git.exe" push --force',
    "git 'push' --force",
    'git "pu"sh -f',
    "GIT push --force",
    # forçar sem a opção habitual
    "git push origin +main",
    "git push origin +HEAD:main",
    "git push --mirror",
    "git push --forc origin main",
    "git push --force-if-includes origin main",
    "git push -fu origin main",
    "git push -uf origin main",
    "git push --dry-run --force origin main",
    # invólucros e palavras de controlo
    "GIT_TRACE=1 git push -f",
    "env GIT_TRACE=1 git push -f",
    "timeout 30 git push -f",
    "nohup git push -f &",
    "command git push -f",
    "sudo -u root git push -f",
    "if git push -f; then echo ok; fi",
    "(git push -f)",
    "{ git push -f; }",
    "echo \"$(git push -f)\"",
    "echo `git push -f`",
    "git status | git push -f",
    r"find . -name x -exec git push -f {} \;",
    "for r in a b; do git push -f $r; done",
    "case $x in a) git push -f;; esac",
    "git submodule foreach git push -f",
    "git submodule foreach --recursive 'git push --force'",
    'echo "x << y"\ngit push --force\ny',
    "git status\ngit push -f",
    # shell dentro de shell
    'bash -c "git push -f"',
    "bash -lc 'git push --force origin main'",
    "sh -c 'cd x && git push -f'",
    'cmd /c "git push -f"',
    "cmd.exe //c git push -f",
    'powershell -NoProfile -Command "git push -f"',
    "pwsh -c 'git push --force'",
    'eval "git push -f"',
    "wsl -e git push -f",
    "bash <<'EOF'\ngit push -f\nEOF",
]


@pytest.mark.parametrize("comando", PUSH_FORCADO)
def test_push_forcado_e_recusado(comando):
    assert decisao(comando) == vc.DENY


PUSH_FORCADO_PS = [
    "git push --force",
    "& git push -f",
    '& "C:\\Program Files\\Git\\cmd\\git.exe" push -f',
    "$saida = git push --force origin main",
    "Set-Location backend-crm; git push -f",
    "Invoke-Expression 'git push -f'",
    "iex \"git push --force\"",
    "Start-Process git -ArgumentList 'push','-f'",
    'Start-Process -FilePath git -ArgumentList "push --force" -Wait',
    "Invoke-Command -ScriptBlock { git push -f }",
    "powershell -Command { git push -f }",
    "cmd /c git push -f",
    'bash -c "git push -f"',
    "git push `\n  --force",
]


@pytest.mark.parametrize("comando", PUSH_FORCADO_PS)
def test_push_forcado_e_recusado_no_powershell(comando):
    assert decisao(comando, "PowerShell") == vc.DENY


def test_comando_codificado_do_powershell_e_lido():
    b64 = base64.b64encode("git push --force".encode("utf-16-le")).decode()
    assert decisao(f"powershell -EncodedCommand {b64}") == vc.DENY
    assert decisao(f"pwsh -enc {b64}", "PowerShell") == vc.DENY


def test_comando_codificado_ilegivel_pergunta():
    assert decisao("powershell -EncodedCommand !!!nao-e-base64") == vc.ASK


# --------------------------------------------------------------------------
# Railway
# --------------------------------------------------------------------------

RAILWAY_RECUSA = [
    "railway down",
    "railway delete",
    "railway rm",
    "railway remove",
    "railway project delete",
    "railway environment delete staging",
    "railway env delete staging",
    "railway environment staging rm",
    "railway service delete",
    "railway service backend-crm delete",
    "railway service rm",
    "railway -s backend-crm service remove --yes",
    "railway volume delete --volume data --yes",
    "railway volumes delete --volume data",
    "railway volume rm",
    "railway volume remove",
    "railway volume detach",
    "railway volume -v data delete",
    "railway -s backend-crm volume delete",
    "railway volume --service backend-crm detach",
    "railway volume files delete /backup.tar --yes",
    "railway volume file rm /backup.tar",
    "railway volumes delete --help",
    "railway.exe down",
    "RAILWAY down",
    "npx railway down",
    "npx -y @railway/cli down",
    "npx @railway/cli@latest volume delete",
    "cd backend-crm && railway down -y",
    'bash -c "railway down"',
    "railway logs; railway delete",
]


@pytest.mark.parametrize("comando", RAILWAY_RECUSA)
def test_railway_apagar_ou_desligar_e_recusado(comando):
    assert decisao(comando) == vc.DENY


RAILWAY_PERGUNTA = [
    "railway variable list",
    "railway variables",
    "railway vars --help",
    "railway var set A=1",
    "railway variables --set A=1",
    "railway -s backend-crm variable set A=1",
    "railway run python script.py",
    "railway local python script.py",
    "railway ssh",
    "railway shell",
    "railway shell --service backend-crm",
    "railway connect",
    "railway connect postgres",
    "railway up",
    "railway up --detach",
    "railway volume files upload ./backup.tar /backup.tar",
    "railway volume files --volume data upload ./a /a",
    "npx @railway/cli up",
    'powershell -Command "railway up"',
]


@pytest.mark.parametrize("comando", RAILWAY_PERGUNTA)
def test_railway_sensivel_pergunta(comando):
    assert decisao(comando) == vc.ASK


# --------------------------------------------------------------------------
# O que não pode ser travado
# --------------------------------------------------------------------------

LIVRES = [
    "git status",
    "git push",
    "git push origin main",
    "git push -u origin feat/x",
    "git push --set-upstream origin fix/forca-de-vendas",
    "git push --follow-tags",
    "git push --no-verify origin main",
    "git push --dry-run origin main",
    'git push origin "$(git branch --show-current)"',
    'git push -u origin "$BRANCH"',
    "git -C . push origin main",
    "git fetch --force",
    "git checkout -f main",
    "git add -f ficheiro.txt",
    "git branch -f tmp HEAD",
    'git commit -m "docs: explicar que git push --force é recusado"',
    'git commit -m "fix: railway down passa a ser recusado"',
    "git commit -m \"$(cat <<'EOF'\nfeat: verificador\n\n- recusa git push --force e railway down, it's (done)\nEOF\n)\"",
    "cat <<'EOF' > nota.md\ngit push --force\nrailway down\nEOF",
    'echo "git push --force"',
    'grep -rn "git push -f" docs/',
    'grep -rn "railway volume delete" docs/',
    "git log --oneline -5",
    "railway status",
    "railway logs --service backend-crm",
    "railway logs -n 50",
    "railway deployment list",
    "railway service list",
    "railway service status",
    "railway service logs --service backend-crm",
    "railway volume list --json",
    "railway volume files list / --json",
    "railway volume files download /backup.tar ./backup.tar --json",
    "railway whoami",
    "railway --version",
    "python -m pytest backend-crm/tests -q",
    ".venv/Scripts/python.exe -m pytest -k push",
    "npx tsc --noEmit",
    "npm run build",
    "rm -f tmp.txt",
    "bash --version",
    "python --version",
    "ls -la && cd docs && ls",
    "",
]


@pytest.mark.parametrize("comando", LIVRES)
def test_comandos_normais_passam_sem_decisao(comando):
    assert decisao(comando) is None


LIVRES_PS = [
    "git push origin main",
    "$ramo = git branch --show-current",
    "git push -u origin $ramo",
    "Get-ChildItem -Force",
    "Remove-Item -Force tmp.txt",
    'git commit -m "docs: git push --force é recusado"',
    "git commit -m @'\nfix: railway down e git push --force\n'@",
    "railway status",
    "$env:FOO = 'bar'; python -m pytest",
    "Write-Output 'railway down'",
]


@pytest.mark.parametrize("comando", LIVRES_PS)
def test_comandos_normais_passam_sem_decisao_no_powershell(comando):
    assert decisao(comando, "PowerShell") is None


# --------------------------------------------------------------------------
# Formas que não dá para ler com certeza -> perguntar
# --------------------------------------------------------------------------

INCERTOS = [
    "F=--force; git push $F origin main",
    'OPC="-f"; git push "$OPC"',
    "git push origin {+main,dev}",
    "echo --force | xargs git push",
    "echo 'git push --force' | bash",
    "echo 'railway down' | sh",
    'CMD="git push --force"; $CMD',
    'CMD="railway down"; eval "$CMD"',
    "S=push; git $S --force",
    "railway $SUB",
    "S=down; railway $S",
    "railway volume $ACAO",
    "git -c alias.x='push --force' x",
    'git push --force "sem fim',
    "python -c \"import subprocess; subprocess.run(['git', 'push', '--force'])\"",
    "node -e \"require('child_process').execSync('railway down')\"",
    "python <<'EOF'\nimport os\nos.system('git push -f')\nEOF",
]


@pytest.mark.parametrize("comando", INCERTOS)
def test_formas_incertas_perguntam(comando):
    assert decisao(comando) == vc.ASK


# --------------------------------------------------------------------------
# Scripts chamados pelo comando
# --------------------------------------------------------------------------

def test_script_shell_com_push_forcado_e_recusado(tmp_path):
    (tmp_path / "deploy.sh").write_text("#!/bin/bash\nset -e\ngit push --force origin main\n", encoding="utf-8")
    for comando in ("bash deploy.sh", "./deploy.sh", "sh ./deploy.sh", "source deploy.sh", ". deploy.sh"):
        assert decisao(comando, cwd=str(tmp_path)) == vc.DENY, comando


def test_script_e_encontrado_depois_de_cd(tmp_path):
    (tmp_path / "ops").mkdir()
    (tmp_path / "ops" / "limpar.sh").write_text("railway volume delete --volume data\n", encoding="utf-8")
    assert decisao("cd ops && bash limpar.sh", cwd=str(tmp_path)) == vc.DENY


def test_script_powershell_e_lido(tmp_path):
    (tmp_path / "deploy.ps1").write_text("Set-Location x\nrailway up\n", encoding="utf-8")
    assert decisao("powershell -ExecutionPolicy Bypass -File deploy.ps1", cwd=str(tmp_path)) == vc.ASK
    assert decisao(".\\deploy.ps1", "PowerShell", cwd=str(tmp_path)) == vc.ASK


def test_script_python_com_acao_vigiada_pergunta(tmp_path):
    (tmp_path / "publicar.py").write_text(
        'import subprocess\nsubprocess.run(["git", "push", "--force"])\n', encoding="utf-8"
    )
    assert decisao("python publicar.py", cwd=str(tmp_path)) == vc.ASK


def test_script_com_variavel_a_esconder_a_opcao_pergunta(tmp_path):
    (tmp_path / "deploy.sh").write_text("F=--force\ngit push $F origin main\n", encoding="utf-8")
    assert decisao("bash deploy.sh", cwd=str(tmp_path)) == vc.ASK


def test_script_inofensivo_passa(tmp_path):
    (tmp_path / "build.sh").write_text(
        "# nunca usar git push --force aqui\necho 'a publicar'\ngit push origin main\n", encoding="utf-8"
    )
    (tmp_path / "util.py").write_text("# corre no Railway; faz run das migracoes\nprint('ok')\n", encoding="utf-8")
    assert decisao("bash build.sh", cwd=str(tmp_path)) is None
    assert decisao("python util.py", cwd=str(tmp_path)) is None


def test_script_inexistente_nao_decide(tmp_path):
    assert decisao("bash nao-existe.sh", cwd=str(tmp_path)) is None


def test_script_do_package_json_e_lido(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"deploy": "railway up", "build": "vite build"}}), encoding="utf-8"
    )
    assert decisao("npm run deploy", cwd=str(tmp_path)) == vc.ASK
    assert decisao("npm run build", cwd=str(tmp_path)) is None


# --------------------------------------------------------------------------
# Regras de prioridade e contrato do hook
# --------------------------------------------------------------------------

def test_recusar_vence_perguntar():
    assert decisao("railway up && git push -f") == vc.DENY
    assert decisao("git push -f; railway vars") == vc.DENY


def test_nunca_responde_permitir():
    for comando in LIVRES + PUSH_FORCADO + RAILWAY_PERGUNTA + INCERTOS:
        assert decisao(comando) in (None, vc.DENY, vc.ASK)


def correr(entrada: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=entrada.encode("utf-8"), capture_output=True, timeout=30
    )


def entrada(comando, ferramenta="Bash"):
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": ferramenta, "tool_input": {"command": comando}})


def test_hook_recusa_com_json_e_codigo_zero():
    r = correr(entrada("git -C . push --force --dry-run origin HEAD:refs/heads/teste"))
    assert r.returncode == 0
    saida = json.loads(r.stdout)["hookSpecificOutput"]
    assert saida["hookEventName"] == "PreToolUse"
    assert saida["permissionDecision"] == "deny"
    assert "push forçado" in saida["permissionDecisionReason"]


def test_hook_pergunta():
    r = correr(entrada("railway vars --help", "PowerShell"))
    assert r.returncode == 0
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_hook_sem_decisao_nao_escreve_nada():
    r = correr(entrada("git status"))
    assert r.returncode == 0
    assert r.stdout == b""


def test_hook_ignora_outras_ferramentas():
    r = correr(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x"}}))
    assert (r.returncode, r.stdout) == (0, b"")


@pytest.mark.parametrize(
    "invalida",
    ["", "isto nao e json", "[]", json.dumps({"tool_name": "Bash"}), json.dumps({"tool_name": "Bash", "tool_input": {"command": 5}})],
)
def test_hook_falha_fechada_com_entrada_invalida(invalida):
    r = correr(invalida)
    assert r.returncode == 2
    assert b"bloqueado" in r.stderr
