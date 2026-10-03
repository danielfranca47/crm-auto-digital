# Assinatura inativa — Melhorias Futuras

> Contexto: itens deixados de fora da implementação
> `fix-assinatura-inativa-tela-renovacao.md` (ecrã de renovação para conta sem plano
> ativo, já graduado e removido — ver "Conta sem plano activo" e "Página de Assinatura" em
> [`docs/architecture/plans-limits.md`](../architecture/plans-limits.md) e
> [`docs/architecture/billing-efi.md`](../architecture/billing-efi.md)). Validados pelo
> utilizador na graduação de 03/10/2026, todos como não-urgentes.

---

## M1 — Período de tolerância após o vencimento

**Prioridade: ALTA**

**Estado actual:** o job diário (`backend-core/app/jobs/subscription_jobs.py`) marca como
`expired` toda a assinatura `active` com `current_period_end` no passado. Se a cobrança
recorrente da Efí chegar horas depois, o cliente fica bloqueado nesse intervalo — e agora
cai no ecrã de plano inactivo.

**O que precisaria existir:** alguns dias de tolerância (prática de mercado: 3 a 7) entre o
fim do período e o bloqueio, eventualmente com aviso dentro da app nesse intervalo.
Decisão de negócio: quantos dias, e se a Lara continua a responder durante a tolerância.

---

## M2 — Preços nos cartões de plano da página de Assinatura

**Prioridade: MÉDIA**

**Estado actual:** os cartões de Start e Growth em `frontend-crm/src/pages/Assinatura.tsx`
mostram "Valor apresentado no checkout". Os valores vivem só nos planos da Efí (R$97 Start,
R$297 Growth, R$197 na renovação do Fundador — ver `billing-efi.md`).

**O que precisaria existir:** o preço visível antes do clique. Exige decidir de onde vem o
valor (core, para não ficar escrito no frontend) e o que vê um Fundador — o
`renewal_checkout_url` de `/me/entitlements` já distingue a oferta dele.

---

## M3 — backend-crm responde 401 quando não consegue falar com o core

**Prioridade: MÉDIA**

**Estado actual:** `backend-crm/core_client.py` levanta `HTTPException(401)` tanto para
token inválido como para falha de rede ao contactar o core ("Falha ao contatar
backend-core") e para qualquer resposta não-200. No frontend, o handler global
(`useApiErrorHandler`) trata qualquer 401 como sessão expirada: aviso + redirect para
`/login`. O token não é apagado (recarregar a página devolve a sessão), mas o cliente vê
"Sessão expirada" numa falha passageira do servidor.

**O que precisaria existir:** o backend-crm responder 503 (ou equivalente) quando o
problema é de comunicação com o core, reservando o 401 para sessão realmente inválida — e
o frontend mostrar um aviso de indisponibilidade em vez de mandar para o login. Verificar
antes o que o executor de WhatsApp e o agent-local fazem com esses códigos.

---

## M4 — Faixa "o teu plano expira em N dias" dentro da app

**Prioridade: BAIXA**

**Estado actual:** o aviso de expiração próxima só chega por email (30/15/7/3/2/1/0 dias).
Dentro da app não há nada até o plano expirar.

**Bloqueio conhecido:** as assinaturas normais renovam sozinhas pela Efí todos os meses e o
sistema não regista quais renovam automaticamente — uma faixa baseada só em
`current_period_end` alarmaria todos os pagantes todos os meses. Precisa primeiro de
distinguir renovação automática de renovação manual (Fundador em transição, trial).

---

## M5 — Modo só-leitura após expirar

**Prioridade: BAIXA**

**Estado actual:** sem plano activo, qualquer rota vai para `/assinatura` (`SubscriptionGate`)
e o backend-crm responde 403 a tudo (`require_crm_access`).

**O que precisaria existir:** deixar o cliente ver leads e conversas sem poder agir, em vez
do bloqueio total — argumento de renovação mais forte do que a frase "os teus dados
continuam guardados". Mexe no contrato do `require_crm_access` (leitura permitida, escrita
bloqueada), por isso não é pequeno.

---

## M6 — Texto do botão "Falar com suporte" no ecrã de plano inactivo

**Prioridade: BAIXA**

**Estado actual:** o botão reutiliza `buildWhatsAppUrl` e o modelo
`VITE_WHATSAPP_UPGRADE_MESSAGE_TEMPLATE`, cuja mensagem fala em "upgrade" ("Quero fazer
upgrade do CRM"), mesmo quando o cliente está a tentar renovar um plano expirado.

**O que precisaria existir:** uma mensagem própria para renovação/reactivação.

---

## M7 — Aviso "Sessão expirada" só aparece uma vez por carregamento da página

**Prioridade: BAIXA**

**Estado actual:** `sessionToastDisplayed` em `frontend-crm/src/hooks/useApiErrorHandler.ts`
é uma variável de módulo que passa a `true` no primeiro aviso e nunca é reposta. Como o
login faz recarregamento completo (`window.location.href`), na prática só afecta quem
chega ao login por navegação interna e volta a ter a sessão expirada sem recarregar.

**O que precisaria existir:** repor a flag quando uma sessão nova começa (ou trocar a flag
por um identificador fixo de toast, que já evita duplicados).
