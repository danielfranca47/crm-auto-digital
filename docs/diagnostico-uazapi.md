# Diagnóstico: Migração UazAPI Free → Plano Pago

**Data:** 2026-04-18  
**Branch:** etapa-8-5-ajustes

---

## Resumo executivo

A integração atual com a UazAPI está **bem estruturada e majoritariamente pronta** para o plano pago. A arquitetura isola corretamente a URL base, usa tokens criptografados por instância e trata erros de forma robusta. A migração requer **uma mudança obrigatória** (URL base) e algumas melhorias recomendadas antes de ir para produção com usuários pagantes.

---

## O que muda no plano pago

| Aspecto | Free (`free.uazapi.com`) | Pago |
|---|---|---|
| **Base URL** | `https://free.uazapi.com` | URL própria por servidor (ex: `https://api.uazapi.com` ou subdomínio dedicado) |
| **Admin Token** | Token compartilhado do plano free | Token exclusivo do servidor pago |
| **Limites de instâncias** | Limitado (plano free) | 100–300 dispositivos conforme plano |
| **SLA / Estabilidade** | Best-effort | Suporte dedicado + atualizações regulares |
| **Autenticação** | Admin token + token por instância | Mesmo esquema — sem quebra de contrato |
| **Endpoints** | Iguais | Iguais — API compatível entre planos |

> **Ponto crítico:** a API é compatível entre planos. Não há mudança de contrato de endpoints. A única diferença real é a URL base e o admin token.

---

## Diagnóstico por componente

### ✅ Prontos — sem alteração necessária

| Componente | Arquivo | Status |
|---|---|---|
| Cliente HTTP UazAPI | `backend-core/app/providers/uazapi_client.py` | ✅ Usa `base_url` como parâmetro — plugável |
| Serviço admin | `backend-core/app/services/uazapi_admin.py` | ✅ `base_url` injetado em todas as funções |
| Envio de mensagens | `backend-core/app/api/whatsapp_send.py` | ✅ Lê `UAZAPI_BASE_URL` do settings |
| Criptografia de token | `backend-core/app/utils/crypto.py` | ✅ Fernet por instância, nunca exposto em logs |
| Webhook por instância | `backend-core/app/api/whatsapp_instances.py` | ✅ Auto-configurado no connect |
| Multi-tenancy | `backend-core/app/models/whatsapp_connection.py` | ✅ Isolamento por `user_id` + `instance_id` |
| Modo stub (dev) | `CORE_WHATSAPP_STUB=true` | ✅ Sem tráfego real em ambiente de teste |

---

### 🔴 Mudança obrigatória

#### 1. Atualizar `UAZAPI_BASE_URL` no `.env` do `backend-core`

```diff
- UAZAPI_BASE_URL=https://free.uazapi.com
+ UAZAPI_BASE_URL=https://<url-do-seu-servidor-pago>
```

E atualizar o `UAZAPI_ADMIN_TOKEN` para o token do servidor pago.

**Por quê é a única mudança necessária:** `UAZAPI_BASE_URL` e `UAZAPI_ADMIN_TOKEN` são lidos de `app/config.py` (via `settings`) e propagados como parâmetro para todas as funções de `uazapi_admin.py` e `uazapi_client.py`. Não há nenhuma URL hardcoded nos serviços.

**Verificação:**
```bash
grep -rn "free.uazapi.com" backend-core/
# Deve aparecer apenas no .env — nenhum outro lugar
```

---

### 🟡 Melhorias recomendadas antes de produção

#### 2. Verificar se `free.uazapi.dev` é o host correto do free tier

A documentação menciona `https://free.uazapi.dev` como endpoint do plano gratuito (v2, lançada em setembro 2024), mas o `.env` atual aponta para `https://free.uazapi.com`. Recomendado confirmar com a UazAPI qual endpoint está ativo e atualizar antes de qualquer teste com o plano pago.

#### 3. Validar instâncias existentes na migração

Instâncias criadas no servidor free (`free.uazapi.com`) **não migram automaticamente** para o servidor pago. Cada usuário precisará reconectar o WhatsApp no novo servidor. Fluxo:

1. Marcar conexões existentes como `status = "disconnected"` no banco
2. Usuário acessa o CRM → dispara novo `/api/whatsapp/connect`
3. Sistema cria nova instância no servidor pago
4. Usuário lê QR e reconecta

#### 4. Backoff exponencial em rate-limit (429)

O código atual propaga o erro 429 para o cliente mas não faz retry automático. No plano pago pode haver limites de chamadas por minuto para operações administrativas (init/connect):

- **Arquivo:** `backend-core/app/services/uazapi_admin.py`, linha ~156 (`_request`)
- **Ação:** adicionar retry com backoff na camada `_request` para 429/503

