# Backend Core (Accounts & Subscriptions)

Serviço FastAPI para autenticação básica de usuários do CRM AutoDigital.

## Como rodar
1. Crie um `.env` na pasta `backend-core/` (ou copie o `.env.example`).
2. Instale dependências: `pip install -r backend-core/requirements.txt`.
3. Rode o servidor: `uvicorn app.main:app --reload --app-dir backend-core` (execute a partir da raiz do repositório).

O banco SQLite será criado automaticamente (arquivo `core.db`) na raiz de `backend-core`.

## Rotas disponíveis
- `POST /auth/register`: cria usuário com `email` e `password`.
- `POST /auth/login`: valida credenciais e retorna `access_token` (Bearer).
- `GET /users/me`: requer header `Authorization: Bearer <token>` e retorna dados do usuário autenticado.

## Testando o fluxo
1. **Registrar**: `curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d '{"email":"teste@example.com","password":"senha123"}'`
2. **Login**: `curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"teste@example.com","password":"senha123"}'`
   - Guarde o `access_token` retornado.
3. **/users/me**: `curl http://localhost:8000/users/me -H "Authorization: Bearer <access_token>"`

Substitua `localhost:8000` conforme a porta utilizada pelo Uvicorn.
