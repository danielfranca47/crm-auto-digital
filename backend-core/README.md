# Backend Core (Accounts & Subscriptions)

Serviço FastAPI para autenticação básica de usuários do CRM AutoDigital e gestão de catálogo, planos e assinaturas.

Preparação Local
pip install email-validator
rodar na porta 8001

## Como rodar
1. Crie um `.env` na pasta `backend-core/` (ou copie o `.env.example`).
2. Instale dependências: `pip install -r backend-core/requirements.txt`.
3. Rode o servidor: `uvicorn app.main:app --reload --app-dir backend-core` (execute a partir da raiz do repositório).

O banco SQLite será criado automaticamente (arquivo `core.db`) na raiz de `backend-core`.

> Nota: o hash de senha usa `pbkdf2_sha256` via `passlib`, evitando dependências de SO específicas como o `bcrypt`.

Ao iniciar, o serviço também faz seed dos produtos, planos e limites padrão descritos abaixo.

## Rotas disponíveis
- `POST /auth/register`: cria usuário com `email` e `password`.
- `POST /auth/login`: valida credenciais e retorna `access_token` (Bearer).
- `GET /users/me`: requer header `Authorization: Bearer <token>` e retorna dados do usuário autenticado.
- `GET /products`: lista produtos ativos.
- `GET /plans?product_code=`: lista planos ativos (opcionalmente filtrando por produto).
- `GET /subscriptions/me`: lista assinaturas do usuário autenticado.
- `POST /subscriptions`: cria uma assinatura para o usuário autenticado informando `product_code` e `plan_code`.
- `GET /me/limits`: retorna limites consolidados do usuário (planos ativos + addons).
- `GET /me/entitlements`: retorna status geral de assinaturas, planos por produto e limites consolidados para consumo por serviços externos (CRM/n8n).
- `GET /ai-templates`: lista templates de agente IA disponíveis (estático por enquanto).
- `GET /ai-profiles/me`: retorna o perfil de IA do usuário autenticado (404 se não existir).
- `POST /ai-profiles`: cria ou sobrescreve o perfil de IA do usuário autenticado.
- `PUT /ai-profiles/me`: atualiza parcialmente (ou cria, se informar todos os campos) o perfil de IA do usuário autenticado.
- `GET /ai-profiles/resolve?user_id=`: endpoint interno protegido por `X-Service-Token` que retorna o AIProfile de um usuário sem exigir bearer token.
- `GET /whatsapp-connections/me`: retorna a conexão WhatsApp (provider/tags) do usuário autenticado, com token mascarado.
- `POST /whatsapp-connections/me`: cria ou atualiza a conexão WhatsApp do usuário autenticado, armazenando o token criptografado.
- `PUT /whatsapp-connections/me`: atualiza a conexão WhatsApp do usuário autenticado (token opcional), mantendo criptografia.
- `GET /whatsapp-connections/resolve?instance_id=`: endpoint interno protegido por `X-Service-Token` para resolver dono/status da instância e expor `allow_orion` + `max_ia_conversas_monthly`.
- `GET /whatsapp-connections/resolve-token?instance_id=`: endpoint interno protegido por `X-Service-Token` que retorna o token descriptografado da instância junto com metadados (não requer bearer token).
- `POST /whatsapp-instances/init`: endpoint interno protegido por `X-Service-Token` para inicializar instâncias Uazapi via `admintoken`.
- `POST /whatsapp-instances/connect`: endpoint interno protegido por `X-Service-Token` para iniciar conexão e obter QR/paircode via Uazapi (usa token da instância armazenado).
- `GET /whatsapp-instances/status?instance_id=`: endpoint interno protegido por `X-Service-Token` para consultar status na Uazapi (usa token da instância armazenado).
- `POST /whatsapp-instances/webhook`: endpoint interno protegido por `X-Service-Token` para configurar webhooks globais ou por instância na Uazapi.

> `allow_orion` é calculado apenas com base em `max_ia_conversas_monthly`: se for `None` (ilimitado) ou maior que zero, o uso do produto Orion é permitido, mesmo que `max_whatsapp_send_daily` seja zero.

## Variáveis de ambiente adicionais
- `WHATSAPP_TOKEN_ENC_KEY`: chave Fernet (base64) usada para criptografar o `instance_token` antes de persistir.
- `CORE_SERVICE_TOKEN`: token de serviço necessário para acessar `/whatsapp-connections/resolve`, `/whatsapp-connections/resolve-token` e `/ai-profiles/resolve`.
- `CORE_WHATSAPP_STUB`: ativa o modo stub do endpoint `/whatsapp/send` (use apenas em dev/test).
- `UAZAPI_BASE_URL`: base URL global do provider Uazapi (ex.: `https://free.uazapi.com`).
- `UAZAPI_ADMIN_TOKEN`: token de administração Uazapi usado nos endpoints administrativos.

