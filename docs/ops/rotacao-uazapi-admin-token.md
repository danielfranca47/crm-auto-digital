# Runbook: rotação do UAZAPI_ADMIN_TOKEN

## Quando executar

Sob suspeita de vazamento — não há calendário fixo de rotação. Exemplos de
gatilho: commit acidental do `.env`, token exposto em log, screenshot ou
máquina local comprometida.

## Por que é seguro (sem downtime)

O `UAZAPI_ADMIN_TOKEN` só é lido em `backend-core`, nas rotas administrativas
de `backend-core/app/api/whatsapp_instances.py` (`/instance/init` e
`/globalWebhook`), via `backend-core/app/services/uazapi_admin.py`.

Instâncias já conectadas **não dependem do admin token** para continuar
funcionando: envio de mensagem (`uazapi_client.py`, `backend-executors`) e
verificação de status usam o token por instância (`instance_token`), gerado
uma vez na criação da instância e guardado no banco — não o admin token.

Ou seja: enquanto o token não é atualizado, o único efeito é que **criar uma
instância nova ou reconfigurar o webhook global falha** — nada que já está
conectado e enviando/recebendo mensagens é afetado.

## Passo a passo

1. **Gerar o novo token no painel da UazAPI**
   - Acessar o painel do servidor pago (`https://digitalpro.uazapi.com` — ver
     `docs/diagnostico-uazapi.md`) e gerar/copiar o novo admin token.
   - Não revogar o token antigo ainda — fazer isso só depois do passo 4.

2. **Atualizar a env var em produção (Railway)**
   - No projeto do `backend-core` no Railway, editar a variável
     `UAZAPI_ADMIN_TOKEN` com o novo valor.
   - Railway reinicia o serviço automaticamente ao salvar a variável.

3. **Atualizar o `.env` local**
   - Em `backend-core/.env`, atualizar `UAZAPI_ADMIN_TOKEN` com o mesmo
     valor novo.
   - Reiniciar o `backend-core` local (`uvicorn app.main:app --port 8001`).

4. **Verificar**
   - Confirmar nos logs do `backend-core` (produção e local) que não há mais
     erros `Uazapi admin error status=401` (token antigo rejeitado) nem
     `UAZAPI_ADMIN_TOKEN is not configured`.
   - Disparar uma operação administrativa de teste (ex.: `POST
     /whatsapp-instances/init` com uma instância de teste, ou reconfigurar o
     webhook global) e confirmar resposta `200`.
   - Confirmar que uma instância já conectada continua enviando/recebendo
     normalmente (não deve ter sido afetada — ver seção acima).

5. **Revogar o token antigo**
   - Só depois de confirmar o passo 4: revogar o token antigo no painel da
     UazAPI, para que ele deixe de ser válido.

## Onde o token vive hoje

- `backend-core/.env` (local, já protegido por `.gitignore`)
- Env vars do serviço `backend-core` no Railway (produção)

Nenhuma outra cópia — `backend-crm` e `backend-executors` não usam o admin
token (ver seção "Por que é seguro" acima).
