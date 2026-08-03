import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";

export const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

/**
 * Fuso horário do negócio (ai_profile.timezone) — usado para exibir e salvar horários de
 * compromissos de forma consistente independente do fuso de quem está a ver a Agenda.
 * Sem timezone configurado no perfil, cai no fuso do próprio navegador (comportamento anterior).
 */
export function useBusinessTimezone(): string {
  const { data } = useQuery({
    queryKey: ["ai-profile-timezone"],
    queryFn: () => api.core.getAiProfileMe(),
    staleTime: 5 * 60_000,
  });

  return data?.timezone || browserTimezone;
}