## Modo stub do WhatsApp send (dev/test)
Para rodar testes end-to-end sem chamar o provider real, ative:

```bash
CORE_WHATSAPP_STUB=true
```

Quando ativo, o endpoint `POST /whatsapp/send` retorna 200 sem chamar a Uazapi.
Exemplo de resposta:

```json
{
  "provider": "uazapi",
  "provider_message_id": "stub-2024-01-01T12:00:00+00:00-abc123",
  "raw": {
    "stub": true,
    "status": "ok",
    "echo": {
      "provider": "uazapi",
      "instance_id": "inst_123",
      "number": "5511999999999",
      "text": "Olá!"
    }
  }
}
```

> Aviso: use apenas em ambientes de desenvolvimento/teste.

## Endpoints internos Uazapi (admin)

Todos os endpoints abaixo exigem `X-Service-Token: <CORE_SERVICE_TOKEN>`.

### `POST /whatsapp-instances/init`

Headers adicionais usados pelo Core ao chamar a Uazapi: `admintoken: <UAZAPI_ADMIN_TOKEN>`.

Body mínimo:

```json
{
  "user_id": 123,
  "instance_id": "minha-instancia"
}
```

O `instance_id` é normalizado para slug (sem espaços). O Core envia `{"name": "<instance_id>"}` para a Uazapi. Campos extras no body são repassados (ex.: `systemName`, `fingerprintProfile`).

### `POST /whatsapp-instances/connect`

Headers adicionais usados pelo Core ao chamar a Uazapi: `token: <INSTANCE_TOKEN>`.

Body mínimo:

```json
{
  "user_id": 123,
  "instance_id": "minha-instancia"
}
```

Resposta da Uazapi pode conter `qrcode`/`paircode`. O Core retorna o `raw` sem alterações.

### `GET /whatsapp-instances/status?instance_id=...`

Headers adicionais usados pelo Core ao chamar a Uazapi: `token: <INSTANCE_TOKEN>`.

Retorna o status informado pela Uazapi (`status`/`instanceStatus`).

### `POST /whatsapp-instances/webhook`

Para **webhook global**, o Core usa `admintoken` e chama `/globalWebhook` na Uazapi.
Para **webhook por instância**, o Core usa `token: <INSTANCE_TOKEN>`; se `instance_token` não for enviado no payload, o Core busca o token no banco pela `instance_id`.

Body mínimo (global):

```json
{
  "url": "https://crm.exemplo.com/webhooks/uazapi",
  "globalWebhook": true
}
```

Body mínimo (por instância):

```json
{
  "url": "https://crm.exemplo.com/webhooks/uazapi",
  "instance_id": "minha-instancia"
}
```

Recomendado incluir:

```json
{
  "events": ["messages", "messages_update", "connection"],
  "excludeMessages": ["wasSentByApi"]
}
```

## Testando o fluxo
1. **Registrar**: `curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d '{"email":"teste@example.com","password":"senha123"}'`
2. **Login**: `curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"teste@example.com","password":"senha123"}'`
   - Guarde o `access_token` retornado.
3. **/users/me**: `curl http://localhost:8000/users/me -H "Authorization: Bearer <access_token>"`
4. **Criar assinatura**: `curl -X POST http://localhost:8000/subscriptions -H "Content-Type: application/json" -H "Authorization: Bearer <access_token>" -d '{"product_code":"crm","plan_code":"crm_basic"}'`
5. **Checar limites**: `curl http://localhost:8000/me/limits -H "Authorization: Bearer <access_token>"`
6. **Checar entitlements consolidados**: `curl http://localhost:8000/me/entitlements -H "Authorization: Bearer <access_token>"`
6. **Criar/atualizar perfil IA (exemplo completo)**:
   ```bash
   curl -X POST http://localhost:8000/ai-profiles \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <access_token>" \
     -d '{
       "template_key": "sdr_padrao",
       "name": "Agente Comercial da Agência XYZ",
       "brand_name": "Agência XYZ",
       "tone_of_voice": "profissional e amigável",
       "niche": "agência de tráfego para clínicas",
       "target_audience": "clínicas de estética e saúde",
       "offer_description": "serviço de gestão de tráfego e CRM",
       "goals": "qualificar leads e agendar reuniões",
       "custom_instructions": "reforce sempre os cases de clínicas"
     }'
   ```
7. **Consultar perfil IA**: `curl http://localhost:8000/ai-profiles/me -H "Authorization: Bearer <access_token>"`

Substitua `localhost:8000` conforme a porta utilizada pelo Uvicorn.