#### 5. Rotação e proteção do `UAZAPI_ADMIN_TOKEN`

O admin token atual está em texto plano no `.env`. Para o plano pago (que tem custo):
- Não comitar o `.env` com o token real no repositório
- Considerar secrets manager (Doppler, AWS Secrets Manager, ou variável de ambiente no servidor)
- Rotacionar o token após a migração

#### 6. Validação E.164 no envio de mensagem

O número de destino atualmente só tem formatação removida (espaços, traços, parênteses), sem validação de formato. Com plano pago e custo por instância, erros de número podem gerar chamadas desnecessárias à API:

- **Arquivo:** `backend-core/app/api/whatsapp_send.py`, linha ~107
- **Sugestão:** validar padrão `^\+?[1-9]\d{7,14}$` antes de chamar a UazAPI

---

## Fluxo atual (mapeado)

```
frontend-crm → POST /api/whatsapp/connect
    → backend-crm/routes/whatsapp_connect.py
        → core_client.init_core_whatsapp_instance()
            → backend-core POST /whatsapp-instances/init
                → uazapi_admin.init_instance()
                    → POST {UAZAPI_BASE_URL}/instance/init   ← muda aqui
                    ← instance_token (criptografado e salvo no DB)
        → core_client.connect_core_whatsapp_instance()
            → backend-core POST /whatsapp-instances/connect
                → uazapi_admin.connect_instance()
                    → POST {UAZAPI_BASE_URL}/instance/connect  ← muda aqui
                    ← QR code
        → set_core_whatsapp_webhook()
            → POST {UAZAPI_BASE_URL}/webhook               ← muda aqui
    ← { instance_id, status, qr: { kind, value } }

Envio de mensagem:
backend-executors → POST /whatsapp/send (core)
    → uazapi_client.send_text()
        → POST {UAZAPI_BASE_URL}/send/text                 ← muda aqui
```

**Apenas a URL base muda** — todos os paths de endpoint permanecem os mesmos.

---

## Checklist de migração

```
[x] Confirmar URL do servidor pago com a UazAPI — https://digitalpro.uazapi.com
[x] Atualizar UAZAPI_BASE_URL no backend-core/.env
[x] Atualizar UAZAPI_ADMIN_TOKEN (token do servidor pago)
[x] Atualizar UAZAPI_BASE_URL no backend-crm/.env (segunda cópia, usada por audio_transcription.py)
[x] Testar fluxo completo: connect → QR → status connected → envio de texto → inbound + resposta IA → áudio + transcrição
[ ] Monitorar logs de erro nas primeiras 24h após migração
[x] Garantir que .env com o token pago não está no git history (gitignored)
```

Detalhes da execução: [`docs/implementations/etapa-uazapi-migracao-plano-pago.md`](implementations/etapa-uazapi-migracao-plano-pago.md).

---

## Conclusão

**Migração concluída em 2026-08-12.** `UAZAPI_BASE_URL` e `UAZAPI_ADMIN_TOKEN` foram trocados para o servidor pago (`https://digitalpro.uazapi.com`) em `backend-core/.env` e `backend-crm/.env`, confirmando a premissa deste diagnóstico: troca de variável de ambiente, sem alteração de código.

Validação end-to-end feita com a instância real do utilizador:
- Conexão via QR code → status `connected` no servidor pago.
- Mensagem inbound de um número externo criou o lead e dispara a IA.
- IA respondeu automaticamente (3 mensagens) via `backend-executors` → `POST /whatsapp/send` no servidor pago.
- Áudio (PTT) enviado ao número conectado foi baixado do servidor pago e transcrito corretamente pelo pipeline (`services/audio_transcription.py`), com a IA respondendo ao conteúdo transcrito.

**Nota para testes locais futuros:** o webhook da UazAPI é sempre registrado apontando para `CRM_PUBLIC_BASE_URL` (URL pública), nunca `localhost` — a UazAPI não consegue entregar eventos a um endereço não roteável. Para testar o fluxo inbound localmente é necessário expor o `backend-crm` via túnel (ex.: ngrok), apontar `CRM_PUBLIC_BASE_URL` temporariamente para o túnel, reconfigurar o webhook (`POST {UAZAPI_BASE_URL}/webhook` com o token da instância) e reverter tudo ao final do teste. Também é necessário ter o `backend-executors` (`app.workers.whatsapp_worker`) rodando — é ele quem consome os jobs `whatsapp.inbound.n8n` e efetivamente decide e envia a resposta da IA.

As melhorias listadas na seção amarela (retry/backoff em 429, validação E.164, rotação de token) seguem como recomendação para antes de conectar os 2 clientes — tratadas como Fase 2 opcional no arquivo de implementação.
