import { useQuery } from "@tanstack/react-query";
import { readAuthToken } from "@/lib/auth-token";
import { pickCrmSubscription, SubscriptionState } from "@/lib/subscription";
import { api } from "@/services/api";

export const ENTITLEMENTS_QUERY_KEY = ["entitlements"] as const;

/**
 * Estado da assinatura do CRM, lido do core (`/me/entitlements` responde mesmo sem plano
 * activo, ao contrário das rotas do backend-crm).
 *
 * `unknown` = não foi possível saber (core indisponível, sem token). Conta como acesso
 * liberado: quem decide de facto é o backend-crm, e um cliente pagante nunca deve ver o
 * ecrã de "sem plano" por uma falha de rede.
 */
export function useSubscriptionStatus() {
  const query = useQuery({
    queryKey: ENTITLEMENTS_QUERY_KEY,
    queryFn: () => api.core.getEntitlements(),
    enabled: !!readAuthToken(),
    retry: 1,
    staleTime: 60_000,
  });

  const picked = query.data ? pickCrmSubscription(query.data) : null;
  const state: SubscriptionState | "unknown" = picked?.state ?? "unknown";

  return {
    state,
    product: picked?.product ?? null,
    hasAccess: state === "active" || state === "unknown",
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    refetch: query.refetch,
  } as const;
}
