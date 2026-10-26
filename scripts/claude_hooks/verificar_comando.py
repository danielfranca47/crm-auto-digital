"""Verificador de comandos das barreiras duras — hook PreToolUse do Claude Code.

Recebe no stdin o JSON do hook (ferramentas Bash e PowerShell), lê a estrutura
do comando em vez de comparar o início do texto, e responde uma de três coisas:

  recusar    ação proibida (push forçado; apagar ou desligar coisas no Railway)
  perguntar  ação sensível (variáveis, run, shell, connect, ssh, up, envio para
             volume), ou
             forma que não dá para ler com certeza e aparenta uma dessas ações
  nada       segue o fluxo normal (regras de permissão + revisor automático)

Numa sessão da cloud (variável CLAUDE_CODE_REMOTE=true, a rotina da fila
automática) recusa também qualquer `git push` que não seja para uma branch
`claude/…` e os comandos `gh` que alteram o repositório no GitHub. Em sessões
locais essas duas regras não existem.

Nunca responde "permitir". Um erro interno termina com código 2, que bloqueia
o comando em vez de o deixar passar em silêncio.

Teste manual: python scripts/claude_hooks/verificar_comando.py < entrada.json
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys

DENY = "deny"
ASK = "ask"
_INCERTO = "incerto"

_DOC = 'Ver docs/ops/local-dev.md, secção "Modo auto e regras de permissão do Claude Code".'
MOTIVO_PUSH = (
    "Barreira dura do projeto: push forçado (--force, -f, --force-with-lease, --mirror "
    "ou destino a começar por '+') nunca é executado, seja qual for a forma do comando. " + _DOC
)
MOTIVO_RAILWAY_APAGA = (
    "Barreira dura do projeto: comandos do Railway que apagam ou desligam coisas (down, "
    "delete, apagar ambiente ou serviço, apagar ou desanexar volume, apagar ficheiros de "
    "um volume) nunca são executados, seja qual for a forma do comando. " + _DOC
)
MOTIVO_RAILWAY_SENSIVEL = (
    "Ação sensível no Railway (variáveis, run, shell, connect, ssh, up ou envio de "
    "ficheiros para um volume): precisa de confirmação do utilizador. " + _DOC
)
MOTIVO_ALIAS = (
    "O comando define um atalho (alias) de git na própria linha, o que pode esconder um "
    "push forçado: precisa de confirmação do utilizador. " + _DOC
)
MOTIVO_INCERTO = (
    "O comando está escrito de uma forma que o verificador não consegue ler com certeza "
    "e aparenta um push forçado ou uma ação sensível no Railway: precisa de confirmação "
    "do utilizador. " + _DOC
)
MOTIVO_EMBUTIDO = (
    "O script ou código que este comando executa aparenta conter um push forçado ou uma "
    "ação sensível no Railway: precisa de confirmação do utilizador. " + _DOC
)

_DOC_FILA = 'Ver docs/ops/fila-automatica.md, secção "Turno da noite".'
MOTIVO_CLOUD_PUSH = (
    "Sessão na cloud (fila automática): só é executado `git push` para uma branch "
    "`claude/…` escrita por extenso no comando (ex.: git push -u origin claude/<slug>). "
    "Push para `main` ou outra branch, push sem destino, apagar branches e push de todas "
    "as branches nunca são executados. " + _DOC_FILA
)
MOTIVO_CLOUD_GH = (
    "Sessão na cloud (fila automática): comandos `gh` que alteram o repositório no GitHub "
    "(juntar um pull request, `gh api` de escrita, definições, segredos, workflows, "
    "releases) nunca são executados. " + _DOC_FILA
)

_NIVEL_MAX = 6
_TAMANHO_MAX = 512 * 1024
_JANELA = 15

_SHELLS_POSIX = {"bash", "sh", "zsh", "dash", "ksh"}
_SHELLS_PS = {"powershell", "pwsh"}
_INTERPRETES = {"python", "python3", "py", "node", "deno", "bun", "ruby", "perl"}
_EXT_SCRIPT = {".sh", ".bash", ".ps1", ".bat", ".cmd", ".py", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl"}
_PALAVRAS_CONTROLO = {"if", "then", "else", "elif", "do", "while", "until", "!", "time"}
_ATRIBUICOES_PS = {"=", "+=", "-="}

# Invólucros: correm o que vem a seguir. O valor são as opções que levam argumento.
_INVOLUCROS = {
    "env": ("-u", "-C", "--unset", "--chdir"),
    "timeout": ("-s", "-k", "--signal", "--kill-after"),
    "nohup": (),
    "command": (),
    "builtin": (),
    "noglob": (),
    "exec": ("-a",),
    "setsid": (),
    "winpty": (),
    "sudo": ("-u", "-g", "-p", "-C", "-h", "-U", "-r", "-t"),
    "doas": ("-u",),
    "nice": ("-n",),
    "ionice": ("-c", "-n", "-p"),
    "stdbuf": ("-i", "-o", "-e"),
    "xargs": ("-n", "-I", "-P", "-L", "-d", "-s", "-E", "-a"),
    "call": (),
    "wsl": ("-d", "--distribution", "-u", "--user", "--cd"),
}

_GIT_OPCOES_COM_VALOR = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}

_RAILWAY_OPCOES_COM_VALOR = {
    "-s", "--service", "-e", "--environment", "-p", "--project", "-v", "--volume", "--mount-path", "--name",
}
_RAILWAY_ALIAS = {
    "volumes": "volume",
    "env": "environment",
    "projects": "project",
    "variables": "variable",
    "vars": "variable",
    "var": "variable",
    "local": "run",
    "rm": "delete",
    "remove": "delete",
}
_RAILWAY_APAGAR = {"delete", "rm", "remove"}

_PREFIXO_CLOUD = "claude/"
_PUSH_OPCOES_COM_VALOR = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
_PUSH_VARIAS = ("--all", "--branches", "--mirror", "--delete", "--prune")
_GH_OPCOES_COM_VALOR = {"-R", "--repo", "--hostname"}
_GH_ESCRITA = {
    "pr": {"merge"},
    "repo": {"delete", "edit", "rename", "archive", "unarchive", "sync", "deploy-key"},
    "release": {"create", "delete", "edit", "upload", "delete-asset"},
    "workflow": {"run", "enable", "disable"},
    "run": {"rerun", "cancel", "delete"},
    "secret": {"set", "delete", "remove"},
    "variable": {"set", "delete", "remove"},
    "cache": {"delete"},
}
_GH_API_CAMPOS = ("-f", "-F", "--field", "--raw-field", "--input")

_PS_OPCOES_COM_VALOR = (
    "executionpolicy", "windowstyle", "inputformat", "outputformat", "workingdirectory",
    "configurationname", "settingsfile", "version", "psconsolefile", "custompipename",
)
_SAPS_PARAMS = ("filepath", "argumentlist", "wait", "nonewwindow", "passthru", "usenewenvironment", "loaduserprofile")
_SAPS_PARAMS_COM_VALOR = (
    "workingdirectory", "windowstyle", "verb", "credential",
    "redirectstandardoutput", "redirectstandarderror", "redirectstandardinput",
)

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")
_RE_ATRIBUICAO = re.compile(r"^[A-Za-z_]\w*\+?=")
_RE_PONTUACAO = re.compile(r"[\"'`,;\[\](){}]")
_RE_PUSH = re.compile(r"\bpush\b", re.I)
_RE_FORCA = re.compile(r"--for|--mir|(?<![\w-])-[A-Za-z]*f[A-Za-z]*(?![\w-])|(?<![\w+])\+[\w/]")
_RE_GIT = re.compile(r"\bgit\b", re.I)
_RE_RAILWAY = re.compile(r"\brailway\b", re.I)
_RE_GH_ESCRITA = re.compile(r"\bgh\b[^\n;|&]*\b(merge|api)\b", re.I)
_RE_RAILWAY_PALAVRAS = re.compile(
    r"\b(down|delete|rm|remove|detach|variables?|vars?|run|local|shell|connect|ssh|up|upload)\b", re.I
)


class _Ilegivel(Exception):
    """O texto não dá para separar em comandos (aspas ou parênteses sem fim)."""


class _Token(str):
    """Pedaço de comando já sem aspas. `dinamico`: contém variável ou substituição."""

    dinamico = False


def _token(texto: str, dinamico: bool = False) -> _Token:
    t = _Token(texto)
    t.dinamico = dinamico
    return t


def _din(t: str) -> bool:
    return getattr(t, "dinamico", False)


def _nome_base(t: str, minusculas: bool = True) -> str:
    """`"C:\\Program Files\\Git\\cmd\\git.exe"` -> `git`."""
    nome = t.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if minusculas:
        nome = nome.lower()
    for ext in (".exe", ".cmd", ".bat", ".com"):
        if nome.lower().endswith(ext):
            return nome[: -len(ext)]
    return nome


def _extensao(t: str) -> str:
    return os.path.splitext(t.lower())[1]


def _sem_opcoes(tokens: list, com_valor: tuple = ()) -> list:
    i = 0
    while i < len(tokens) and tokens[i].startswith("-"):
        if tokens[i] == "--":
            i += 1
            break
        i += 2 if tokens[i] in com_valor else 1
    return tokens[i:]


def _prefixo_de(nome: str, candidatos: tuple, minimo: int = 2) -> bool:
    """PowerShell aceita o nome do parâmetro abreviado (`-Arg` por `-ArgumentList`)."""
    return len(nome) >= minimo and any(c.startswith(nome) for c in candidatos)


# --------------------------------------------------------------------------
# Regras por programa
# --------------------------------------------------------------------------

def _forca(a: str) -> bool:
    """O argumento de `git push` força a reescrita do remoto?"""
    if a.startswith("--"):
        nome = a.split("=", 1)[0].lower()
        # git aceita opções longas abreviadas (--forc, --mir)
        return nome.startswith("--for") or (len(nome) > 2 and "--mirror".startswith(nome))
    if a.startswith("-") and len(a) > 1:
        for ch in a[1:]:
            if ch == "f":
                return True
            if ch == "o" or not ch.isalnum():  # -o <valor>: o resto já é o valor
                return False
        return False
    return a.startswith("+") and len(a) > 1


def _git(args: list, incerto: bool = False):
    """Decisão para `git <args>`: (DENY|ASK|_INCERTO, motivo) ou None."""
    i = 0
    atalho = False
    while i < len(args):
        a = args[i]
        if a in _GIT_OPCOES_COM_VALOR:
            if a in ("-c", "--config-env") and i + 1 < len(args) and args[i + 1].lower().startswith("alias."):
                atalho = True
            i += 2
            continue
        if a.lower().startswith("--config-env=alias."):
            atalho = True
        if not a.startswith("-"):
            break
        i += 1
    if atalho:
        return ASK, MOTIVO_ALIAS
    if i >= len(args):
        return None
    if _din(args[i]):
        return _INCERTO, "sub"
    if args[i].lower() != "push":
        return None
    resto = args[i + 1:]
    if any(_forca(a) for a in resto):
        return DENY, MOTIVO_PUSH
    if incerto or any(_din(a) for a in resto):
        return _INCERTO, "push"
    return None


def _railway(args: list, incerto: bool = False):
    """Decisão para `railway <args>`: (DENY|ASK, motivo) ou None."""
    pos = []
    i = 0
    while i < len(args):
        a = args[i]
        if a.lower() in _RAILWAY_OPCOES_COM_VALOR:
            i += 2
            continue
        if not a.startswith("-"):
            pos.append(a)
        i += 1
    if not pos:
        return (ASK, MOTIVO_INCERTO) if incerto else None
    if _din(pos[0]):
        return ASK, MOTIVO_INCERTO
    p0 = _RAILWAY_ALIAS.get(pos[0].lower(), pos[0].lower())
    resto = {p.lower() for p in pos[1:]}
    resto_incerto = incerto or any(_din(p) for p in pos[1:])

    if p0 in ("down", "delete"):
        return DENY, MOTIVO_RAILWAY_APAGA
    if p0 in ("environment", "project", "service"):
        if resto & _RAILWAY_APAGAR:
            return DENY, MOTIVO_RAILWAY_APAGA
        return (ASK, MOTIVO_INCERTO) if resto_incerto else None
    if p0 == "volume":
        if resto & {"files", "file"}:
            if resto & _RAILWAY_APAGAR:
                return DENY, MOTIVO_RAILWAY_APAGA
            if "upload" in resto:
                return ASK, MOTIVO_RAILWAY_SENSIVEL
        elif resto & (_RAILWAY_APAGAR | {"detach"}):
            return DENY, MOTIVO_RAILWAY_APAGA
        return (ASK, MOTIVO_INCERTO) if resto_incerto else None
    if p0 in ("variable", "run", "shell", "connect", "ssh", "up"):
        return ASK, MOTIVO_RAILWAY_SENSIVEL
    return None


def _ramo_atual(base: str):
    """Branch atual, lida de `.git/HEAD` a subir desde `base`; None se não der para saber."""
    pasta = os.path.abspath(base)
    while True:
        marca = os.path.join(pasta, ".git")
        try:
            if os.path.isfile(marca):  # worktree: o ficheiro aponta para a pasta verdadeira
                with open(marca, encoding="utf-8") as f:
                    linha = f.read().strip()
                if not linha.startswith("gitdir:"):
                    return None
                marca = os.path.join(pasta, linha[len("gitdir:"):].strip())
            if os.path.isdir(marca):
                with open(os.path.join(marca, "HEAD"), encoding="utf-8") as f:
                    cabeca = f.read().strip()
                prefixo = "ref: refs/heads/"
                return cabeca[len(prefixo):] if cabeca.startswith(prefixo) else None
        except OSError:
            return None
        acima = os.path.dirname(pasta)
        if acima == pasta:
            return None
        pasta = acima


def _git_cloud(args: list, base: str, incerto: bool = False):
    """Na cloud, `git push` só para `claude/…`: (DENY|_INCERTO, motivo) ou None."""
    i = 0
    while i < len(args):
        a = args[i]
        if a in _GIT_OPCOES_COM_VALOR:
            if a == "-C" and i + 1 < len(args):
                base = os.path.join(base, _caminho(args[i + 1]))
            i += 2
            continue
        if not a.startswith("-"):
            break
        i += 1
    if i >= len(args):
        return None
    if _din(args[i]):
        return _INCERTO, "sub"
    if args[i].lower() != "push":
        return None
    resto = args[i + 1:]
    if incerto or any(_din(a) for a in resto):
        return DENY, MOTIVO_CLOUD_PUSH
    pos = []
    j = 0
    while j < len(resto):
        a = resto[j]
        if a == "--":
            pos += resto[j + 1:]
            break
        if a.startswith("--"):
            nome = a.split("=", 1)[0].lower()
            if len(nome) > 2 and any(v.startswith(nome) for v in _PUSH_VARIAS):
                return DENY, MOTIVO_CLOUD_PUSH
        elif a.startswith("-") and len(a) > 1:
            if "d" in a[1:].split("o", 1)[0]:  # -d apaga; depois de -o já é o valor
                return DENY, MOTIVO_CLOUD_PUSH
        else:
            pos.append(a)
            j += 1
            continue
        j += 2 if a in _PUSH_OPCOES_COM_VALOR else 1
    destinos = pos[1:]  # pos[0] é o remoto
    if not destinos:  # sem destino, quem decide é a configuração do git
        return DENY, MOTIVO_CLOUD_PUSH
    for ref in destinos:
        origem, separador, destino = ref.lstrip("+").partition(":")
        if separador and not origem:  # `:branch` apaga a branch no remoto
            return DENY, MOTIVO_CLOUD_PUSH
        ramo = destino if separador else origem
        if ramo.startswith("refs/heads/"):
            ramo = ramo[len("refs/heads/"):]
        if ramo in ("HEAD", "@"):
            ramo = _ramo_atual(base) or ""
        if not ramo.startswith(_PREFIXO_CLOUD) or len(ramo) == len(_PREFIXO_CLOUD):
            return DENY, MOTIVO_CLOUD_PUSH
    return None


def _gh_api_escreve(args: list) -> bool:
    metodo = None
    campos = False
    for i, a in enumerate(args):
        minus = a.lower()
        if a in ("-X", "--method"):
            metodo = args[i + 1].upper() if i + 1 < len(args) else "?"
        elif minus.startswith("--method="):
            metodo = a.split("=", 1)[1].upper()
        elif a.startswith("-X") and len(a) > 2:
            metodo = a[2:].upper()
        elif a in _GH_API_CAMPOS or minus.startswith(("--field=", "--raw-field=", "--input=")):
            campos = True
        elif len(a) > 2 and a[:2] in ("-f", "-F"):
            campos = True
    if metodo is not None:
        return metodo not in ("GET", "HEAD")
    return campos  # com campos e sem método, o `gh api` envia um POST


def _gh_cloud(args: list, incerto: bool = False):
    """Na cloud, `gh` não altera o repositório: (DENY, motivo) ou None."""
    pos = []
    i = 0
    while i < len(args) and len(pos) < 2:
        a = args[i]
        if a in _GH_OPCOES_COM_VALOR:
            i += 2
            continue
        if not a.startswith("-"):
            pos.append(a)
        i += 1
    if not pos:
        return None
    if incerto or any(_din(p) for p in pos):
        return DENY, MOTIVO_CLOUD_GH
    grupo = pos[0].lower()
    if grupo == "api":
        return (DENY, MOTIVO_CLOUD_GH) if _gh_api_escreve(args) else None
    if len(pos) > 1 and pos[1].lower() in _GH_ESCRITA.get(grupo, ()):
        return DENY, MOTIVO_CLOUD_GH
    return None


def _procura_solta_cloud(texto: str, base: str):
    """O mesmo que `_procura_solta`, para as duas regras das sessões da cloud."""
    for linha in texto.splitlines():
        palavras = _RE_PONTUACAO.sub(" ", linha).split()
        for i, palavra in enumerate(palavras):
            nome = _nome_base(palavra, minusculas=False)
            resto = palavras[i + 1:i + 1 + _JANELA]
            if nome == "git":
                r = _git_cloud(resto, base)
            elif nome == "gh":
                r = _gh_cloud(resto)
            else:
                continue
            if r and r[0] == DENY:
                return r
    return None


def _procura_solta(texto: str) -> bool:
    """Procura as ações vigiadas em texto que não é shell (código, lista de argumentos).

    Só conta o nome em minúsculas, tal como se escreve o comando — "Railway" em
    prosa não é uma chamada à CLI.
    """
    for linha in texto.splitlines():
        palavras = _RE_PONTUACAO.sub(" ", linha).split()
        for i, palavra in enumerate(palavras):
            nome = _nome_base(palavra, minusculas=False)
            resto = palavras[i + 1:i + 1 + _JANELA]
            if nome == "git":
                r = _git(resto)
            elif nome == "railway":
                r = _railway(resto)
            else:
                continue
            if r and r[0] in (DENY, ASK):
                return True
    return False


def _marcas(texto: str) -> bool:
    """Sinais soltos das ações vigiadas, para formas que não dá para ler de todo."""
    if _RE_GIT.search(texto) and _RE_PUSH.search(texto) and _RE_FORCA.search(texto):
        return True
    return bool(_RE_RAILWAY.search(texto) and _RE_RAILWAY_PALAVRAS.search(texto))


# --------------------------------------------------------------------------
# Leitura do texto: separa em comandos simples, respeitando aspas
# --------------------------------------------------------------------------

class _Leitor:
    """Separa o texto de uma shell em segmentos (um comando simples cada).

    `segmentos` junta os de todos os níveis — cadeias, subshells e `$(...)`.
    `heredocs` guarda (palavras do comando que recebe, corpo).
    """

    def __init__(self, texto: str, ps: bool):
        self.t = texto
        self.n = len(texto)
        self.ps = ps
        self.segmentos: list = []
        self.heredocs: list = []

    def ler(self, i: int = 0, aninhado: bool = False) -> int:
        t, n, ps = self.t, self.n, self.ps
        atual: list = []
        buf: list = []
        tem = din = False
        pendentes: list = []
        fundo = 0
        descarta = False  # o próximo token é o destino de um `>`: não é argumento

        def fecha_token():
            nonlocal buf, tem, din, descarta
            if tem:
                if not descarta:
                    atual.append(_token("".join(buf), din))
                descarta = False
            buf, tem, din = [], False, False

        def fecha_segmento():
            nonlocal atual, descarta
            fecha_token()
            descarta = False
            if atual:
                self.segmentos.append(atual)
            atual = []

        while i < n:
            c = t[i]
            if c == "\n" and pendentes:
                fecha_segmento()
                i = self._corpos(i + 1, pendentes)
                pendentes = []
                continue
            if ps and c == "@" and not tem and t[i + 1:i + 2] in ("'", '"'):
                aspa = t[i + 1]
                fim = t.find("\n" + aspa + "@", i + 2)
                if fim == -1:
                    raise _Ilegivel("here-string sem fim")
                corpo = t[i + 2:fim].lstrip("\r\n")
                buf.append(corpo)
                tem = True
                din = din or (aspa == '"' and "$" in corpo)
                i = fim + 3
                continue
            if c == "'":
                fim = t.find("'", i + 1)
                if fim == -1:
                    raise _Ilegivel("aspa simples sem fim")
                buf.append(t[i + 1:fim])
                tem = True
                i = fim + 1
                continue
            if c == '"':
                i, d = self._aspas(i + 1, buf)
                din = din or d
                tem = True
                continue
            if c == "\\" and not ps:
                if i + 1 < n and t[i + 1] != "\n":
                    buf.append(t[i + 1])
                    tem = True
                i += 2
                continue
            if c == "`":
                if ps:  # em PowerShell a crase é o carácter de escape
                    if i + 1 < n and t[i + 1] not in "\r\n":
                        buf.append(t[i + 1])
                        tem = True
                    i += 2
                    continue
                fim = t.find("`", i + 1)
                if fim == -1:
                    raise _Ilegivel("crase sem fim")
                self._aninhar(t[i + 1:fim])
                din = tem = True
                i = fim + 1
                continue
            if c == "$":
                if t[i + 1:i + 2] == "(":
                    i = self.ler(i + 2, aninhado=True)
                    din = tem = True
                    continue
                if t[i + 1:i + 2] == "{":
                    fim = t.find("}", i + 2)
                    if fim == -1:
                        raise _Ilegivel("${ sem fim")
                    buf.append(t[i:fim + 1])
                    din = tem = True
                    i = fim + 1
                    continue
                buf.append(c)
                din = tem = True
                i += 1
                continue
            if c == "#" and not tem:
                fim = t.find("\n", i)
                i = n if fim == -1 else fim
                continue
            if c in " \t\r":
                fecha_token()
                i += 1
                continue
            if c == "<" and not ps and t[i:i + 2] == "<<" and t[i + 2:i + 3] != "<" and t[max(i - 1, 0):i] != "<":
                m = _HEREDOC.match(t, i)
                if m:
                    fecha_token()
                    pendentes.append(([str(x) for x in atual], m.group(2)))
                    i = m.end()
                    continue
            if c == ">":
                # Redirecionamento de saída (`>`, `>>`, `2>`, `>&1`): nem o número do
                # descritor nem o destino são argumentos do comando.
                if tem and not din and "".join(buf).isdigit():
                    buf, tem = [], False
                fecha_token()
                i += 1
                while i < n and t[i] in ">&":
                    i += 1
                descarta = True
                continue
            if c == "<":
                fecha_token()
                i += 1
                continue
            if c == "(":
                fundo += 1
                fecha_segmento()
                i += 1
                continue
            if c == ")":
                fecha_segmento()
                if aninhado and fundo == 0:
                    return i + 1
                fundo = max(0, fundo - 1)
                i += 1
                continue
            if c in "{}" and not ps and (tem or (c == "{" and t[i + 1:i + 2] not in ("", " ", "\t", "\n", "\r"))):
                # expansão de chaves do bash ({a,b}): faz parte do token e gera texto
                buf.append(c)
                din = tem = True
                i += 1
                continue
            if c == "&" and t[i + 1:i + 2] == ">":  # `&>`: redirecionamento, não separador
                fecha_token()
                i += 1
                continue
            if c in "\n;|&{}":
                fecha_segmento()
                i += 1
                continue
            buf.append(c)
            tem = True
            i += 1
        if aninhado:
            raise _Ilegivel("parêntese sem fim")
        fecha_segmento()
        return i

    def _aspas(self, i: int, buf: list):
        """Lê até à aspa dupla que fecha. Devolve (índice a seguir, é dinâmico)."""
        t, n, ps = self.t, self.n, self.ps
        din = False
        while i < n:
            c = t[i]
            if c == '"':
                if ps and t[i + 1:i + 2] == '"':
                    buf.append('"')
                    i += 2
                    continue
                return i + 1, din
            if c == "\\" and not ps and t[i + 1:i + 2] in ("$", "`", '"', "\\", "\n"):
                if t[i + 1] != "\n":
                    buf.append(t[i + 1])
                i += 2
                continue
            if c == "`":
                if ps:
                    if i + 1 < n:
                        buf.append(t[i + 1])
                    i += 2
                    continue
                fim = t.find("`", i + 1)
                if fim == -1:
                    raise _Ilegivel("crase sem fim")
                self._aninhar(t[i + 1:fim])
                din = True
                i = fim + 1
                continue
            if c == "$":
                din = True
                if t[i + 1:i + 2] == "(":
                    i = self.ler(i + 2, aninhado=True)
                    continue
            buf.append(c)
            i += 1
        raise _Ilegivel("aspas sem fim")

    def _aninhar(self, texto: str) -> None:
        sub = _Leitor(texto, self.ps)
        sub.ler()
        self.segmentos += sub.segmentos
        self.heredocs += sub.heredocs

    def _corpos(self, i: int, pendentes: list) -> int:
        """Consome os corpos dos heredocs abertos na linha anterior."""
        t, n = self.t, self.n
        for consumidor, delimitador in pendentes:
            linhas = []
            while i < n:
                fim = t.find("\n", i)
                if fim == -1:
                    fim = n
                linha = t[i:fim]
                i = min(fim + 1, n)
                if linha.strip() == delimitador:
                    break
                linhas.append(linha)
            self.heredocs.append((consumidor, "\n".join(linhas)))
        return i


# --------------------------------------------------------------------------
# Análise
# --------------------------------------------------------------------------

class _Analise:
    def __init__(self, raiz: str, cwd: str | None, cloud: bool = False):
        self.textos = [raiz]  # a raiz, mais scripts lidos e comandos descodificados
        self.bases = [cwd or os.getcwd()]
        self.cloud = cloud  # sessão da cloud: valem também `_git_cloud` e `_gh_cloud`
        self.vistos: set = set()
        self.decisoes: list = []

    def resultado(self):
        for alvo in (DENY, ASK):
            for decisao, motivo in self.decisoes:
                if decisao == alvo:
                    return decisao, motivo
        return None

    def _regista(self, r) -> None:
        if not r:
            return
        decisao, motivo = r
        if decisao == _INCERTO:
            # git com partes que só se conhecem ao executar (variável, xargs)
            sinal = _RE_PUSH if motivo == "sub" else _RE_FORCA
            if self.cloud and any(_RE_PUSH.search(texto) for texto in self.textos):
                decisao, motivo = DENY, MOTIVO_CLOUD_PUSH
            elif not any(sinal.search(texto) for texto in self.textos):
                return
            else:
                decisao, motivo = ASK, MOTIVO_INCERTO
        self.decisoes.append((decisao, motivo))

    def _opaco(self, texto: str = "") -> None:
        """Forma que não dá para ler: pergunta se o texto aparenta uma ação vigiada."""
        alvos = [alvo for alvo in self.textos + [texto] if alvo]
        if any(_procura_solta(alvo) or _marcas(alvo) for alvo in alvos):
            self.decisoes.append((ASK, MOTIVO_INCERTO))
        if self.cloud:
            if any(_RE_GIT.search(alvo) and _RE_PUSH.search(alvo) for alvo in alvos):
                self.decisoes.append((DENY, MOTIVO_CLOUD_PUSH))
            if any(_RE_GH_ESCRITA.search(alvo) for alvo in alvos):
                self.decisoes.append((DENY, MOTIVO_CLOUD_GH))

    def _texto_solto(self, texto: str) -> None:
        if _procura_solta(texto):
            self.decisoes.append((ASK, MOTIVO_EMBUTIDO))
        if self.cloud:
            self._regista(_procura_solta_cloud(texto, self.bases[-1]))

    def comando(self, texto: str, ps: bool, nivel: int = 0) -> None:
        if nivel > _NIVEL_MAX:
            self._opaco(texto)
            return
        leitor = _Leitor(texto, ps)
        try:
            leitor.ler()
        except _Ilegivel:
            self._opaco(texto)
            return
        for consumidor, corpo in leitor.heredocs:
            nomes = {_nome_base(p) for p in consumidor}
            if nomes & _SHELLS_POSIX:
                self.comando(corpo, False, nivel + 1)
            elif nomes & _SHELLS_PS:
                self.comando(corpo, True, nivel + 1)
            elif nomes & _INTERPRETES:
                self._texto_solto(corpo)
        for segmento in leitor.segmentos:
            self._segmento(segmento, ps, nivel)

    def _reanalisa(self, tokens: list, ps: bool, nivel: int) -> None:
        """O resto da linha é um comando: como tokens já separados e como texto."""
        if len(tokens) > 1:
            self._segmento(tokens, ps, nivel + 1)
        self.comando(" ".join(tokens), ps, nivel + 1)

    def _segmento(self, tokens: list, ps: bool, nivel: int) -> None:
        if nivel > _NIVEL_MAX:
            self._opaco(" ".join(tokens))
            return
        tokens = list(tokens)
        incerto = False  # os argumentos chegam de fora do texto (xargs)
        while tokens:
            t = tokens[0]
            nome = _nome_base(t)

            if ps and _din(t) and len(tokens) > 1 and tokens[1] in _ATRIBUICOES_PS:
                tokens = tokens[2:]
                continue
            if _RE_ATRIBUICAO.match(t) or nome in _PALAVRAS_CONTROLO:
                tokens = tokens[1:]
                continue

            if nome in _INVOLUCROS:
                tokens = _sem_opcoes(tokens[1:], _INVOLUCROS[nome])
                if nome == "xargs":
                    incerto = True
                if nome == "timeout":
                    tokens = tokens[1:]  # a duração
                continue
            if nome == "start" and not ps:
                tokens = tokens[1:]
                while tokens and (not tokens[0] or re.match(r"^/[A-Za-z]+$", tokens[0])):
                    tokens = tokens[1:]
                continue
            if nome == "find":
                marcas = [i for i, x in enumerate(tokens) if x in ("-exec", "-execdir", "-ok", "-okdir")]
                if not marcas:
                    return
                tokens = tokens[marcas[0] + 1:]
                incerto = True
                continue
            if nome in ("npx", "bunx", "pnpx") or (
                nome in ("npm", "pnpm", "yarn", "bun") and len(tokens) > 1 and tokens[1].lower() in ("exec", "dlx", "x")
            ):
                tokens = self._npx(tokens[1:] if nome in ("npx", "bunx", "pnpx") else tokens[2:], nivel)
                continue

            if nome in ("npm", "pnpm", "yarn", "bun") and len(tokens) > 2 and tokens[1].lower() in ("run", "run-script"):
                self._script_npm(tokens[2], nivel)
                return

            if nome == "git":
                self._regista(_git(tokens[1:], incerto))
                if self.cloud:
                    self._regista(_git_cloud(tokens[1:], self.bases[-1], incerto))
                if "foreach" in tokens:  # git submodule foreach <comando>
                    resto = _sem_opcoes(tokens[tokens.index("foreach") + 1:])
                    if resto:
                        self._reanalisa(resto, False, nivel)
            elif nome == "railway":
                self._regista(_railway(tokens[1:], incerto))
            elif nome == "gh" and self.cloud:
                self._regista(_gh_cloud(tokens[1:], incerto))
            elif nome in _SHELLS_POSIX:
                self._shell_posix(tokens[1:], nivel)
            elif nome in _SHELLS_PS:
                self._shell_ps(tokens[1:], nivel)
            elif nome == "cmd":
                self._cmd(tokens[1:], nivel)
            elif nome == "eval":
                self._reanalisa(tokens[1:], False, nivel)
            elif nome in ("invoke-expression", "iex"):
                self._reanalisa([x for x in tokens[1:] if x.lower() != "-command"], True, nivel)
            elif nome in ("start-process", "saps") or (ps and nome == "start"):
                self._start_process(tokens[1:], nivel)
            elif nome in ("source", "."):
                if len(tokens) > 1:
                    self._script(tokens[1], nivel, shell=True)
            elif nome in _INTERPRETES:
                self._interprete(tokens[1:], nivel)
            elif nome in ("cd", "pushd", "chdir", "set-location", "sl") and len(tokens) > 1:
                self.bases.append(os.path.join(self.bases[-1], _caminho(tokens[-1])))
            elif _extensao(t) in _EXT_SCRIPT:
                self._script(t, nivel)
            elif _din(t):
                self._opaco()
            return

    def _npx(self, resto: list, nivel: int) -> list:
        i = 0
        while i < len(resto) and resto[i].startswith("-"):
            opcao = resto[i]
            if opcao == "--":
                i += 1
                break
            if opcao in ("-c", "--call") and i + 1 < len(resto):
                self.comando(resto[i + 1], False, nivel + 1)
            i += 2 if opcao in ("-c", "--call", "-p", "--package") else 1
        resto = resto[i:]
        if resto and re.match(r"@railway/cli(@|$)", resto[0].lower()):
            resto = [_token("railway")] + resto[1:]
        return resto

    def _shell_posix(self, args: list, nivel: int) -> None:
        i = 0
        while i < len(args) and args[i][:1] in ("-", "+"):
            a = args[i]
            if not a.startswith("--") and "c" in a[1:]:  # -c, -lc, -ic
                if i + 1 < len(args):
                    self.comando(args[i + 1], False, nivel + 1)
                else:
                    self._opaco()
                return
            if a == "-s":
                break
            i += 2 if a in ("-o", "-O", "--rcfile", "--init-file") else 1
        else:
            if i < len(args):
                self._script(args[i], nivel, shell=True)
                return
        self._opaco()  # lê os comandos do stdin

    def _shell_ps(self, args: list, nivel: int) -> None:
        i = 0
        while i < len(args) and args[i].startswith("-"):
            nome = args[i].lower().lstrip("-")
            if nome and "command".startswith(nome):
                resto = args[i + 1:]
                if not resto or resto == ["-"]:
                    self._opaco()
                else:
                    self._reanalisa(resto, True, nivel)
                return
            if nome == "ec" or (nome and "encodedcommand".startswith(nome)):
                self._codificado(args[i + 1] if i + 1 < len(args) else "", nivel)
                return
            if nome and "file".startswith(nome):
                if i + 1 < len(args):
                    self._script(args[i + 1], nivel)
                return
            com_valor = nome in ("ex", "ep", "w", "wd", "o", "if", "of") or _prefixo_de(nome, _PS_OPCOES_COM_VALOR)
            i += 2 if com_valor else 1
        resto = args[i:]
        if not resto:
            self._opaco()
            return
        if _extensao(resto[0]) == ".ps1":
            self._script(resto[0], nivel)
        self._reanalisa(resto, True, nivel)

    def _codificado(self, b64: str, nivel: int) -> None:
        try:
            texto = base64.b64decode(b64, validate=True).decode("utf-16-le")
        except (ValueError, UnicodeDecodeError):
            self.decisoes.append((ASK, MOTIVO_INCERTO))
            return
        self.textos.append(texto)
        self.comando(texto, True, nivel + 1)

    def _cmd(self, args: list, nivel: int) -> None:
        for i, a in enumerate(args):
            if a.lower() in ("/c", "/k", "//c", "//k"):
                if args[i + 1:]:
                    self._reanalisa(args[i + 1:], False, nivel)
                return
        self._opaco()

    def _start_process(self, args: list, nivel: int) -> None:
        partes = []
        i = 0
        while i < len(args):
            a = args[i]
            parametro = a.lower()[1:] if a.startswith("-") else ""
            if _prefixo_de(parametro, _SAPS_PARAMS_COM_VALOR):
                i += 2
                continue
            if not _prefixo_de(parametro, _SAPS_PARAMS):
                partes += [_token(p, _din(a)) for p in a.replace(",", " ").split()]
            i += 1
        if partes:
            self._segmento(partes, False, nivel + 1)

    def _interprete(self, args: list, nivel: int) -> None:
        i = 0
        while i < len(args):
            a = args[i]
            if a in ("-c", "-e", "--eval", "-p", "--print") and i + 1 < len(args):
                self._texto_solto(args[i + 1])  # código escrito na própria linha
                return
            if a == "-m":
                return  # módulo instalado, não um ficheiro do projeto
            if a == "-":
                break
            if not a.startswith("-"):
                for candidato in args[i:i + 2]:
                    self._script(candidato, nivel)
                return
            i += 2 if a in ("-X", "-W", "-r", "--require", "--import", "--loader") else 1
        self._opaco()  # sem ficheiro: o código chega pelo stdin

    def _script(self, caminho: str, nivel: int, shell: bool = False) -> None:
        """Lê o script que o comando executa e procura as mesmas ações lá dentro."""
        if _din(caminho):
            self._opaco()
            return
        ficheiro = self._resolve(caminho)
        if ficheiro is None:
            return
        chave = os.path.normcase(os.path.abspath(ficheiro))
        if chave in self.vistos:
            return
        self.vistos.add(chave)
        try:
            if os.path.getsize(ficheiro) > _TAMANHO_MAX:
                return
            with open(ficheiro, "rb") as f:
                bruto = f.read()
        except OSError:
            return
        codificacao = "utf-16" if bruto[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
        conteudo = bruto.decode(codificacao, errors="replace")
        self.textos.append(conteudo)
        ext = _extensao(caminho)
        if ext == ".ps1":
            self.comando(conteudo, True, nivel + 1)
        elif shell or ext in (".sh", ".bash", ".bat", ".cmd"):
            self.comando(conteudo, False, nivel + 1)
        else:
            self._texto_solto(conteudo)

    def _script_npm(self, nome: str, nivel: int) -> None:
        """`npm run <nome>`: analisa o comando guardado no package.json."""
        comando = None
        ficheiro = self._resolve("package.json")
        if ficheiro is not None:
            try:
                with open(ficheiro, encoding="utf-8") as f:
                    comando = json.load(f).get("scripts", {}).get(nome)
            except (OSError, ValueError, AttributeError):
                pass
        if isinstance(comando, str):
            self.textos.append(comando)
            self.comando(comando, False, nivel + 1)
        else:
            self._script(nome, nivel)  # `bun run ficheiro.ts`

    def _resolve(self, caminho: str) -> str | None:
        caminho = _caminho(caminho)
        if os.path.isabs(caminho):
            candidatos = [caminho]
        else:
            candidatos = [os.path.join(base, caminho) for base in reversed(self.bases)]
        for candidato in candidatos:
            if os.path.isfile(candidato):
                return candidato
        return None


def _caminho(caminho: str) -> str:
    caminho = os.path.expanduser(caminho)
    m = re.match(r"^/([A-Za-z])/(.*)", caminho)  # /c/pasta do Git Bash
    if m and os.name == "nt":
        return f"{m.group(1)}:/{m.group(2)}"
    return caminho


def avaliar(comando: str, ferramenta: str = "Bash", cwd: str | None = None, cloud: bool = False):
    """Devolve (DENY|ASK, motivo), ou None quando não há nada a dizer."""
    analise = _Analise(comando, cwd, cloud)
    analise.comando(comando, ps=(ferramenta == "PowerShell"))
    return analise.resultado()


def main() -> int:
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        dados = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
        ferramenta = dados.get("tool_name")
        if ferramenta not in ("Bash", "PowerShell"):
            return 0
        comando = dados["tool_input"]["command"]
        if not isinstance(comando, str):
            raise TypeError("tool_input.command não é texto")
        cloud = os.environ.get("CLAUDE_CODE_REMOTE", "").strip().lower() == "true"
        resultado = avaliar(comando, ferramenta, dados.get("cwd"), cloud)
    except Exception as erro:  # falha fechada: na dúvida, bloqueia
        sys.stderr.write(
            "verificar_comando: erro interno, comando bloqueado por segurança "
            f"({type(erro).__name__}: {erro})\n"
        )
        return 2
    if resultado:
        decisao, motivo = resultado
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decisao,
                    "permissionDecisionReason": motivo,
                }
            },
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
