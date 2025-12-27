import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { useApiErrorHandler } from "./useApiErrorHandler";

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
  const { handleError } = useApiErrorHandler();

  const fetchUsage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get<UsageResponse>("/usage");
      setData(response);
    } catch (err) {
      const result = handleError(err, {
        silent: true,
        fallbackMessage: "Erro ao carregar informações do plano.",
      });
      setError(result.message);
    } finally {
      setLoading(false);
    }
  }, [handleError]);

  useEffect(() => {
    fetchUsage();
  }, [fetchUsage]);

  return { data, loading, error, refetch: fetchUsage } as const;
}
