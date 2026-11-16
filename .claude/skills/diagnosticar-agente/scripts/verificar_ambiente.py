"""Checklist do PC antes de configurar um agente — primeiro passo da skill no modo colaborador.

Uso: python verificar_ambiente.py
Escreve cada verificação em linguagem simples (✅ / ❌ + o que fazer) e termina com o modo a usar:
  MODO=dono         → há Railway neste PC (bancada local e transporte railway disponíveis)
  MODO=colaborador  → sem Railway: tudo pelas rotas públicas com a conta de teste do login
Sai com código 1 se faltar alguma coisa que impeça o modo colaborador.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).parent
REPO = AQUI.parents[3]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=60).stdout.strip()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(AQUI))
    falta = False

    # 1. projeto atualizado
    buscou = subprocess.run(["git", "fetch", "--quiet", "origin"], cwd=REPO, capture_output=True, timeout=60).returncode == 0
    if buscou and (atras := git("rev-list", "--count", "HEAD..origin/main")):
        if atras != "0":
            print(f"❌ O projeto está {atras} atualização(ões) atrás. Correr: git pull (na pasta do projeto)")
            falta = True
        else:
            print("✅ Projeto atualizado")
    else:
        print("⚠️ Não consegui confirmar se o projeto está atualizado (sem ligação ao GitHub?)")

    # 2. modo
    # DIAG_MODO_COLABORADOR=1 força o modo colaborador (para o dono experimentar como um colega)
    dono = shutil.which("railway") is not None and not os.getenv("DIAG_MODO_COLABORADOR")
    print("ℹ️ Railway encontrado neste PC" if dono else "ℹ️ Sem Railway neste PC — modo colaborador")

    # 3. conta de teste
    import prod_http
    try:
        conta = prod_http.executar({"agente": {}}, {"acao": "conta"})
        print(f"✅ Login na conta de teste ({prod_http.acesso()['email']}, conta {conta['user_id']})")
        if conta["subscription_status"] != "active":
            print("❌ A conta de teste não tem plano ativo. Pedir ao Daniel o plano Interno.")
            falta = True
        else:
            print(f"✅ Plano ativo: {', '.join(p for p in conta['planos'] if p)}")
        print("✅ AI Profile já existe" if conta["ai_profile_id"]
              else "ℹ️ A conta ainda não tem AI Profile — a skill cria-o na primeira configuração")
    except prod_http.AcessoErro as e:
        print(f"❌ {e}")
        falta = True
    except Exception as e:  # rede, servidor em baixo
        print(f"❌ Não consegui falar com o sistema: {e}")
        falta = True

    print(f"MODO={'dono' if dono else 'colaborador'}")
    return 1 if falta and not dono else 0


if __name__ == "__main__":
    sys.exit(main())
