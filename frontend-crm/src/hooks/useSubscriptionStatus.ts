import { useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { ApiError } from "@/lib/api-client";
import { readAuthToken } from "@/lib/auth-token";
import { isPublicPath } from "@/lib/public-routes";
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
  const { pathname } = useLocation();
  const enabled = !!readAuthToken() && !isPublicPath(pathname);

  const query = useQuery({
    queryKey: ENTITLEMENTS_QUERY_KEY,
    queryFn: () => api.core.getEntitlements(),
    enabled,
    // Só repete em falha de rede/5xx — um 401/403 não muda à segunda tentativa.
    retry: (failureCount, error) =>
      failureCount < 1 && !(error instanceof ApiError && !!error.status && error.status < 500),
    // Em erro, não refazer só porque outro componente montou: a query voltaria a "pending",
    // o SubscriptionGate esconderia a app e a montagem seguinte repetia o ciclo. A consulta
    // recupera ao voltar o foco à janela ou quando um 403 invalida a chave.
    retryOnMount: false,
    staleTime: 60_000,
  });

  const picked = query.data ? pickCrmSubscription(query.data) : null;
  const state: SubscriptionState | "unknown" = picked?.state ?? "unknown";

  return {
    state,
    product: picked?.product ?? null,
    hasAccess: state === "active" || state === "unknown",
    // "Ainda não houve nenhuma resposta" (sucesso ou erro). `query.isLoading` volta a true
    // a cada nova tentativa de uma consulta em erro — o gate não pode depender disso.
    isLoading: enabled && !query.isFetched,
    isFetching: query.isFetching,
    refetch: query.refetch,
  } as const;
}
