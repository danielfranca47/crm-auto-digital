"""Categorias que sobem sempre para o utilizador — portão da fila automática.

Olha para o que uma branch alterou em relação à base (ficheiros e linhas) e
responde quais categorias sensíveis foram tocadas. Uma branch que toca em
qualquer uma delas nunca é mergeada pelo agente avaliador: fica à espera da
decisão do utilizador, mesmo com veredito favorável.

  seguranca_agente  regras de permissão e de processo do próprio agente
  pagamento         pagamento e cobrança (Efi, planos, assinaturas, reembolso)
  envio_real        envio real a clientes (WhatsApp, email)
  base_de_dados     estrutura da base de dados (colunas, tabelas, migrações)
  instrucoes_ia     instruções da IA (prompts Mãe/Filha, playbooks, Camada 7)

Código de saída: 0 = nada sobe, 1 = sobe, 2 = erro (quem chama trata como
"sobe" — na dúvida, decide o utilizador).

Uso: python scripts/fila/categorias_que_sobem.py [--base origin/main] [--ramo HEAD] [--json]
Ver docs/ops/fila-automatica.md, secção "O que sobe sempre".
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

NOMES = {
    "seguranca_agente": "Regras de segurança e de processo do próprio agente",
    "pagamento": "Pagamento e cobrança",
    "envio_real": "Envio real a clientes (WhatsApp, email)",
    "base_de_dados": "Estrutura da base de dados",
    "instrucoes_ia": "Instruções da IA (prompts)",
}

# Vale para qualquer ficheiro, incluindo documentação.
_CAMINHO_SEGURANCA = re.compile(
    r"^(\.claude/|\.github/|scripts/claude_hooks/|scripts/fila/"
    r"|docs/ops/fila-automatica\.md$|CLAUDE\.md$)",
    re.IGNORECASE,
)

# As regras abaixo só olham para código: documentação não muda comportamento.
_CAMINHOS = {
    "pagamento": re.compile(
        r"(^|[/_.-])efi([/_.-]|$)|billing|subscription|checkout|assinatura"
        r"|refund|reembolso|payment|pagamento|addon"
        r"|(^|[/_.-])(admin)?plans?([/_.-]|$)",
        re.IGNORECASE,
    ),
    "envio_real": re.compile(
        r"uazapi|whatsapp_send|email_service|smtp|(^|/)core_client\.py$"
        r"|^backend-executors/app/(runners|workers|clients)/",
        re.IGNORECASE,
    ),
    "base_de_dados": re.compile(
        r"(^|/)migrations/|\.sql$|^backend-core/app/(models/|db\.py$|seed\.py$)"
        r"|^backend-crm/(database|models)\.py$",
        re.IGNORECASE,
    ),
    "instrucoes_ia": re.compile(
        r"decision_engine|field_extractor|assistente_ia/llm\.py$|ai_playbooks/"
        r"|meta_prompter|spy_agent/module_|collab_monitor/classifier|sales_flow",
        re.IGNORECASE,
    ),
}

# Linhas alteradas (acrescentadas ou removidas) em código que não é de teste.
_LINHAS = {
    "pagamento": re.compile(r"efi_client|\bEFI_[A-Z_]+|gerencianet", re.IGNORECASE),
    "envio_real": re.compile(
        r"\bsend_(whatsapp\w*|text|media|email|followup_now)\s*\(|\bsmtplib\b"
        r"|whatsapp\.send|email\.send|/send/(text|media)",
        re.IGNORECASE,
    ),
    "base_de_dados": re.compile(
        r"\bensure_column\s*\(|\b(ALTER|DROP|CREATE)\s+(TABLE|(UNIQUE\s+)?INDEX)\b"
        r"|\bADD\s+COLUMN\b|__tablename__|\bColumn\s*\(",
        re.IGNORECASE,
    ),
    "instrucoes_ia": re.compile(r"prompt\w*\s*\+?=(?!=)|\bVocê é\b|\bYou are\b", re.IGNORECASE),
}

_DOCUMENTACAO = re.compile(r"^docs/|\.(md|txt)$", re.IGNORECASE)
_TESTE = re.compile(r"(^|/)tests?/|(^|/)test_[^/]+\.py$|\.(test|spec)\.[jt]sx?$", re.IGNORECASE)


def classificar(ficheiros, linhas=None):
    """Devolve {categoria: [motivos]} para os ficheiros e linhas alterados.

    `ficheiros`: caminhos relativos à raiz do repositório.
    `linhas`: {caminho: [linhas acrescentadas ou removidas]} (opcional).
    """
    linhas = linhas or {}
    encontrados = {}

    def marcar(categoria, motivo):
        motivos = encontrados.setdefault(categoria, [])
        if motivo not in motivos:
            motivos.append(motivo)

    for original in ficheiros:
        caminho = original.replace("\\", "/")
        while caminho.startswith("./"):
            caminho = caminho[2:]
        if _CAMINHO_SEGURANCA.search(caminho):
            marcar("seguranca_agente", caminho)
        if _DOCUMENTACAO.search(caminho):
            continue
        for categoria, padrao in _CAMINHOS.items():
            if padrao.search(caminho):
                marcar(categoria, caminho)
        if _TESTE.search(caminho):
            continue
        for linha in linhas.get(original, []):
            for categoria, padrao in _LINHAS.items():
                if padrao.search(linha):
                    marcar(categoria, f"{caminho}: {linha.strip()[:80]}")

    return {c: encontrados[c] for c in NOMES if c in encontrados}


def ler_diff(texto):
    """Extrai do `git diff -U0` os ficheiros tocados e as linhas alteradas de cada um."""
    ficheiros = []
    linhas = {}
    atuais = []
    no_cabecalho = False
    for linha in texto.splitlines():
        if linha.startswith("diff --git "):
            no_cabecalho = True
            atuais = []
            continue
        if linha.startswith("@@"):
            no_cabecalho = False
            continue
        if no_cabecalho:
            if linha.startswith(("--- ", "+++ ")):
                caminho = linha[4:].strip().strip('"')
                if caminho != "/dev/null":
                    caminho = caminho[2:] if caminho[:2] in ("a/", "b/") else caminho
                    if caminho not in atuais:
                        atuais.append(caminho)
                    if caminho not in ficheiros:
                        ficheiros.append(caminho)
            continue
        if linha[:1] in "+-" and atuais:
            for caminho in atuais:
                linhas.setdefault(caminho, []).append(linha[1:])
    return ficheiros, linhas


def _git(*argumentos):
    resultado = subprocess.run(
        ["git", "-c", "core.quotepath=false", *argumentos],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return resultado.stdout


def avaliar_ramo(base, ramo):
    intervalo = f"{base}...{ramo}"
    nomes = _git("diff", "--no-renames", "--name-only", "-z", intervalo)
    ficheiros = [nome for nome in nomes.split("\0") if nome]
    _, linhas = ler_diff(_git("diff", "--no-renames", "-U0", intervalo))
    return ficheiros, classificar(ficheiros, linhas)


def main(argumentos=None):
    leitor = argparse.ArgumentParser(description="Diz que categorias sensíveis uma branch tocou.")
    leitor.add_argument("--base", default="origin/main")
    leitor.add_argument("--ramo", default="HEAD")
    leitor.add_argument("--json", action="store_true", dest="em_json")
    opcoes = leitor.parse_args(argumentos)

    try:
        ficheiros, categorias = avaliar_ramo(opcoes.base, opcoes.ramo)
    except Exception as erro:  # falha fechada: sem leitura do diff, sobe
        detalhe = getattr(erro, "stderr", None) or str(erro)
        print(f"ERRO ao ler as alterações ({detalhe.strip()}). Tratar como SOBE.", file=sys.stderr)
        return 2

    if opcoes.em_json:
        saida = {
            "sobe": bool(categorias),
            "ficheiros_alterados": len(ficheiros),
            "categorias": [
                {"id": c, "nome": NOMES[c], "motivos": motivos} for c, motivos in categorias.items()
            ],
        }
        print(json.dumps(saida, ensure_ascii=False, indent=2))
    elif categorias:
        print(f"SOBE — {len(categorias)} categoria(s) tocada(s) em {len(ficheiros)} ficheiro(s):")
        for categoria, motivos in categorias.items():
            print(f"- {NOMES[categoria]}")
            for motivo in motivos[:8]:
                print(f"    {motivo}")
            if len(motivos) > 8:
                print(f"    … e mais {len(motivos) - 8}")
    else:
        print(f"NÃO SOBE — {len(ficheiros)} ficheiro(s) alterado(s), nenhuma categoria sensível.")
    return 1 if categorias else 0


if __name__ == "__main__":
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
