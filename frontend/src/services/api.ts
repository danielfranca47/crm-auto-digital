// services/api.ts
const RAW_BASE =
  (import.meta as any)?.env?.VITE_API_BASE_URL ?? "http://localhost:8000";
const API = `${RAW_BASE.replace(/\/$/, "")}/api`;

async function handle(res: Response) {
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = isJson ? (data as any)?.detail ?? JSON.stringify(data) : data;
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return data;
}

// ---- Tipos da Pesquisa (site) ----
export type SearchPayload = {
  proposal: "site";
  country: string;
  state: string;
  city: string;
  neighborhood?: string;
  sector: string;
  quantity: number; // 5..50
};

export type Manifest = {
  run_id: string;
  files?: { csv?: string; xlsx?: string; xlsx_validado?: string };
  counts?: Record<string, number>;
  summary?: Record<string, any>;
};

export type LeadMessage = {
  id: number;
  channel: "email" | "whatsapp" | "instagram" | "call";
  subject?: string | null;
  body: string;
  model?: string | null;
  createdAt: string;
};

export type ManifestResponse = {
  ok: boolean;
  manifest: Manifest;
};

// ========= Tipos adicionais (Prospecção) =========
export type Channel = "email" | "whatsapp" | "instagram" | "call";

export type ProspectionLogPayload = {
  lead_id: number;
  action:
    | "copied"
    | "wa_opened"
    | "mail_opened"
    | "sent"
    | "replied"
    | "moved_stage"
    | "scheduled_followup"
    | "queued"
    | "failed";
  channel?: Channel;
  message_id?: number;
  notes?: string;
};

export type WhatsQueueItem = {
  lead_id: number;
  message_id: number;
  phone: string;
  body: string;
};

export type SaveMessagePayload = {
  lead_id: number;
  channel: Channel;          // "email" | "whatsapp" | "instagram" | "call"
  body: string;
  subject?: string;
  select?: boolean;          // se true, faz upsert em message_selections
};

export type SaveMessageResponse = {
  ok: boolean;
  id: number;                // id da linha criada em messages
  selected?: boolean;        // true se fez a seleção
};

export type WhatsEnqueueResp = {
  ok: boolean;
  queued: { lead_id: number; message_id: number }[];
  skipped: { lead_id: number; reason: string }[];
};
// ================================================

const normalizeNextScheduledAction = (raw: any) => {
  if (!raw) return null;
  const dateValue = raw.date ?? raw.start_at ?? raw.startAt;
  if (!dateValue) return null;

  return {
    date: new Date(dateValue),
    description: raw.description ?? '',
  };
};

const mapAppointment = (raw: any) => ({
  id: String(raw.id),
  leadId: String(
    raw.lead_id ?? raw.leadId ?? raw.leadID ?? raw.lead?.id ?? raw.lead ?? ''
  ),
  description: raw.description ?? '',
  startAt: raw.start_at ? new Date(raw.start_at) : new Date(),
  endAt: raw.end_at ? new Date(raw.end_at) : raw.end_at ?? null,
  createdAt: raw.created_at ? new Date(raw.created_at) : raw.created_at ?? null,
  updatedAt: raw.updated_at ? new Date(raw.updated_at) : raw.updated_at ?? null,
});

