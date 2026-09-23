# Cobertura e medição da regra "admitir que não sabe"

**Status:** Levantado
**Origem:** `levantamentos/2026-09-23-busca-vetorial-gemini.txt` — recomendação do Gemini: obrigar o agente a admitir desconhecimento; relato do utilizador: "às vezes, sim, ele alucina"
**Meta ligada:** M2 — O agente responde certo e não perde leads
**Área do sistema:** backend-executors (decision_engine), backend-crm (registo de handoff)

---

## Pergunta a responder

A regra "quando não souber, não invente" está presente em todas as fases do agente, e
temos forma de saber quando ele inventou ou quando pediu ajuda à equipa?

## O que já se sabe

- A regra existe: `_ESCAPE_HATCH_BLOCK` (`decision_engine.py:140`) manda devolver
  `confidence < 0.5`, perguntar em vez de inventar, e em perguntas técnicas fora do
  conhecimento dizer "Vou confirmar essa informação com a equipa" com
  `handoff_requested = true`.
- É injetada nas filhas de qualificação, apresentação, follow-up e fecho
  (`decision_engine.py:2988`, `3616`, `3965`, `4086`). **Não verificado:** recepção e
  pré-agendamento.
- Também há regras "NUNCA prometa descontos… não presentes em knowledge_items"
  (`decision_engine.py:2982`).
- **Não se sabe** se há métrica/painel de quantas vezes o escape hatch dispara, nem
  forma de detetar alucinação depois do facto. Há também o risco de ele disparar
  **demais** quando a informação existe mas não foi carregada na fase (ver
  `conhecimento-fora-fase-apresentacao.md` e
  `docs/implementations/fix-categorias-conhecimento-orfas.md`).
