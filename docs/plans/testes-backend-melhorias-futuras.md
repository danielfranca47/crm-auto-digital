# Testes de Backend — Melhorias Futuras

> Contexto: itens deixados de fora da graduação de
> `docs/implementations/uazapi-backoff-e164.md` (23/08/2026).

---

## M1 — Corrigir teardown de SQLite temporário no Windows

**Prioridade: BAIXA**

**Em palavras simples:** dois testes pré-existentes do `backend-core`
(`test_ai_profile_agent_mode.py`, `test_ai_profile_timezone_persistence.py`)
falham no Windows com `PermissionError: [WinError 32] O arquivo já está
sendo usado por outro processo` ao tentar remover (`os.remove`) o banco
SQLite temporário criado no `setUp`. A causa provável é a engine SQLAlchemy
do teste não ser encerrada (`engine.dispose()`) antes do `os.remove` — no
Linux isso normalmente não trava, no Windows sim.

**O que precisaria existir:** garantir `engine.dispose()` (ou equivalente)
antes de remover o arquivo temporário nesses testes, e auditar se o mesmo
padrão aparece em outros testes do `backend-core` que criam SQLite
temporário.

**Não é urgente** — os testes falham só nesse passo de limpeza (o teardown),
não na asserção em si; não bloqueia verificação de mudanças de produto, só
polui a saída da suíte completa no Windows.
