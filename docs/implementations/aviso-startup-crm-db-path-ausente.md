# Aviso no arranque se CRM_DB_PATH estiver ausente em produção

**Branch:** *(a definir ao iniciar)*
**Status:** Aguardando Plan Mode

---

## Motivação

Este item surgiu como "Ajuste possível" na graduação de
`docs/implementations/persistencia-banco-dados-producao.md` (feature já
graduada — ver [`docs/architecture/_mapa-sistema.md`](../architecture/_mapa-sistema.md#persistência-em-produção-railway)).

O `backend-crm` corrigiu a perda de dados em produção ao passar a ler
`CRM_DB_PATH` do ambiente (com fallback para um caminho relativo local,
efémero em produção). O código está correto e a env var está configurada em
produção, mas **nada avisa se essa configuração for removida ou esquecida no
futuro** (ex.: apagada por engano no Railway, ou um novo ambiente/serviço
clonado sem copiar as variáveis) — o sistema simplesmente volta a usar o
caminho efémero em silêncio, exatamente a mesma classe de bug que já causou
perda real de leads em produção, sem nenhum sinal nos logs até alguém notar
dados a desaparecer.

Utilizador validou como item urgente (não-backlog) após a correção do bug
original, para fechar essa lacuna enquanto o contexto ainda está fresco.

---

## Problemas Identificados (estado anterior)

1. **Sem sinal no arranque:** `backend-crm/database.py` — se `CRM_DB_PATH`
   não estiver definida, o código cai silenciosamente no caminho relativo
   local, sem log de aviso, mesmo quando a aplicação está a correr num
   ambiente de produção (Railway injeta `RAILWAY_ENVIRONMENT` — sinal
   disponível para detectar o cenário).

---

## Abordagem (rascunho — a confirmar em Plan Mode)

Validar em Plan Mode:
- Onde emitir o aviso: no arranque de `app.py` (mais visível, um log por
  processo) vs. dentro de `database.py`/`get_connection()` (mais próximo da
  causa, mas arrisca logar em todo request se não houver guarda contra
  repetição).
- Critério de detecção de "ambiente de produção": presença de
  `RAILWAY_ENVIRONMENT` (ou variável equivalente) — confirmar o nome exato
  já usado no projeto (`RAILWAY_ENVIRONMENT_NAME` apareceu nas variáveis
  reais do serviço ao investigar o bug original).
- Nível do aviso: log de erro/warning bem visível (ex.: `logger.error` ou
  `print` com prefixo claro) vs. falhar o arranque (`raise`) — falhar o
  arranque é mais seguro (impossível ignorar) mas também mais arriscado
  (pode derrubar produção por um falso positivo); discutir trade-off.
- Aplicar o mesmo raciocínio ao `backend-core` (`DATABASE_URL`)? Já está
  configurado corretamente hoje, mas sofre do mesmo risco estrutural de
  remoção futura sem aviso — avaliar se entra no mesmo escopo ou fica para
  depois.

**Notas:**
- Este rascunho **não substitui o Passo 0 (Plan Mode) obrigatório** de
  `_guia-documentar-implementacao.md`.
