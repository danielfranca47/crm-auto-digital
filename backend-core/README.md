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
- `GET /whatsapp-connections/resolve?instance_id=`: endpoint interno protegido por `X-Service-Token` para resolver dono/status da instância e expor `allow_orion` + `max_ia_conversas_monthly`.
- `GET /whatsapp-connections/resolve-token?instance_id=`: endpoint interno protegido por `X-Service-Token` que retorna o token descriptografado da instância junto com metadados (não requer bearer token).

> `allow_orion` é calculado apenas com base em `max_ia_conversas_monthly`: se for `None` (ilimitado) ou maior que zero, o uso do produto Orion é permitido, mesmo que `max_whatsapp_send_daily` seja zero.

## Variáveis de ambiente adicionais
- `WHATSAPP_TOKEN_ENC_KEY`: chave Fernet (base64) usada para criptografar o `instance_token` antes de persistir.
- `CORE_SERVICE_TOKEN`: token de serviço necessário para acessar `/whatsapp-connections/resolve`, `/whatsapp-connections/resolve-token` e `/ai-profiles/resolve`.

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
