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

---

## M2 — Avisar quando `ai_profile` de teste não configura `qualification_fields`

**Prioridade: BAIXA**

> Contexto: item deixado de fora da graduação de
> `docs/implementations/testes-backend-executors-falhando.md` (31/08/2026).

**Em palavras simples:** desde a mudança "AI Profile como única fonte de
verdade" (commit `13b826a`), um `ai_profile` de teste sem
`qualification_fields` configurado faz `required_fields` ficar `[]`
silenciosamente — sem nenhum erro ou aviso. Isso foi a causa camuflada por
trás de várias falhas de teste na sessão de 31/08/2026 (o teste parecia estar
testando "campo obrigatório faltando", mas na prática nenhum campo era
obrigatório).

**O que precisaria existir:** um fixture de teste compartilhado (ou helper)
em `backend-executors/tests/` que documente esse comportamento explicitamente
— por exemplo, uma função `consultivo_profile(**overrides)` /
`agenda_profile(**overrides)` que já venha com os campos obrigatórios
default preenchidos, para não repetir a mesma descoberta caso a caso em
futuras sessões de debugging.

**Não é urgente** — é uma conveniência de DX para testes futuros, sem
impacto em produção; a suíte atual já está 100% verde sem isso.
