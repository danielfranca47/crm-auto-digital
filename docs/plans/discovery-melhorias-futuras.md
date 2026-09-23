# Discovery — melhorias futuras

Itens deixados de fora da implementação `feat-discovery-centro-inteligencia.md`
(graduada em 23/09/2026). Processo atual: `docs/discovery/_guia-discovery.md`.

---

## M1 — Rotina semanal automática de discovery

**Prioridade:** MÉDIA

**Problema:** hoje a discovery avança só quando o utilizador ou uma sessão roda os
comandos `/discovery-*`. Investigações ficam paradas em `Levantado` e os gatilhos
de stand-by só são verificados quando alguém roda o `/discovery-status`.

**Proposta:** uma rotina agendada (skill `/schedule`, agente na nuvem) que corre 1x
por semana e:
- aprofunda 1–2 investigações `Levantado` (pela meta mais prioritária em
  `_metas-produto.md`);
- verifica os gatilhos de stand-by e regista a "última verificação" no radar;
- **nunca** aplica vereditos — deixa tudo "Pronta para decisão" para o utilizador.

**Pré-requisitos / cuidados:**
- Usar a discovery à mão algumas vezes antes, para confirmar a qualidade das
  investigações (automatizar um processo não afinado multiplica o erro).
- Adaptar a regra de git do `CLAUDE.md` (sem push automático): um agente na
  nuvem precisa de publicar o trabalho numa branch própria para o utilizador ver.
- Custo contínuo de tokens — definir um teto por execução.
- Leituras de produção exigem autorização explícita (o modo automático bloqueia
  por padrão).
