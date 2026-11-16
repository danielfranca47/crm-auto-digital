# A leitura dos horários do profissional pode sair errada e ficar presa

**Branch:** `worktree-fix+horarios-profissional-leitura-instavel` (pedido: `fix/horarios-profissional-leitura-instavel`)
**Status:** Em andamento
**Autonomia:** manual
**Origem:** bancada do agente Sensi Vitae, c14 local (16/11/2026) — `README.md` da bancada, secção
"16/11/2026 — c14-tipo-perguntas".

---

## Motivação

`professional_hours.get_hours()` pede à IA, **uma vez por texto**, que converta os horários do perfil
(`professional_availability` + `custom_instructions`) numa tabela, e guarda o resultado em memória
(`_CACHE`) até o processo reiniciar. Numa das leituras a IA **saltou a terça-feira da Val**. A partir
daí, todas as conversas da conta ouviram "na terça não temos atendimento", e um caso gravou sábado,
um dia que o cliente nunca pediu, até o serviço ser reiniciado. Medido com o mesmo texto: 52 de 52
leituras certas isoladas, por isso a falha é rara (~1 em 50). Mas, quando acontece, é silenciosa e
afeta todos os clientes daquela conta, em cada processo (Playground e worker do WhatsApp, cada um com
a sua leitura).

## Causa confirmada (16/11/2026)

- `backend-executors/app/services/professional_hours.py`: uma única chamada (`generate_professional_hours`),
  sem verificação de coerência, e o resultado (certo ou errado) fica em `_CACHE[hash do texto]`.
- Log da leitura errada: `event=professional_hours_extracted hash=5fab7b849fec` com `Val` sem `tue`
  (`ambiente/executors-n.log` da bancada).

## Problemas Identificados (estado anterior)

1. **Uma só leitura (`professional_hours.get_hours`):** o texto era lido uma vez e a tabela, certa
   ou errada, ficava em `_CACHE` até reiniciar.
2. **Sem temperatura (`llm_service.generate_professional_hours`):** a chamada ia sem `temperature`
   (padrão do provedor), o que aumenta a variação entre leituras do mesmo texto.

## Abordagem (opção 1 da lista original, decidida no Plan Mode de 16/11/2026)

```
texto do perfil (sem cache)
  → 2 leituras em paralelo (temperature=0)
  ├─ iguais → guarda e usa
  └─ diferentes → 3.ª leitura
       ├─ alguma coincide com outra → guarda e usa essa
       └─ nenhuma coincide → sem tabela (a filha confere pelo texto), NÃO guarda — repete na
          próxima mensagem
```

Leitura que falha (rede, JSON inválido) não conta como voto. Comparação normalizada (a ordem dos
intervalos não conta). Assim, um dia que falta numa leitura isolada perde para as outras duas e
nunca vira "fechado" em silêncio. Opções 2 e 3 (tabela visível no ecrã / grade estruturada) ficam
em "Ajustes Possíveis".

## Plano de Implementação

### Fase 1 — Leitura por consenso

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/services/professional_hours.py` | `_read_once()` (uma leitura), `_majority()` (consenso), `get_hours()` com 2 leituras em paralelo + 3.ª para desempatar; só o acordo fica em cache; logs `reads`/`agreed` e `event=professional_hours_disagreement` |
| `backend-executors/app/services/llm_service.py` | `generate_professional_hours` com `temperature=0` |
| `backend-executors/tests/test_professional_hours.py` | leituras falsas: consenso, uma sem a terça perde, três diferentes ficam sem tabela e repetem, falha não vota, ordem dos intervalos |
| `docs/architecture/pipeline-phases.md`, `docs/prompts_llms.md` | descrição da leitura por consenso |

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `f395c22` | leitura dos horários por consenso + temperature 0 + testes + docs |

### Relatório da Fase 1 — o que mudou na prática

O sistema lê os horários dos terapeutas a partir do texto do perfil com a ajuda da IA. Antes lia uma
vez só: se essa leitura viesse errada (como quando "esqueceu" a terça da Val), o erro ficava guardado
e todos os clientes ouviam "à terça não há atendimento" até o serviço reiniciar. Agora lê duas vezes
ao mesmo tempo (sem demorar mais) e só guarda quando as duas dizem o mesmo; se discordarem, lê uma
terceira para desempatar. Se nem assim houver acordo, não guarda nada e o agente confere pelo texto,
tentando outra vez na mensagem seguinte. Também passou a ler de forma "fria" (sem criatividade), o que
torna as leituras mais iguais entre si.

---

## Checks de Validação

### Cenário U1 — Testes unitários
- [x] `pytest backend-executors/tests` — 531 passaram (16/11/2026; `scripts/` já falhava em `main`)

### Cenário B1 — Bancada: terças da Val aceites
Bancada isolada (código da worktree, portas 8110–8112, snapshot dos bancos de `ambiente/`, perfil
local 5 = c14); segunda 16/11, por isso "amanhã" = terça 17/11. Tentativas `20261116-145x-CONSENSO-*`.
- [x] `p-ruben` (amanhã 11h = terça) — gravado ter 17/11 11h com a Val
- [x] `p-joaquim` (amanhã 11h = terça) — terça 11h aceite com a Val ("depois das 19h" recusado, propôs 16h);
  não chegou a gravar porque o cliente simulado parou no "Posso confirmar?" (redação já conhecida, não é horário)
- [x] `pos-marcacao` — terça 14h gravada; remarcação para qui 19/11 15h gravada; nenhum sábado
- **Validado em:** 16/11/2026

### Cenário B2 — Medição das leituras (20× o texto c14, sem cache)
- [x] 20/20 tabelas com Val seg–sáb 11–17h e Daniel seg–sex 11–19h30; 0 precisaram da 3.ª leitura
  (40 leituras com `temperature=0`, todas iguais)
- **Validado em:** 16/11/2026

### Cenário B3 — Log
- [x] `event=professional_hours_extracted hash=5fab7b849fec reads=2 agreed=true` com Val seg–sáb e
  Daniel seg–sex (mesmo hash do caso original)
- **Validado em:** 16/11/2026

---

## Ajustes Possíveis Pós-Implementação

- Opção 2: guardar a tabela no perfil quando o texto é gravado (core) e mostrá-la no ecrã
  "Horários de atendimento" para o dono confirmar.
- Opção 3: campo estruturado (grade por profissional/dia) em vez de texto livre.
- Rever no WhatsApp real: `railway logs -s "worker backend-executors" | grep professional_hours`.

## Área do sistema

- `backend-executors/app/services/professional_hours.py`, `llm_service.py`; opção 2/3 também
  backend-core (`ai_profiles`) e `frontend-crm` (Camada 5 · Apresentação)
- `docs/architecture/agenda.md`, `docs/architecture/pipeline-phases.md`

## Validação

Teste unitário com leituras falsas (uma sem a terça). Bancada `.claude/agentes/sensi-vitae/`:
`p-ruben`, `p-joaquim`, `pos-marcacao` (terça), e o script de medição das leituras (20× o mesmo texto).
