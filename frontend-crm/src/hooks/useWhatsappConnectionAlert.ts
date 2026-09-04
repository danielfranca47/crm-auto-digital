import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";

export function useWhatsappConnectionAlert() {
  const { data } = useQuery({
    queryKey: ["whatsapp-connection-alert"],
    queryFn: () => api.crm.whatsappConnectionAlert(),
    refetchInterval: 60_000,
  });

  return {
    disconnected: data?.disconnected ?? false,
    since: data?.since ?? null,
  };
}
