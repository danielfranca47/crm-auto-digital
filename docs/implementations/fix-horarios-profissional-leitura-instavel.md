# A leitura dos horários do profissional pode sair errada e ficar presa

**Branch:** (a criar)
**Status:** Aguardando Plan Mode
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

## Direção da solução (a decidir no Plan Mode)

| # | Opção | Nota |
|---|---|---|
| 1 | Ler 2 vezes e só guardar quando as duas tabelas coincidem (3.ª leitura para desempatar) | Pequeno; custo extra só quando o texto muda |
| 2 | Guardar a tabela no perfil quando o texto é gravado (core), mostrar no ecrã "Horários de atendimento" para o dono confirmar | Visível e editável; mais trabalho (UI + core) |
| 3 | Campo estruturado (grade por profissional/dia) em vez de texto livre | Elimina a leitura pela IA; muda o ecrã e outras contas |

Em qualquer opção: um dia que aparece no texto mas falta na tabela não deve virar "fechado" em
silêncio (ex.: tratar como "sem veredicto" e deixar a Filha decidir pelo texto).

## Área do sistema

- `backend-executors/app/services/professional_hours.py`, `llm_service.py`; opção 2/3 também
  backend-core (`ai_profiles`) e `frontend-crm` (Camada 5 · Apresentação)
- `docs/architecture/agenda.md`, `docs/architecture/pipeline-phases.md`

## Validação

Teste unitário com leituras falsas (uma sem a terça). Bancada `.claude/agentes/sensi-vitae/`:
`p-ruben`, `p-joaquim`, `pos-marcacao` (terça), e o script de medição das leituras (20× o mesmo texto).
