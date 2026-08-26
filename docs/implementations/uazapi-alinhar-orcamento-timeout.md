# M3 — Alinhar orçamento de timeout executor → core → UazAPI

**Branch:** `fix/uazapi-alinhar-orcamento-timeout`
**Status:** Todos os cenários validados (26/08/2026)

---

## Motivação

Item M3 de `docs/plans/confiabilidade-integracoes-externas-melhorias-futuras.md`,
deixado de fora da graduação de `uazapi-backoff-e164.md` (23/08/2026).

`backend-executors/app/clients/core_client.py::send_whatsapp_message`
(executor → core, texto) usa `timeout=15.0`; `send_whatsapp_media`
(executor → core, mídia) usa `timeout=20.0`. Mas
`backend-core/app/providers/uazapi_client.py` (core → UazAPI) usa
`timeout=20.0` por tentativa para `send_text` e `timeout=30.0` para
`send_media`, com até 3 tentativas em 429/503 (backoff ~0.5s + ~1s entre
tentativas; timeout/erro de rede não são re-tentados, propagam na hora).
Ou seja, o executor pode desistir antes do core sequer terminar uma única
tentativa lenta-porém-bem-sucedida à UazAPI.

Causa raiz: os dois valores (15s no executor, 20s no core) nasceram já
descasados no mesmo commit `45f4fd1`, sem nenhum comentário justificando os
números.

---

## Problemas Identificados (estado anterior)

1. **Orçamento de timeout descasado:** `core_client.py::send_whatsapp_message`
   (timeout 15s) espera menos que o pior caso realista de
   `uazapi_client.py::send_text` no core (~21.5s, contando retry 429/503).
2. **Mesmo problema em mídia:** `core_client.py::send_whatsapp_media`
   (timeout 20s) espera menos que o pior caso de `send_media` no core
   (~31.5s).
3. **Risco real por trás do descompasso:** `send_whatsapp_message`/
   `send_whatsapp_media` são chamados de dentro de `execute_job()`
   (`backend-executors/app/runners/whatsapp.py`), que roda num loop síncrono
   de polling (`whatsapp_worker.py:50-97`) — não numa requisição HTTP com
   usuário esperando. Um timeout aqui vira `CoreClientError(error_type="network")`,
   tratado como sempre-retryable (`whatsapp.py:432-435`), e o job é
   re-tentado mais tarde. Se o core, entretanto, **completou** o envio na
   UazAPI (mensagem já saiu no WhatsApp) antes do executor desistir, o
   retry do job **duplica o envio da mensagem ao lead**.
4. **Documentado como limitação conhecida e não resolvida:**
   `docs/architecture/whatsapp-send-resiliencia.md`, secção "Limitação de
   timeout conhecida".

---

## Diagnóstico

- Nenhuma outra rota consome `uazapi_client.send_text`/`send_media` além de
  `backend-core/app/api/whatsapp_send.py` (`/whatsapp/send`,
  `/whatsapp/send-media`), e o único chamador dessas rotas é o
  `core_client.py` do executor — não há terceiro orçamento de tempo a
  conciliar.
- O executor roda em loop de polling sequencial (um job por vez,
  `whatsapp_worker.py:95-97`) sem SLA documentado de latência end-to-end
  (não há menção a isso em `followup.md`, `sales-flow.md` ou
  `humanization.md` — só o delay de humanização, que é outra coisa). Uma
  espera ocasional maior por job não tem custo de UX visível a um usuário.
- Abordagem escolhida: **aumentar o timeout do executor**, não diminuir o
  do core→UazAPI — o core→UazAPI (20s/30s) já está em produção paga sem
  relatos de problema; reduzi-lo sem dado real de latência da UazAPI
  arriscaria transformar chamadas lentas-porém-válidas em falsas falhas.

**Cálculo do pior caso no core** (a tentativa final, mais longa possível,
estoura o timeout de tentativa, precedida de duas tentativas rápidas com
erro 429/503 + backoff):
- Texto: até 20s (tentativa final) + ~1.5s (backoff acumulado 0.5+1s) ≈ **21.5s**
- Mídia: até 30s (tentativa final) + ~1.5s ≈ **31.5s**

**Riscos e dependências:**
- Impacto no throughput do worker: como processa um job por vez, um evento
  de retry+timeout longo atrasa o próximo job em até ~10s a mais que hoje —
  só no caso raro de 429/503 seguido de tentativa final lenta. Aceitável
  frente ao risco de duplicar envio.
- Não resolve, mas destrava: `uazapi-retry-status-adicionais.md` (retry em
  500/502/504 e timeout) cita este item como pré-requisito — depois desta
  mudança, o orçamento do executor deixa de estar "apertado", mudando a
  premissa por trás da decisão atual de não re-tentar timeout no core. Fica
  para avaliação naquele item específico.
- `get_smtp_credentials` e `get_active_whatsapp_connection` (10s cada) não
  chamam a UazAPI — fora do escopo deste item.

---

## Abordagem

