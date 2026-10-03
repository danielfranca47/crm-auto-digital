import { Navigate, useLocation } from "react-router-dom";
import { useSubscriptionStatus } from "@/hooks/useSubscriptionStatus";

/**
 * Sem plano activo, a única página útil é /assinatura — todas as outras dependem do
 * backend-crm, que responde 403. Leva o utilizador até lá em vez de o deixar bater no erro.
 */
export default function SubscriptionGate({ children }: { children: React.ReactNode }) {
  const { hasAccess, isLoading } = useSubscriptionStatus();
  const { pathname } = useLocation();

  if (isLoading) {
    return <div style={{ padding: 24 }}>Carregando…</div>;
  }
  if (!hasAccess && pathname !== "/assinatura") {
    return <Navigate to="/assinatura" replace />;
  }
  return <>{children}</>;
}
