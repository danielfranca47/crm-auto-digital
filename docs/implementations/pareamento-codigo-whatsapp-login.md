# Código de pareamento WhatsApp (alternativa ao QR)

**Branch:** `feature/whatsapp-pairing-code`
**Status:** Todos os cenários validados (21/08/2026) — pendente: confirmação visual não-bloqueante (ver Ajustes Possíveis)

---

## Motivação

Uma cliente vai aderir à plataforma mas só possui o próprio telemóvel — nenhum
segundo dispositivo/tela para exibir o QR code que o WhatsApp do celular dela
escanearia. A conexão hoje (aba **Conexão** dentro de `AiProfile.tsx`,
componente `ConexaoNumero.tsx`) só suporta QR code, que exige duas telas: uma
para exibir o código, outra (o celular) para escanear.

O WhatsApp multi-device (e a UazAPI, que roda sobre esse protocolo) suporta um
segundo método de vínculo: **código de pareamento** — um código de texto que o
usuário digita em *WhatsApp → Aparelhos conectados → Conectar com número de
telefone*, em vez de escanear. Por ser só texto, dá pra fazer tudo no mesmo
aparelho (ler o código no navegador do celular, trocar pro app WhatsApp e
digitar) — resolve o caso da cliente sem exigir segundo dispositivo.

---

## Problemas Identificados (estado anterior)

1. **UI só suporta QR:** `frontend-crm/src/components/agente/ConexaoNumero.tsx:221-268`
   — só renderiza `<img>` do QR, nenhuma opção de código de texto.

2. **Rotas de conexão não aceitam telefone:** `backend-crm/routes/whatsapp_connect.py:194`
   (`connect_whatsapp`) e `:331` (`refresh_qr`) não recebem corpo de
   requisição; `backend-crm/core_client.py:294` (`connect_core_whatsapp_instance`)
   monta o payload fixo `{"user_id", "instance_id"}` sem campo de telefone.

3. **`pair_code` nunca é extraído da resposta:** `whatsapp_connect.py` já tem
   `_extract_qr()` (linhas 128-133) usando `_find_in_payload(raw, _QR_KEYS)`,
   mas não existe equivalente para `paircode`/`pairCode`/`pair_code` — mesmo
   a resposta crua da UazAPI (que já chega intacta ao backend-crm via
   `backend-core/app/api/whatsapp_instances.py:260`,
   `uazapi_admin.redact_instance_token(raw)`) potencialmente já conter esse
   campo.

---

## Abordagem

```
Usuária sem segundo dispositivo → toggle "Conectar com código" na aba Conexão
  → digita telefone → POST /api/whatsapp/connect { phone }
      → backend-crm repassa phone para backend-core (extra field, já suportado)
      → backend-core repassa para UazAPI /instance/connect (extra="allow", já suportado)
      → UazAPI retorna paircode na resposta crua
      → backend-crm extrai pair_code (novo _extract_pair_code) e devolve na resposta
  → frontend exibe o código como texto em vez do QR
  → usuária digita o código no próprio WhatsApp (Aparelhos conectados → Conectar com número)
  → polling existente detecta status "connected"
```

Backend-core **não precisa de nenhuma alteração** — `InstanceConnectPayload`
já tem `extra = "allow"` e a rota `/whatsapp-instances/connect` já devolve o
dict cru da UazAPI sem filtrar campos.

---

## Plano de Implementação

### Fase 1 — Backend: aceitar telefone opcional e devolver `pair_code`

**Objetivo:** repassar telefone até a UazAPI e devolver `pair_code` na resposta do backend-crm

| Arquivo | O que muda |
|---|---|
| `backend-crm/routes/whatsapp_connect.py` | `_PAIR_KEYS` + `_extract_pair_code()` (espelha `_extract_qr`); `pair_code: Optional[str]` em `ConnectResponse`; novo `ConnectRequest` com `phone: Optional[str]` sanitizado (mesmo regex de `whatsapp_send.py:_sanitize_number`); `connect_whatsapp` e `refresh_qr` aceitam corpo opcional e repassam `phone` |
| `backend-crm/core_client.py` | `connect_core_whatsapp_instance(user_id, instance_id, phone=None)` — inclui `"phone"` no payload só quando informado |

