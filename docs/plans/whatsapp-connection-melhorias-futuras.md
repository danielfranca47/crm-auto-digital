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
