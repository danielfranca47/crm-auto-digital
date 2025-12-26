import { useCallback, useEffect, useState } from "react";
import { apiClient, ApiError } from "@/lib/api-client";

type UsageResponse = {
  entitlements?: {
    products?: Array<{ product_code?: string; plan_code?: string; status?: string }>;
    limits?: Record<string, number | null>;
  };
  usage?: Record<string, unknown>;
};

export function useUsage() {
  const [data, setData] = useState<UsageResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchUsage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get<UsageResponse>("/usage");
      setData(response);
    } catch (err) {
      const isApiError = err instanceof ApiError;
      const expired = isApiError && (err.status === 401 || err.status === 403);
      setError(expired ? "Sessão expirada" : (err as Error)?.message ?? "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsage();
  }, [fetchUsage]);

  return { data, loading, error, refetch: fetchUsage } as const;
}
