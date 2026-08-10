# Email Cold Outreach — Melhorias Futuras

> Contexto: itens deixados de fora da implementação
> `docs/implementations/etapa-agent-local-v3-email-cold-outreach.md` (email cold outreach v1,
> SMTP-only, graduada — ver `docs/architecture/auth-email.md` e
> `docs/architecture/agent-local-app.md` para a arquitectura actual). Nenhum destes itens é
> bloqueante — todos os cenários de teste da v1 foram validados.

## M1 — Suporte Outlook/Hotmail/Microsoft 365

**Prioridade: BAIXA**

A v1 do cold outreach por email é SMTP genérico apenas (Gmail com senha de app, ou email
comercial/hosting). Contas Outlook/Hotmail/Microsoft 365 ficam de fora porque a Microsoft
desactivou SMTP com autenticação básica para essas contas (set/2024 pessoais, 2022
empresariais) — suportá-las exigiria implementar OAuth Microsoft, um projecto à parte
(fluxo de autorização, refresh tokens, endpoint Graph API para envio, distinto do
`PUT /users/me/smtp` actual que só valida host/porta/username/senha).

## M2 — Múltiplas contas SMTP por utilizador

**Prioridade: BAIXA**

Hoje só é possível conectar **uma** conta SMTP por utilizador (`PUT /users/me/smtp`
sobrescreve a anterior). Permitir múltiplas contas exigiria: nova tabela (em vez das 6
colunas em `users`), UI de selecção de conta activa no agent-local (card "Conta de email"
em `main_screen.py`), e decidir se a escolha de conta é por-lote (como o canal
WhatsApp/Email hoje) ou uma preferência persistida.
