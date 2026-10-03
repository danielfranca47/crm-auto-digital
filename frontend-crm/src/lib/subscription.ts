import type { EntitlementsResponse, ProductEntitlement } from "@/services/api";

export type SubscriptionState = "active" | "expired" | "cancelled" | "none";

export const SUBSCRIPTION_STATE_LABELS: Record<SubscriptionState, string> = {
  active: "Ativo",
  expired: "Expirado",
  cancelled: "Cancelado",
  none: "Sem plano",
};

function periodEndMs(product: ProductEntitlement) {
  const ms = product.current_period_end ? Date.parse(product.current_period_end) : NaN;
  return Number.isNaN(ms) ? 0 : ms;
}

/**
 * Escolhe a assinatura do CRM que representa o estado actual da conta.
 *
 * O core devolve uma linha por assinatura que o utilizador já teve — cada activação cancela
 * a anterior e cria outra — por isso a primeira linha do produto não é necessariamente a
 * que vale: a activa ganha sempre; sem activa, vale a de período mais recente.
 */
export function pickCrmSubscription(entitlements?: EntitlementsResponse | null): {
  state: SubscriptionState;
  product: ProductEntitlement | null;
} {
  const crmProducts = (entitlements?.products ?? []).filter((p) => p?.product_code === "crm");
  if (!crmProducts.length) return { state: "none", product: null };

  const active = crmProducts.find((p) => p.status === "active");
  if (active) return { state: "active", product: active };

  const latest = crmProducts.reduce((best, p) => (periodEndMs(p) > periodEndMs(best) ? p : best));
  return { state: latest.status === "expired" ? "expired" : "cancelled", product: latest };
}
