# Reembolso — Melhorias Futuras

> Contexto: itens deixados de fora da graduação de `refund-admin-mvp.md` (botão de reembolso
> manual no painel admin, já implementado e graduado).

## M1 — Reembolso automático dos 7 dias via agente de email

**Prioridade: BAIXA**

Agente que lê emails de pedido de reembolso, tenta identificar o cliente automaticamente (por
email remetente/dados mencionados) e, se não conseguir, confirma os dados com o cliente antes de
acionar o reembolso. Depende de um agente de leitura/triagem de email ainda não existente no
sistema. O botão manual de reembolso já implementado (`POST /admin/billing/refund`, ver
[`billing-efi.md`](../architecture/billing-efi.md#reembolso)) poderia ser reaproveitado como a
ação final desse fluxo.

## M2 — Inconsistência "7 dias" (H1 da landing) vs "30 dias" (termos formais)

**Prioridade: BAIXA**

A landing (`CRMLandingV2.tsx`) promete garantia de reembolso, mas o H1 fala em "7 dias" enquanto
os termos formais falam em "30 dias". Ainda sem decisão do utilizador sobre qual copy está
correta — decidir e alinhar landing + termos.
