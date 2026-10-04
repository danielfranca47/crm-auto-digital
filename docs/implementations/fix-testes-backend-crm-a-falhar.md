# Corrigir os 18 testes do backend-crm que falham

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
**Origem:** este item surgiu como "Ajuste possível" na graduação de `fix-limpeza-regras-permitir-sempre.md` (04/10/2026), marcado como urgente pelo utilizador

---

## Motivação

Ao correr a suíte completa do `backend-crm` sobre o código de `main`
(04/10/2026, `python -m pytest tests/ -q`, Python global 3.13.1), o resultado
foi **224 aprovados e 18 falhados**. O resultado é igual a partir da raiz do
repositório e a partir da pasta `backend-crm`.

Uma suíte que falha sempre deixa de avisar: uma regressão nova fica escondida
no meio de falhas já conhecidas, e os testes automáticos deixam de servir de
portão para o que entra em `main`.

Comportamento desejado: a suíte do `backend-crm` passa por inteiro em `main`,
ou cada falha que reste tem uma razão escrita.

## Área do sistema

Testes que falham, por ficheiro (`backend-crm/tests/`):

| Ficheiro | Falhas |
|---|---|
| `test_whatsapp_group_ignore.py` | 5 |
| `test_start_followup_transition.py` | 5 |
| `test_meeting_management_gate.py` | 4 |
| `test_inbound_orchestrator_flag.py` | 2 |
| `test_lead_delete.py` | 1 |
| `test_outbound_does_not_persist_outcome.py` | 1 |

Sintomas observados, ainda sem diagnóstico:

- Corridos sozinhos, `test_whatsapp_group_ignore.py` e `test_lead_delete.py`
  nem chegam a ser carregados: o primeiro dá
  `ImportError: cannot import name 'Request' from 'fastapi' (unknown location)`,
  o segundo `AttributeError: 'APIRouter' object has no attribute 'get'`. O
  `fastapi` 0.116.2 está instalado no Python global.
- Na suíte completa os mesmos ficheiros são carregados e falham dentro dos
  testes — o comportamento depende de que testes correm antes.
- `backend-crm/.venv` existe mas está vazia; os testes correm com o Python
  global.

Diagnóstico (Plan Mode) ainda não feito — próximo passo é seguir o Passo 0 de
`_guia-documentar-implementacao.md`. A decidir nesse passo:

- Se a causa é dos testes (ex.: um teste que substitui o `fastapi` por uma
  versão de faz-de-conta e afeta os seguintes), do ambiente desta máquina, ou
  do código do backend.
- Se as falhas também acontecem fora desta máquina.
- Se alguma das falhas corresponde a um defeito real em produção nas áreas
  cobertas (grupos de WhatsApp ignorados, início de follow-up, gestão de
  reuniões, apagar lead).