export const api = {
  // -------- LEADS --------
  getLeads: async () => {
    const res = await fetch(`${API}/leads`);
    const data = await handle(res);
    if (!Array.isArray(data)) return data;
    return data.map((lead) => ({
      ...lead,
      nextScheduledAction: normalizeNextScheduledAction(lead.nextScheduledAction),
    }));
  },

  appointments: {
    list: async (params?: {
      start?: string;
      end?: string;
      status?: string;
      leadId?: string | number | null;
    }) => {
      const search = new URLSearchParams();
      if (params?.start) search.set("start", params.start);
      if (params?.end) search.set("end", params.end);
      if (params?.status) search.set("status", params.status);
      if (params?.leadId) search.set("lead_id", String(params.leadId));

      const qs = search.toString();
      const url = qs ? `${API}/appointments?${qs}` : `${API}/appointments`;
      const res = await fetch(url);
      return handle(res);
    },

    create: async (payload: {
      leadId?: string | number | null;
      title: string;
      description?: string;
      type: string;
      status?: string;
      startTime: string;
      endTime?: string | null;
    }) => {
      const res = await fetch(`${API}/appointments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lead_id: payload.leadId ? Number(payload.leadId) : null,
          title: payload.title,
          description: payload.description,
          type: payload.type,
          status: payload.status ?? "scheduled",
          start_time: payload.startTime,
          end_time: payload.endTime ?? null,
        }),
      });
      return handle(res);
    },

    update: async (
      id: string | number,
      payload: Partial<{
        leadId?: string | number | null;
        title: string;
        description?: string;
        type: string;
        status?: string;
        startTime: string;
        endTime?: string | null;
      }>
    ) => {
      const res = await fetch(`${API}/appointments/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...(payload.leadId !== undefined
            ? { lead_id: payload.leadId === null ? null : Number(payload.leadId) }
            : {}),
          ...(payload.title !== undefined ? { title: payload.title } : {}),
          ...(payload.description !== undefined ? { description: payload.description } : {}),
          ...(payload.type !== undefined ? { type: payload.type } : {}),
          ...(payload.status !== undefined ? { status: payload.status } : {}),
          ...(payload.startTime !== undefined ? { start_time: payload.startTime } : {}),
          ...(payload.endTime !== undefined ? { end_time: payload.endTime } : {}),
        }),
      });
      return handle(res);
    },

    cancel: async (id: string | number) => {
      return api.appointments.update(id, { status: "canceled" });
    },

    remove: async (id: string | number) => {
      const res = await fetch(`${API}/appointments/${id}`, { method: "DELETE" });
      return handle(res);
    },
  },

  createLead: async (leadData: any) => {
    console.log("📦 JSON enviado para o backend:", leadData);
    const res = await fetch(`${API}/leads/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(leadData),
    });
    return handle(res);
  },

  updateLead: async (id: number | string, data: any) => {
    const res = await fetch(`${API}/leads/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return handle(res);
  },

  deleteLead: async (id: number | string) => {
    const res = await fetch(`${API}/leads/${id}`, { method: "DELETE" });
    return handle(res);
  },

  getAppointments: async (leadId: number | string) => {
    const res = await fetch(`${API}/leads/${leadId}/appointments`);
    const data = await handle(res);
    return Array.isArray(data) ? data.map(mapAppointment) : data;
  },

  createAppointment: async (
    leadId: number | string,
    payload: { description: string; startAt: Date; endAt?: Date | null }
  ) => {
    const res = await fetch(`${API}/leads/${leadId}/appointments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        description: payload.description,
        start_at: payload.startAt.toISOString(),
        end_at: payload.endAt ? payload.endAt.toISOString() : undefined,
      }),
    });
    const data = await handle(res);
    return mapAppointment(data);
  },

  updateAppointment: async (
    leadId: number | string,
    appointmentId: number | string,
    payload: { description?: string; startAt?: Date; endAt?: Date | null }
  ) => {
    const res = await fetch(`${API}/leads/${leadId}/appointments/${appointmentId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        description: payload.description,
        start_at: payload.startAt ? payload.startAt.toISOString() : undefined,
        end_at: payload.endAt ? payload.endAt.toISOString() : payload.endAt === null ? null : undefined,
      }),
    });
    const data = await handle(res);
    return mapAppointment(data);
  },

  deleteAppointment: async (leadId: number | string, appointmentId: number | string) => {
    const res = await fetch(`${API}/leads/${leadId}/appointments/${appointmentId}`, {
      method: "DELETE",
    });
    return handle(res);
  },

  // -------- PESQUISA (automação) --------
  pesquisa: {
    executar: async (payload: SearchPayload): Promise<ManifestResponse> => {
      const res = await fetch(`${API}/pesquisa/executar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return handle(res);
    },

    downloadUrl: (runId: string, kind: "xlsx_validado" | "xlsx" | "csv") =>
      `${API}/pesquisa/baixar/${encodeURIComponent(runId)}/${kind}`,
  },

  // -------- UPLOADS da página Assistente IA --------
  uploads: {
    enviar: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API}/uploads`, { method: "POST", body: fd });
      return handle(res);
    },
  },

  // -------- ASSISTENTE IA --------
  assistenteIA: {
    processar: async (payload: any) => {
      const res = await fetch(`${API}/assistente-ia/processar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return handle(res);
    },

    mensagens: async (
      leadId: number | string,
      latest = true
    ): Promise<{ ok: boolean; messages: LeadMessage[] }> => {
      const res = await fetch(
        `${API}/assistente-ia/messages/${leadId}?latest=${latest}`
      );
      return handle(res);
    },

    preview: async (payload: {
      upload_id: string;
      overwrite: "skip" | "update" | "duplicate";
    }) => {
      const res = await fetch(`${API}/assistente-ia/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return handle(res);
    },
  },

  // -------- PROSPECÇÃO --------
  prospeccao: {
    selecionarMensagem: async (
      leadId: number,
      channel: Channel,
      messageId: number
    ) => {
      const res = await fetch(`${API}/prospeccao/select-message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lead_id: leadId, channel, message_id: messageId }),
      });
      return handle(res);
    },

    selecoesDoLead: async (leadId: number): Promise<Record<string, number>> => {
      const res = await fetch(`${API}/prospeccao/selection/${leadId}`);
      const data = await handle(res);
      return (data?.selections as Record<string, number>) ?? {};
    },

    registrarLog: async (payload: ProspectionLogPayload) => {
      const res = await fetch(`${API}/prospeccao/log`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return handle(res);
    },

    // Normaliza a resposta do backend (message_id -> id)
    saveMessage: async (payload: SaveMessagePayload): Promise<SaveMessageResponse> => {
      const res = await fetch(`${API}/prospeccao/save-message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await handle(res);
      // mantém compatibilidade com o tipo atual
      return {
        ok: !!data?.ok,
        id: Number(data?.message_id ?? data?.id),
        selected: data?.selected ?? undefined,
      };
    },

    // alias compatível
    salvarMensagem: async (payload: SaveMessagePayload): Promise<SaveMessageResponse> =>
      api.prospeccao.saveMessage(payload),

    // ===== WhatsApp (envio automático via fila) =====
    whatsapp: {
      enqueue: async (leadIds: number[]): Promise<WhatsEnqueueResp> => {
        const res = await fetch(`${API}/prospeccao/whatsapp/enqueue`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lead_ids: leadIds }),
        });
        return handle(res);
      },

      queue: async (limit = 5): Promise<WhatsQueueItem[]> => {
        const res = await fetch(
          `${API}/prospeccao/whatsapp/queue?limit=${limit}`
        );
        return handle(res);
      },

      mark: async (payload: {
        lead_id: number;
        message_id: number;
        ok: boolean;
        notes?: string;
      }) => {
        const res = await fetch(`${API}/prospeccao/whatsapp/mark`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        return handle(res);
      },

      recent: async (sinceSecs = 300) => {
        const res = await fetch(`${API}/prospeccao/whatsapp/recent?since_secs=${sinceSecs}`);
        return handle(res);
      },
      summary: async () => {
        const res = await fetch(`${API}/prospeccao/whatsapp/summary`);
        return handle(res);
      },

      worker: {
        start: async () => {
          const res = await fetch(`${API}/whatsapp/worker/start`, { method: "POST" });
          return handle(res);
        },
        stop: async () => {
          const res = await fetch(`${API}/whatsapp/worker/stop`, { method: "POST" });
          return handle(res);
        },
        status: async () => {
          const res = await fetch(`${API}/whatsapp/worker/status`);
          return handle(res);
        },
      },
    },
  },

  // -------- WHATSAPP (QR via Selenium) --------
  whatsapp: {
    iniciarQR: async () => {
      const res = await fetch(`${API}/whatsapp/iniciar-qr`, { method: "POST" });
      return handle(res);
    },
    verificarLogin: async (opts?: { passive?: boolean }) => {
      const passive = opts?.passive !== false;
      const qs = passive ? "?passive=1" : "";
      const res = await fetch(`${API}/whatsapp/verificar-login${qs}`);
      return handle(res);
    },
    novoQR: async () => {
      const res = await fetch(`${API}/whatsapp/novo-qr`);
      return handle(res);
    },
    stop: async () => {
      const res = await fetch(`${API}/whatsapp/stop`, { method: "POST" });
      return handle(res);
    },

    // >>> Endpoints do worker (adicionados)
    worker: {
      start: async () => {
        const res = await fetch(`${API}/whatsapp/worker/start`, { method: "POST" });
        return handle(res);
      },
      stop: async () => {
        const res = await fetch(`${API}/whatsapp/worker/stop`, { method: "POST" });
        return handle(res);
      },
      status: async (): Promise<{ running: boolean }> => {
        const res = await fetch(`${API}/whatsapp/worker/status`);
        return handle(res);
      },
    },
  },
};