```
executor (core_client.py) → core (whatsapp_send.py) → uazapi_client.py → UazAPI
   timeout=25.0 (texto)         timeout=20.0/tentativa, até 3 tentativas em 429/503
   timeout=35.0 (mídia)         timeout=30.0/tentativa, até 3 tentativas em 429/503

Pior caso no core (texto) ≈ 21.5s  <  25.0s (executor) → sem desistência prematura
Pior caso no core (mídia) ≈ 31.5s  <  35.0s (executor) → sem desistência prematura
```

---

## Plano de Implementação

### Fase 1 — Aumentar timeout do executor para cobrir o pior caso do core

**Objetivo:** o timeout do executor ao esperar pelo core nunca é menor que
o pior caso realista de processamento do core (incluindo retry 429/503).

| Arquivo | O que muda |
|---|---|
| `backend-executors/app/clients/core_client.py` | `send_whatsapp_message`: `timeout=15.0` → `timeout=25.0`. `send_whatsapp_media`: `timeout=20.0` → `timeout=35.0` |
| `docs/architecture/whatsapp-send-resiliencia.md` | Remove a secção "Limitação de timeout conhecida" — deixa de ser limitação não resolvida |

```python
# ANTES
def send_whatsapp_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.core_api_base.rstrip("/")
    url = f"{base_url}/whatsapp/send"
    with httpx.Client(timeout=15.0) as client:
        ...

def send_whatsapp_media(payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.core_api_base.rstrip("/")
    url = f"{base_url}/whatsapp/send-media"
    with httpx.Client(timeout=20.0) as client:
        ...

# DEPOIS
def send_whatsapp_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.core_api_base.rstrip("/")
    url = f"{base_url}/whatsapp/send"
    with httpx.Client(timeout=25.0) as client:
        ...

def send_whatsapp_media(payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = settings.core_api_base.rstrip("/")
    url = f"{base_url}/whatsapp/send-media"
    with httpx.Client(timeout=35.0) as client:
        ...
```

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `87fd3c4` | timeouts alinhados em `core_client.py` + doc atualizada |

**Detalhes do commit `87fd3c4`:**
- `backend-executors/app/clients/core_client.py` — `send_whatsapp_message`
  timeout 15.0 → 25.0; `send_whatsapp_media` timeout 20.0 → 35.0
- `docs/architecture/whatsapp-send-resiliencia.md` — secção "Orçamento de
  timeout" substitui a antiga "Limitação de timeout conhecida (não
  resolvida)"

### Relatório da Fase 1 — o que mudou na prática

**Antes:** se o core demorasse mais que 15s (texto) ou 20s (mídia) para
completar um envio à UazAPI — mesmo que a mensagem tivesse sido enviada com
sucesso —, o executor desistia por timeout e reagendava o job para
tentativa futura, correndo risco de enviar a mesma mensagem duas vezes ao
lead.

**Agora:** o executor espera até 25s/35s, tempo suficiente para cobrir o
pior caso realista do core (incluindo as tentativas de retry em 429/503).
Isso elimina a janela em que o executor desistia antes do core terminar.
Não há mudança perceptível quando o envio é rápido (caso normal).

**Para validar:** Cenário P1 e P2, abaixo (já revisados nesta sessão — ver
resultado registrado nos checks).

---

## Checks de Validação

Sem UI (backend-executors não tem frontend) e sem forma confiável de forçar
uma resposta lenta real da UazAPI em ambiente local — validação por revisão
de código/cálculo e testes automatizados existentes.

### Cenário P1 — Suíte de testes do backend-executors sem regressão
- [x] Rodar a suíte de testes do `backend-executors`
- [x] Confirmar que nada quebrou com a mudança de timeout
- **Validado em:** 26/08/2026 — 80 falhas / 209 passaram no worktree; 81
  falhas / 221 passaram na pasta principal (`main`), sem a mudança. Mesma
  família de falhas pré-existentes em ambos (`test_qualification_*`,
  `test_recepcao_*`, `test_scheduling_agent_no_closing`, etc.), sem
  relação com `core_client.py` — nenhuma regressão nova introduzida.

### Cenário P2 — Revisão do cálculo de pior caso
- [x] Confirmar que 25.0s > ~21.5s (pior caso texto) e 35.0s > ~31.5s (pior
      caso mídia), com margem de segurança razoável
- **Validado em:** 26/08/2026 — cálculo revisado no diagnóstico acima;
  margem de ~3.5s (texto) e ~3.5s (mídia) sobre o pior caso estimado.
- **Nota:** não é possível forçar uma resposta lenta real da UazAPI em
  ambiente de teste para validar isso ao vivo — cobertura fica no cálculo
  documentado acima.

---

## Ajustes Possíveis Pós-Implementação

- Reavaliar `uazapi-retry-status-adicionais.md` (retry em 500/502/504 e
  timeout) agora que o orçamento do executor tem mais margem — a razão
  original para não re-tentar timeout ("orçamento apertado") fica mais
  fraca depois desta mudança.
