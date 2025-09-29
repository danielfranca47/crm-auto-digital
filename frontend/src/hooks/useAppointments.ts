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

function normalizeAppointment(raw: any): Appointment {
  const start = raw?.start_time ?? raw?.startTime ?? raw?.start ?? "";
  const end = raw?.end_time ?? raw?.endTime ?? raw?.end ?? null;
  return {
    id: String(raw?.id ?? ""),
    leadId:
      raw?.lead_id !== undefined && raw?.lead_id !== null
        ? String(raw.lead_id)
        : raw?.leadId !== undefined
        ? String(raw.leadId)
        : null,
    title: raw?.title ?? "",
    description: raw?.description ?? undefined,
    type: raw?.type ?? "meeting",
    status: raw?.status ?? "scheduled",
    startTime: typeof start === "string" ? start : new Date(start).toISOString(),
    endTime:
      end === null || end === undefined
        ? undefined
        : typeof end === "string"
        ? end
        : new Date(end).toISOString(),
    leadName: raw?.lead_contact ?? raw?.leadName ?? null,
    leadCompany: raw?.lead_company ?? raw?.leadCompany ?? null,
  };
}

export function useAppointments(filters?: {
  start?: string;
  end?: string;
  status?: string;
  leadId?: string | number | null;
}) {
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
  });
}

export function useCreateAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateAppointmentPayload) => {
      const response = await api.appointments.create({
        leadId: payload.leadId ?? null,
        title: payload.title,
        description: payload.description,
        type: payload.type,
        status: payload.status ?? "scheduled",
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
    }: {
      id: string | number;
      data: UpdateAppointmentPayload;
    }) => {
      const response = await api.appointments.update(id, {
        leadId: data.leadId ?? undefined,
        title: data.title,
        description: data.description,
        type: data.type,
        status: data.status,
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
    mutationFn: async (id: string | number) => {
      const response = await api.appointments.cancel(id);
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
    mutationFn: async (id: string | number) => {
      return api.appointments.remove(id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentsKeys.all });
    },
  });
}

export { normalizeAppointment };
