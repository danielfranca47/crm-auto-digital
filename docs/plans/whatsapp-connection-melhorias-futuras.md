# WhatsApp Connection — Melhorias Futuras

> Contexto: itens deixados de fora da graduação de
> `docs/implementations/pareamento-codigo-whatsapp-login.md` (código de
> pareamento como alternativa ao QR).

## M1 — Paridade de código de pareamento no Agente Espião

**Prioridade: MÉDIA**

`backend-crm/routes/spy_agent.py` (endpoint `/api/spy-agent/reconnect`, linhas
581-649) tem um fluxo de reconexão WhatsApp duplicado e independente do de
`routes/whatsapp_connect.py` — helpers próprios de extração de QR
(`_QR_KEYS`, `_find_in_payload`, `_infer_qr_kind`, `_normalize_status_raw`),
sem reaproveitar os de `whatsapp_connect.py`. Não suporta telefone/código de
pareamento hoje — só QR.

Se fizer sentido oferecer o mesmo método alternativo por lá (útil para quem
está a configurar o Agente Espião com um único aparelho), seria uma
implementação separada. Ver [`docs/architecture/whatsapp-connection.md`](../architecture/whatsapp-connection.md#outros-consumidores-fora-deste-fluxo)
para o estado actual dos dois fluxos.

---

## M2 — Reconexão remota via palavra-chave num número de suporte dedicado

**Prioridade:** a definir com o utilizador

**Contexto:** surgiu durante a investigação de `alerta-desconexao-whatsapp.md`
e `aviso-sessao-dupla-whatsapp.md`. Hipótese principal para a queda de sessão
após ~1h: conflito de sessão quando o mesmo número tem o WhatsApp Web/Desktop
aberto em paralelo à ligação do CRM (payload real capturado:
`"401: logged out from another device"`). O aviso preventivo
(`aviso-sessao-dupla-whatsapp.md`) e os testes em curso devem confirmar isto
primeiro.

**Ideia proposta pelo utilizador:** dedicar um número de WhatsApp só para
suporte, usado pela Lara para contactar o cliente afectado. Se o cliente
responder com uma palavra-chave (ex.: "restabelecer conexão"), o sistema
tentaria automaticamente: (1) reativar a ligação/login do agente do cliente
na UazAPI, e (2) forçar a saída do WhatsApp Web/Desktop da máquina local do
cliente, para eliminar o conflito de sessão sem o cliente precisar de o fazer
manualmente.

**Não avaliado ainda — precisa de diagnóstico próprio em Plan Mode antes de
implementar:**
- Viabilidade técnica do ponto (2): não há confirmação de que a
  UazAPI/Baileys expõe alguma operação que permita a uma sessão vinculada
  (a do agente) forçar o logout de *outro* aparelho vinculado da mesma conta
  (o WhatsApp Web/Desktop do cliente) — isto normalmente só é possível a
  partir do aparelho principal (o telemóvel), via "Aparelhos conectados →
  Sair". Precisa de confirmação na documentação da UazAPI/Baileys antes de
  prometer esta funcionalidade ao cliente.
- Se (2) não for viável, a funcionalidade reduz-se a "reconectar o agente
  automaticamente por palavra-chave" (sem resolver a causa raiz se o cliente
  continuar a usar o WhatsApp Web/Desktop em paralelo).
- Custo de manter um número dedicado de suporte activo (nova instância
  UazAPI, novo fluxo de mensagens fora do pipeline normal de leads).
