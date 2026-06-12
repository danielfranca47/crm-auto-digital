import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import type {
  Appointment,
  CreateAppointmentPayload,
  UpdateAppointmentPayload,
} from "@/types/crm";

export const appointmentsKeys = {
  all: ["appointments"] as const,
  list: (filters?: Record<string, unknown>) =>
    ["appointments", filters ? JSON.stringify(filters) : "all"] as const,
};

// chave separada para consultas POR LEAD
export const leadAppointmentsKeys = {
  byLead: (leadId: string | number) =>
    ["lead-appointments", String(leadId)] as const,
};

// --- Normalização compatível com backend novo e legado ---
function normalizeAppointment(raw: any): Appointment {
  const start =
    raw?.start_at ?? raw?.start_time ?? raw?.startAt ?? raw?.start ?? "";
  const end =
    raw?.end_at ?? raw?.end_time ?? raw?.endAt ?? raw?.end ?? start ?? null;
  const rawStatus = String(raw?.status ?? "pending");
  const normalizedStatus = rawStatus === "scheduled" ? "pending" : rawStatus;

  return {
    id: String(raw?.id ?? ""),
    leadId:
      raw?.lead_id !== undefined && raw?.lead_id !== null
        ? String(raw.lead_id)
        : raw?.leadId !== undefined && raw?.leadId !== null
        ? String(raw.leadId)
        : null,
    title: raw?.title ?? "Compromisso",
    description: raw?.description ?? undefined,
    type: raw?.type ?? "meeting",
    status: normalizedStatus as any,
    outcome: raw?.outcome ?? undefined,
    outcome_note: raw?.outcome_note ?? raw?.outcomeNote ?? null,
    outcome_at: raw?.outcome_at ?? raw?.outcomeAt ?? null,
    startTime:
      typeof start === "string" ? start : new Date(start).toISOString(),
    endTime:
      end === null || end === undefined
        ? undefined
        : typeof end === "string"
        ? end
        : new Date(end).toISOString(),
    leadName: raw?.lead_contact ?? raw?.leadName ?? null,
    leadCompany: raw?.lead_company ?? raw?.leadCompany ?? null,
    source: (raw?.source ?? "crm") as "crm" | "google",
    google_event_id: raw?.google_event_id ?? null,
  };
}

/**
 * Hook de listagem (AGENDA/DASHBOARD).
 * Só faz request se tiver `start` ou `end` (ou se `enabled: true` for passado).
 */
export function useAppointments(
  filters?: {
    start?: string;
    end?: string;
    status?: string;
    leadId?: string | number | null;
  },
  options?: { enabled?: boolean }
) {
  const enabled =
    options?.enabled ??
    Boolean(filters?.start || filters?.end || filters?.leadId);

  return useQuery({
    queryKey: appointmentsKeys.list(filters ?? {}),
    queryFn: async () => {
      const response = await api.appointments.list({
        start: filters?.start,
        end: filters?.end,
        status: filters?.status,
        leadId: filters?.leadId ?? undefined,
      });
      if (!Array.isArray(response)) return [] as Appointment[];
      return response.map(normalizeAppointment);
    },
    enabled,
    staleTime: 60_000,
  });
}

/**
 * Hook de listagem POR LEAD (CARD DO LEAD).
 * Usa exclusivamente GET /leads/{id}/appointments.
 */
export function useLeadAppointments(
  leadId?: string | number,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: leadAppointmentsKeys.byLead(leadId ?? "0"),
    enabled: !!leadId && (options?.enabled ?? true),
    queryFn: async () => {
      if (!leadId) return [] as Appointment[];
      const data = await api.getAppointments(leadId);
      const list = Array.isArray(data) ? data : [];
      return list.map(normalizeAppointment);
    },
    staleTime: 60_000,
  });
}

export function useCreateAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateAppointmentPayload) => {
      // Se há leadId, use a rota POR LEAD (POST /leads/{id}/appointments),
      // que aceita apenas { description, startAt, endAt }.
      if (payload.leadId !== undefined && payload.leadId !== null) {
        const res = await api.createAppointment(payload.leadId, {
          title: payload.title,
          type: payload.type,
          description: payload.description,
          startAt: new Date(payload.startTime),
          endAt: payload.endTime ? new Date(payload.endTime) : undefined,
        });
        return normalizeAppointment(res);
      }

      // Fallback: endpoint genérico
      const response = await api.appointments.create({
        leadId: null,
        title: payload.title,
        description: payload.description,
        type: payload.type,
        status: (payload.status as any) ?? "pending",
        startTime: payload.startTime,
        endTime: payload.endTime ?? null,
      });
      return normalizeAppointment(response);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentsKeys.all });
    },
  });
}

export function useUpdateAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      data,
      leadId,
    }: {
      id: string | number;
      data: UpdateAppointmentPayload;
      leadId?: string | number | null;
    }) => {
      // Se soubermos o leadId, use a rota POR LEAD (PATCH /leads/{id}/appointments/{id}),
      // que aceita apenas { description, startAt, endAt }.
      if (leadId ?? data.leadId) {
        const lid = String(leadId ?? data.leadId!);
        const resp = await api.updateAppointment(lid, id, {
          title: data.title,
          type: data.type,
          description: data.description,
          startAt: data.startTime ? new Date(data.startTime) : undefined,
          endAt:
            data.endTime === null
              ? null
              : data.endTime
              ? new Date(data.endTime)
              : undefined,
        });
        return normalizeAppointment(resp);
      }

      // Fallback: endpoint genérico (aceita campos completos)
      const response = await api.appointments.update(id, {
        leadId: data.leadId ?? undefined,
        title: data.title,
        description: data.description,
        type: data.type,
        status: data.status as any,
        startTime: data.startTime,
        endTime: data.endTime,
      });
      return normalizeAppointment(response);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentsKeys.all });
    },
  });
}

export function useCancelAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, leadId }: { id: string | number; leadId: string | number }) => {
      // chama o cancel “tolerante” que criamos acima
      const response = await api.appointments.cancel({ id, leadId });
      return normalizeAppointment(response);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentsKeys.all });
    },
  });
}

export function useDeleteAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (
      arg: string | number | { id: string | number; leadId: string | number }
    ) => {
      if (typeof arg === "object" && arg !== null && "id" in arg && arg.leadId) {
        return api.appointments.remove({ id: arg.id, leadId: arg.leadId });
      }
      const id = typeof arg === "object" ? arg.id : arg;
      return api.appointments.remove(id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentsKeys.all });
      queryClient.invalidateQueries({ queryKey: leadAppointmentsKeys.byLead("") });
    },
  });
}

export { normalizeAppointment };
