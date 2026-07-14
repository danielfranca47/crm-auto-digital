# Empacotamento do agent-local v2 (.exe)

**Branch:** *(a definir ao iniciar)*
**Status:** Aguardando Plan Mode

---

## Motivação

Empacotamento é sempre a **última fase do ciclo de uma versão** do agent-local
— ver [`docs/plans/_versionamento-agent-local.md`](../plans/_versionamento-agent-local.md).
A v2 já está totalmente documentada e validada (ver
[`docs/architecture/agent-local-app.md`](../architecture/agent-local-app.md),
"Versão documentada: v2") — o único item pendente do ciclo v2 é gerar
`agent-local.exe`, para que utilizadores finais consigam abrir a app com
duplo clique, sem precisar de Python/venv instalados.

Este item nasceu originalmente como Fase 4 de
`docs/implementations/agent-local-v2-app-standalone.md` (já graduado e
removido) e foi adiado a pedido do utilizador até todos os cenários de teste
das Fases 5–10 estarem validados. Esse pré-requisito está cumprido — por
isso o item sai de `docs/plans/` e entra aqui como próximo a implementar.

---

## Problemas Identificados (estado anterior)

1. **Sem distribuição para utilizador final:** hoje `agent-local` só corre via
   `python main.py` dentro do `.venv` do projecto — inviável para distribuir
   a clientes/utilizadores finais sem conhecimento técnico.

---

## Abordagem (rascunho — a confirmar em Plan Mode)

PyInstaller para gerar um binário Windows único.

| Arquivo | O que muda |
|---|---|
| `agent-local/agent-local.spec` | Novo: PyInstaller spec |
| `agent-local/build.bat` | Novo: script de build Windows |

**Notas:**
- Suporte por ora só Windows — PyInstaller gera binário por plataforma;
  macOS/Linux ficam fora deste item.
- Este rascunho **não substitui o Passo 0 (Plan Mode) obrigatório** de
  `_guia-documentar-implementacao.md` — validar em Plan Mode: dependências
  ocultas (Selenium/ChromeDriver, assets do CustomTkinter), tamanho do
  binário resultante, e comportamento numa máquina limpa sem Python
  instalado, antes de aprovar fases.