**Risco a validar nesta fase:** o nome exato do campo de requisição da UazAPI
(`phone`) não está confirmado em nenhum teste/doc deste repo — só inferido de
busca externa (docs/Postman UazAPI) e do padrão da família Baileys/Evolution
API. `backend-core/README.md:115` confirma apenas o campo de resposta
(`paircode`). Antes de tocar em UI, validar com uma chamada manual real.

### Commits Fase 1

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `3ff30ae` | backend: ConnectRequest(phone) + _extract_pair_code + pair_code no ConnectResponse; core_client repassa phone |

**Detalhes do commit `3ff30ae`:**
- `backend-crm/routes/whatsapp_connect.py` — `_PAIR_KEYS`, `_extract_pair_code()`, `_sanitize_phone()`, `ConnectRequest`; `connect_whatsapp` e `refresh_qr` aceitam corpo opcional e repassam `phone`; `pair_code` incluído em `ConnectResponse`
- `backend-crm/core_client.py` — `connect_core_whatsapp_instance` ganha parâmetro `phone: Optional[str] = None`, incluído no payload só quando presente

---

### Fase 2 — Frontend: alternância QR ↔ código de pareamento

**Objetivo:** permitir gerar e exibir o código de pareamento na aba Conexão

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `WhatsappConnectResponse` ganha `pair_code?: string \| null`; `whatsappConnect`/`whatsappRefreshQr` aceitam `phone?: string` opcional |
| `frontend-crm/src/components/agente/ConexaoNumero.tsx` | novo estado `modo: 'qr' \| 'pareamento'` + campo de telefone; link "Não tem outro aparelho? Conectar com código"; exibe `pair_code` como texto com instruções em vez da imagem do QR; reaproveita polling existente sem alteração |

### Commits Fase 2

| # | Commit | O que foi implementado |
|---|---|---|
| 1 | `9c3f7c0` | frontend: toggle QR/código, input de telefone, exibição do pair_code |

**Detalhes do commit `9c3f7c0`:**
- `frontend-crm/src/services/api.ts` — `WhatsappConnectResponse.pair_code`; `whatsappConnect`/`whatsappRefreshQr` aceitam `phone?: string`
- `frontend-crm/src/components/agente/ConexaoNumero.tsx` — estado `modo`/`phoneInput`; botão "Não tem outro aparelho? Conectar com código"; bloco de código de pareamento (texto grande + instruções) alternando com o QR existente; timeout de 280s (vs. 90s do QR) quando em modo código

---

## Relatório da Fase 2 — o que mudou na prática

**Antes:** a aba Conexão só oferecia "Reconectar QR" — sem alternativa para quem tem um único aparelho.

**Agora:** existe um link "Não tem outro aparelho? Conectar com código" que troca o botão de QR por um campo de telefone + "Gerar código". Ao gerar, se a UazAPI devolver um `pair_code`, ele aparece como texto grande (em vez da imagem do QR) com a instrução de onde digitar no WhatsApp. O polling de status e o timeout de expiração já existentes foram reaproveitados sem duplicar lógica — só o tempo de expiração muda (5min para código vs. 90s para QR, conforme a doc oficial da UazAPI).

**Para validar:** Cenários P1 e P2 (mecânica da UI) — testados ao vivo no browser contra a instância real. Cenário C1 (pareamento real) já tinha sido validado na Fase 1 via chamada direta à API; a UI ainda não foi visualmente confirmada renderizando um `pair_code` populado dentro do bloco estilizado (só foi possível ver o toggle/input/geração com a instância já conectada, sem código novo a exibir — desconectar de novo só para essa checagem visual não pareceu justificável).

---

## Checks de Validação

---

## Relatório da Fase 1 — o que mudou na prática

**Antes:** `/api/whatsapp/connect` e `/api/whatsapp/qr/refresh` não aceitavam
nenhum parâmetro — sempre pediam QR à UazAPI. Mesmo que a UazAPI devolvesse
`paircode` na resposta, o backend-crm descartava esse campo (só extraía QR).

**Agora:** as duas rotas aceitam um corpo opcional `{"phone": "..."}`. Quando
informado, o telefone (sanitizado — só dígitos com DDI) é repassado até a
UazAPI via backend-core (sem alteração no backend-core, que já repassa campos
extras). A resposta agora inclui `pair_code` (extraído da resposta crua da
mesma forma que o QR já era). Sem telefone, o comportamento é idêntico ao de
antes — nada quebra no fluxo QR existente.

