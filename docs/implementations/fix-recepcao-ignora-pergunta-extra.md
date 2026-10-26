# Recepção: pergunta extra da IA substituía o cumprimento

---

**Branch:** `worktree-fix+recepcao-ignora-pergunta-extra` (nome pedido: `fix/recepcao-ignora-pergunta-extra`)
**Status:** Em andamento
**Autonomia:** manual

---

## Motivação

Em produção (Lara, Sensi Vitae, 26/10/2026), "Bom dia, quanto custa a massagem relaxante de 1h?"
recebia como primeira mensagem só "Posso enviar a nossa tabela de preços?", sem cumprimento,
em 2 de 2. A Filha Recepção tinha escrito "Bom dia! Sou a Lara, do Sensi Vitae.".

Causa raiz: a Filha devolvia `should_ask=true` e `question_text="Posso enviar a nossa tabela de
preços?"` (o passo 1 do roteiro das instruções), e `compose_decision_output()` usa
`question_text` antes de `message_text` em todas as rotas. Reproduzido localmente com o
contexto real do Playground de produção: 2 de 3.

---

## Problemas Identificados (estado anterior)

1. **`question_text` vence `message_text` na Recepção (`decision_engine.py:compose_decision_output`)**:
   `question_text = child_result.question_text or child_result.message_text`. O prompt da
   Recepção pede `should_ask: false` e `question_text: ""`, mas nada no código o garantia.

---

## Abordagem

Na rota `recepcao`, a mensagem final usa `message_text` (e só cai em `question_text` se
`message_text` vier vazio). As outras rotas ficam iguais.

---

## Plano de Implementação

### Fase 1: Recepção usa sempre `message_text`

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/decision_engine.py` | `compose_decision_output()`: ordem `message_text` → `question_text` na rota `recepcao` |
| `backend-executors/tests/test_requeue_pending_message_routing.py` | teste com `should_ask=true` + `question_text` na Recepção |
| `docs/architecture/llm-architecture.md` | regra na secção da Filha Recepção |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | (a registar) | Recepção usa sempre `message_text` |

Testes: `backend-executors/tests` com 478 passados.

### Relatório da Fase 1: o que mudou na prática

**Antes:** quando o cliente perguntava um preço logo na primeira mensagem, às vezes a Lara não
cumprimentava e mandava só "Posso enviar a nossa tabela de preços?".
**Agora:** a primeira mensagem é sempre o cumprimento ("Bom dia! Sou a Lara, do Sensi Vitae."),
e a resposta ao preço vem a seguir.

---

## Checks de Validação

### Cenário C1: pergunta de preço na primeira mensagem (contexto real de produção)
- [x] Pipeline completo (`decide()`) com o contexto do Playground de produção (lead 152, reposto no 1.º turno), 6 execuções
- [x] Confirmar: as 6 começam por "Bom dia! Sou a Lara, do Sensi Vitae." (5 só isso, 1 com "Vou ajudar com a sua dúvida.")
- **Validado em:** 26/10/2026. Antes da correção, o mesmo teste dava "Posso enviar a nossa tabela de preços?" em 2 de 3.

### Cenário C2: produção depois do merge
- [⏭️] Repetir no Playground de produção depois do deploy. Fica no relatório pós-merge, porque o deploy só acontece depois da graduação.
