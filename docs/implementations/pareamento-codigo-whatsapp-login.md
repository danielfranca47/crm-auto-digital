# Código de pareamento WhatsApp (alternativa ao QR)

**Branch:** `feature/whatsapp-pairing-code`
**Status:** Em andamento

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

_(a preencher após o commit)_

---

### Fase 2 — Frontend: alternância QR ↔ código de pareamento

**Objetivo:** permitir gerar e exibir o código de pareamento na aba Conexão

| Arquivo | O que muda |
|---|---|
| `frontend-crm/src/services/api.ts` | `WhatsappConnectResponse` ganha `pair_code?: string \| null`; `whatsappConnect`/`whatsappRefreshQr` aceitam `phone?: string` opcional |
| `frontend-crm/src/components/agente/ConexaoNumero.tsx` | novo estado `modo: 'qr' \| 'pareamento'` + campo de telefone; link "Não tem outro aparelho? Conectar com código"; exibe `pair_code` como texto com instruções em vez da imagem do QR; reaproveita polling existente sem alteração |

### Commits Fase 2

_(a preencher após o commit)_

---

## Checks de Validação

### Cenário B1 — Requisição manual confirma `paircode` na resposta
- [ ] `POST /api/whatsapp/connect` com `{"phone": "<numero real>"}` contra backend-crm real
- [ ] Confirmar que a resposta crua da UazAPI contém `paircode`
- **Pendente**

### Cenário P1 — Toggle exibe input de telefone
- [ ] Abrir aba Conexão → clicar "Não tem outro aparelho? Conectar com código"
- [ ] Confirmar: campo de telefone aparece, QR não é exibido nesse modo
- **Pendente**

### Cenário P2 — Gerar código exibe texto correto
- [ ] Preencher telefone → gerar código
- [ ] Confirmar: código aparece como texto (não imagem), com instruções de onde digitar
- **Pendente**

### Cenário C1 — Pareamento real conecta o WhatsApp
- [ ] Gerar código com telefone real de teste
- [ ] Digitar o código em WhatsApp → Aparelhos conectados → Conectar com número de telefone
- [ ] Confirmar: status muda para "Conectado" (mesmo polling do fluxo QR)
- **Pendente** — cenário fim-a-fim que replica o caso real da cliente (um único aparelho)

---

## Ajustes Possíveis Pós-Implementação

- `backend-crm/routes/spy_agent.py:581-649` tem um fluxo de reconexão
  duplicado e independente (helpers próprios). Ficou fora do escopo — se
  fizer sentido dar paridade lá também, é uma implementação separada.
- Na graduação, criar `docs/architecture/whatsapp-connection.md` — não existe
  doc de arquitetura dedicado a conexão/QR/instância hoje (fragmentado entre
  `_mapa-sistema.md` e `webhooks.md`).