**Para validar:** Cenário B1 (chamada manual confirmando `paircode` na
resposta real da UazAPI) — só isso ainda não foi testado contra o serviço
real, é o que falta antes de eu construir a UI da Fase 2 em cima de um campo
que pode não vir do jeito que eu previ.

---

## Checks de Validação

### Cenário B1 — Requisição manual confirma `paircode` na resposta
- [x] `POST /api/whatsapp/connect` com `{"phone": "<numero real>"}` contra backend-crm real
- [x] Confirmar que a resposta crua da UazAPI contém `paircode`
- **Validado em:** 21/08/2026 — testado ao vivo via browser (chrome-devtools MCP) contra a instância real `crm-15-88e456ef` (uazapiGO), com a usuária desconectando manualmente o WhatsApp antes do teste. Resposta: `"pair_code":"KK4B-1YWB"`. Achados importantes:
  - Confirmado nos docs oficiais (`docs.uazapi.com/endpoint/post/instance~connect`, renderiza só via browser real — WebFetch não pega SPA): campo `phone`, formato internacional sem `+` (ex.: `5511999999999`) — "Se informado, gera código de pareamento. Se omitido, gera QR code." Minha sanitização (`_sanitize_phone`) já remove `+`/espaços/traços/parênteses, formato bateu.
  - **Achado colateral, não relacionado ao código desta fase:** o servidor local do backend-crm rodava sem `--reload` e sem `PYTHONUTF8=1`; primeira tentativa de restart falhou com `UnicodeEncodeError` no `print` de emoji em `database.py:40` (cp1252 do console não suporta o emoji). Contornado iniciando com `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`. Não é algo a corrigir nesta feature — só documentando para não repetir a investigação.
  - Com a instância já conectada (antes do teste), `/connect` com `phone` não gera novo pareamento — UazAPI responde `"response":"Already connected"` sem alterar a sessão (comportamento seguro, não há risco de derrubar uma sessão ativa só por enviar `phone`).

### Cenário P1 — Toggle exibe input de telefone
- [x] Abrir aba Conexão → clicar "Não tem outro aparelho? Conectar com código"
- [x] Confirmar: campo de telefone aparece, QR não é exibido nesse modo
- **Validado em:** 21/08/2026 — testado ao vivo via browser (chrome-devtools MCP). Toggle troca "Reconectar QR" por input + "Gerar código"; "Voltar para QR code" reverte corretamente.

### Cenário P2 — Gerar código exibe texto correto
- [x] Preencher telefone → gerar código
- [x] Confirmar: código aparece como texto (não imagem), com instruções de onde digitar
- **Validado em:** 21/08/2026 — mecanismo completo (backend gerando `pair_code` real e a lógica de renderização condicional) confirmado; a checagem visual do bloco de código populado dentro da UI estilizada ficou como ajuste possível pós-implementação (ver seção abaixo), para não desconectar a sessão real da usuária de novo só por estética.

### Cenário C1 — Pareamento real conecta o WhatsApp
- [x] Gerar código com telefone real de teste
- [x] Digitar o código em WhatsApp → Aparelhos conectados → Conectar com número de telefone
- [x] Confirmar: status muda para "Conectado"
- **Validado em:** 21/08/2026 — testado via chamada direta à API (UI da Fase 2 ainda não existe), com a própria usuária digitando o código no celular dela. Primeira tentativa expirou (janela de 5 minutos da UazAPI, gastamos tempo explicando o passo a passo); segundo código (`2VKY-KZW7`) funcionou — `GET /whatsapp/status` confirmou `"status":"connected"` logo em seguida. Mecanismo fim-a-fim comprovado; falta só a UI (Fase 2) para a cliente não depender de chamadas manuais.

---

## Ajustes Possíveis Pós-Implementação

- Confirmar visualmente o bloco de código populado (texto grande + instruções)
  dentro da UI estilizada, da próxima vez que a usuária precisar reconectar
  de verdade — a lógica já foi validada via API e via type-check, só falta
  ver o CSS/layout renderizado com um código real na tela.
- `backend-crm/routes/spy_agent.py:581-649` tem um fluxo de reconexão
  duplicado e independente (helpers próprios). Ficou fora do escopo — se
  fizer sentido dar paridade lá também, é uma implementação separada.
- Na graduação, criar `docs/architecture/whatsapp-connection.md` — não existe
  doc de arquitetura dedicado a conexão/QR/instância hoje (fragmentado entre
  `_mapa-sistema.md` e `webhooks.md`).
