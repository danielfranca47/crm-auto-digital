# Pós-Checkout Efí — Melhorias Futuras

> Contexto: itens sobreviventes de `kiwify-checkout-melhorias-pos-etapa-9-7.md` após a
> migração do gateway de pagamento de Kiwify para Efí Bank (ver
> [`docs/architecture/billing-efi.md`](../architecture/billing-efi.md) —
> `docs/implementations/migracao-gateway-efi-bank.md`, já graduado e removido). Os itens
> que dependiam especificamente do fluxo Kiwify (seed do plano `crm_scale`, retries de
> webhook, fluxo de upgrade sem proration) foram descartados na auditoria de 12/09/2026 —
> resolvidos pelo próprio fluxo Efí, ou já rastreados noutro documento. Os itens abaixo
> continuam válidos porque não dependem do gateway específico.

---

## M1 — Página de boas-vindas para novos compradores

**Prioridade: ALTA**

**Estado actual:** o checkout hoje é feito na página hospedada pela Efí
(`GET /checkout/efi/{offer_key}`, `backend-crm/routes/checkout.py`); ao activar a
subscrição de um comprador com email novo, o backend já envia o email de boas-vindas
(`render_welcome_email`) — mas não existe nenhuma página dedicada dentro do produto para
receber esse cliente depois do pagamento. Não existe rota pública `/welcome` em
`frontend-crm/src/App.tsx`.

**Risco concreto:** o cliente novo termina o pagamento na página da Efí e não tem nenhuma
orientação dentro da plataforma sobre o que fazer a seguir (primeiro login, ligar o
WhatsApp, configurar o agente).

**O que precisaria existir:** uma rota pública `/welcome` com confirmação de activação,
instruções de primeiro login e primeiros passos sugeridos.

---

## M2 — Forçar mudança de senha no primeiro login

**Prioridade: ALTA**

**Estado actual:** quando o email do comprador não existe no sistema, o backend cria o
`User` com uma senha temporária aleatória (14 caracteres) e a envia por email em texto
claro (`backend-core/app/api/subscriptions.py`, função `payment_event`, ramo de email
desconhecido). Não existe nenhum campo `must_change_password` nem mecanismo que force a
troca dessa senha após o primeiro login.

**Risco concreto:** se o email for comprometido, a conta fica vulnerável indefinidamente.

**O que precisaria existir:** um campo que force a definição de uma nova senha no primeiro
acesso, ou substituir o envio da senha em claro por um link de definição de senha
(reaproveitando o fluxo de recuperação de senha já existente).

---

## M3 — Email de confirmação quando cliente existente faz upgrade

**Prioridade: MÉDIA**

**Estado actual:** quando um cliente existente tem o plano activado/renovado
(`backend-core/app/api/subscriptions.py`, função `payment_event`, ramo "activate (ou renew
sem sub activa)"), o sistema só regista um log (`logger.info(...)`) — nenhum email de
confirmação é enviado ao cliente.

**Risco concreto:** o cliente paga um upgrade e só descobre que funcionou entrando na
plataforma — nenhum sinal de confirmação chega por email.

**O que precisaria existir:** enviar um email de confirmação (mesmo padrão já usado noutros
pontos do ciclo de vida da assinatura, ex.: aviso de expiração) quando esse ramo
activa/renova o plano de um cliente já existente.
