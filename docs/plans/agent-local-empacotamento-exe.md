# Empacotamento do agent-local (.exe)

**Versão-alvo: v3.** A v2 do agent-local está documentada em
[`docs/architecture/agent-local-app.md`](../architecture/agent-local-app.md).

> Contexto: item retirado de `docs/implementations/agent-local-v2-app-standalone.md`
> (Fase 4). Adiado a pedido do utilizador — não faz sentido empacotar um .exe
> antes de todos os cenários de teste do app standalone (Fases 5–10) estarem
> validados. Retomar só depois disso.

## M1 — Empacotamento PyInstaller (.exe)

**Prioridade: MÉDIA**

**Objetivo:** `agent-local.exe` funciona numa máquina limpa com duplo clique.

| Arquivo | O que muda |
|---|---|
| `agent-local/agent-local.spec` | Novo: PyInstaller spec |
| `agent-local/build.bat` | Novo: script de build Windows |

**Notas:**
- Suporte por ora só Windows — PyInstaller gera binário por plataforma; macOS/Linux ficam fora deste item.
- Pré-requisito: todos os cenários de teste pendentes de `agent-local-v2-app-standalone.md` (Fases 5–10) validados primeiro.
