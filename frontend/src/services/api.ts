// services/api.ts
const fromEnv = (import.meta as any)?.env?.VITE_API_BASE_URL;

// fallback esperto: se estiver em *.danielfranca.pt, usa a API pública
const smartFallback =
  typeof location !== "undefined" &&
  /\.danielfranca\.pt$/i.test(location.hostname)
    ? "https://api.danielfranca.pt"
    : "http://localhost:8000";

const RAW_BASE = fromEnv || smartFallback;

const API = `${RAW_BASE.replace(/\/$/, "")}/api`;
const AUTH = `${RAW_BASE.replace(/\/$/, "")}/auth`;

// helper fetch com cookies (reutiliza o mesmo handle)
async function handleWithCreds(res: Response) {
  return handle(res);
}

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
  channel: Channel; // "email" | "whatsapp" | "instagram" | "call"
  body: string;
  subject?: string;
  select?: boolean; // se true, faz upsert em message_selections
};

export type SaveMessageResponse = {
  ok: boolean;
  id: number; // id da linha criada em messages
  selected?: boolean; // true se fez a seleção
};

export type WhatsEnqueueResp = {
  ok: boolean;
  queued: { lead_id: number; message_id: number; job_id?: number }[];
  skipped: { lead_id: number; reason: string }[];
};

export type AgentsOverview = {
  jobs: {
    pending: number;
    in_progress: number;
    completed_recent: number;
    failed_recent: number;
  };
  agents: {
    id: string;
    name: string;
    status: string;
    last_seen?: string | null;
    updated_at?: string | null;
  }[];
  generated_at: string;
};
// ================================================

const normalizeNextScheduledAction = (raw: any) => {
  if (!raw) return null;
  const dateValue = raw.date ?? raw.start_at ?? raw.startAt;
  if (!dateValue) return null;

  return {
    date: new Date(dateValue),
    description: raw.description ?? "",
  };
};

function mapAppointment(raw: any) {
  const start =
    raw?.start_at ?? raw?.start_time ?? raw?.startAt ?? raw?.start ?? null;
  const end = raw?.end_at ?? raw?.end_time ?? raw?.endAt ?? raw?.end ?? null;

  return {
    id: String(raw?.id ?? ""),
    leadId:
      raw?.lead_id != null
        ? String(raw.lead_id)
        : raw?.leadId != null
        ? String(raw.leadId)
        : null,

    title: raw?.title ?? "Compromisso",
    description: raw?.description ?? undefined,
    type: raw?.type ?? "meeting",

    // preserva exatamente o que veio do backend
    status: raw?.status ?? "pending",

    startTime:
      typeof start === "string"
        ? start
        : start
        ? new Date(start).toISOString()
        : "",
    endTime:
      end == null
        ? undefined
        : typeof end === "string"
        ? end
        : new Date(end).toISOString(),

    leadName: raw?.lead_contact ?? raw?.leadName ?? null,
    leadCompany: raw?.lead_company ?? raw?.leadCompany ?? null,
  };
}

export const api = {
  // -------- LEADS --------
  getLeads: async () => {
    const res = await fetch(`${API}/leads`);
    const data = await handle(res);
    if (!Array.isArray(data)) return data;
    return data.map((lead) => ({
      ...lead,
      nextScheduledAction: normalizeNextScheduledAction(
        lead.nextScheduledAction
      ),
    }));
  },
  // --- LEADS (CRUD) ---
createLead: async (payload: {
  companyName: string;
  contactName?: string | null;
  phone?: string | null;
  email?: string | null;
  origin?: string | null;
  category: string;               // ex.: "to-prospect"
  customMessage?: string | null;
  observations?: string | null;
  priority?: number;              // default no back = 1
}) => {
  const res = await fetch(`${API}/leads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      companyName: payload.companyName,
      contactName: payload.contactName ?? null,
      phone: payload.phone ?? null,
      email: payload.email ?? null,
      origin: payload.origin ?? "Manual",
      category: payload.category,
      customMessage: payload.customMessage ?? null,
      observations: payload.observations ?? null,
      priority: payload.priority ?? 1,    // <- **priority** (int), não "prioridade"
    }),
  });
  return handle(res); // retorna o lead criado
},

updateLead: async (id: string | number, patch: Partial<{
  companyName: string;
  contactName: string | null;
  phone: string | null;
  email: string | null;
  origin: string | null;
  category: string;
  customMessage: string | null;
  observations: string | null;
  priority: number;
  lastMovement: string | Date;
}>) => {
  const res = await fetch(`${API}/leads/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...(patch.companyName !== undefined ? { companyName: patch.companyName } : {}),
      ...(patch.contactName !== undefined ? { contactName: patch.contactName } : {}),
      ...(patch.phone !== undefined ? { phone: patch.phone } : {}),
      ...(patch.email !== undefined ? { email: patch.email } : {}),
      ...(patch.origin !== undefined ? { origin: patch.origin } : {}),
      ...(patch.category !== undefined ? { category: patch.category } : {}),
      ...(patch.customMessage !== undefined ? { customMessage: patch.customMessage } : {}),
      ...(patch.observations !== undefined ? { observations: patch.observations } : {}),
      ...(patch.priority !== undefined ? { priority: patch.priority } : {}),
      ...(patch.lastMovement !== undefined
        ? { lastMovement: patch.lastMovement instanceof Date ? patch.lastMovement.toISOString() : patch.lastMovement }
        : {}),
    }),
  });
  return handle(res);
},

deleteLead: async (id: string | number) => {
  const res = await fetch(`${API}/leads/${id}`, { method: "DELETE" });
  return handle(res);
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
      startTime: string; // ISO
      endTime?: string | null; // ISO | null
    }) => {
      const res = await fetch(`${API}/appointments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lead_id: payload.leadId ? Number(payload.leadId) : null,
          title: payload.title,
          description: payload.description,
          type: payload.type,
          status: payload.status ?? "pending",
          start_at: payload.startTime,
          end_at: payload.endTime ?? null,
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
        startTime: string; // ISO
        endTime?: string | null; // ISO | null
      }>
    ) => {
      const res = await fetch(`${API}/appointments/${id}`, {
        method: "PATCH", //
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...(payload.leadId !== undefined
            ? {
                lead_id:
                  payload.leadId === null ? null : Number(payload.leadId),
              }
            : {}),
          ...(payload.title !== undefined ? { title: payload.title } : {}),
          ...(payload.description !== undefined
            ? { description: payload.description }
            : {}),
          ...(payload.type !== undefined ? { type: payload.type } : {}),
          ...(payload.status !== undefined ? { status: payload.status } : {}),
          ...(payload.startTime !== undefined
            ? { start_at: payload.startTime }
            : {}),
          ...(payload.endTime !== undefined ? { end_at: payload.endTime } : {}),
        }),
      });
      return handle(res);
    },

    cancel: async (
      arg: string | number | { id: string | number; leadId: string | number }
    ) => {
      // forma nova { id, leadId }
      if (typeof arg === "object" && arg !== null && "id" in arg && "leadId" in arg) {
        const { id, leadId } = arg as { id: string | number; leadId: string | number };
        // usa a rota por lead (PATCH status=canceled)
        return api.updateAppointment(String(leadId), String(id), {
          status: "canceled",
        });
      }

      // forma antiga (só id) — mantém compat
      return api.appointments.update(arg as string | number, {
        status: "canceled",
      });
    },

    /**
     * (opcional) Remoção tolerante: aceita { id, leadId } e usa a rota por lead
     */
    remove: async (
      arg:
        | string
        | number
        | { id: string | number; leadId: string | number }
    ) => {
      if (typeof arg === "object" && arg !== null && "id" in arg && "leadId" in arg) {
        const { id, leadId } = arg as { id: string | number; leadId: string | number };
        const res = await fetch(
          `${API}/leads/${leadId}/appointments/${id}`,
          { method: "DELETE" }
        );
        return handle(res);
      }
      const res = await fetch(`${API}/appointments/${arg}`, { method: "DELETE" });
      return handle(res);
    },
  },

  getAppointments: async (leadId: number | string) => {
    const res = await fetch(`${API}/leads/${leadId}/appointments`);
    // devolve JSON bruto; o hook faz a normalização correta
    return handle(res);
  },

  createAppointment: async (
    leadId: number | string,
    payload: {
      title?: string;
      description?: string;
      type?: string;
      status?: string;
      location?: string;
      startAt: Date;
      endAt?: Date | null;
    }
  ) => {
    const res = await fetch(`${API}/leads/${leadId}/appointments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...(payload.title !== undefined ? { title: payload.title } : {}),
        ...(payload.description !== undefined
          ? { description: payload.description }
          : {}),
        ...(payload.type !== undefined ? { type: payload.type } : {}),
        status: payload.status ?? "pending",
        ...(payload.location !== undefined ? { location: payload.location } : {}),
        start_at: payload.startAt.toISOString(),
        ...(payload.endAt !== undefined
          ? {
              end_at:
                payload.endAt === null ? null : payload.endAt.toISOString(),
            }
          : {}),
      }),
    });
    const data = await handle(res);
    return mapAppointment(data);
  },

  updateAppointment: async (
    leadId: number | string,
    appointmentId: number | string,
    payload: {
      title?: string;
      description?: string;
      type?: string;
      status?: string;
      location?: string;
      startAt?: Date;
      endAt?: Date | null;
    }
  ) => {
    const res = await fetch(
      `${API}/leads/${leadId}/appointments/${appointmentId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...(payload.title !== undefined ? { title: payload.title } : {}),
          ...(payload.description !== undefined
            ? { description: payload.description }
            : {}),
          ...(payload.type !== undefined ? { type: payload.type } : {}),
          ...(payload.status !== undefined ? { status: payload.status } : {}),
          ...(payload.location !== undefined ? { location: payload.location } : {}),
          ...(payload.startAt !== undefined
            ? { start_at: payload.startAt.toISOString() }
            : {}),
          ...(payload.endAt !== undefined
            ? {
                end_at:
                  payload.endAt === null ? null : payload.endAt.toISOString(),
              }
            : {}),
        }),
      }
    );
    return handle(res); // <- sem mapAppointment
  },

  deleteAppointment: async (
    leadId: number | string,
    appointmentId: number | string
  ) => {
    const res = await fetch(
      `${API}/leads/${leadId}/appointments/${appointmentId}`,
      { method: "DELETE" }
    );
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
    saveMessage: async (
      payload: SaveMessagePayload
    ): Promise<SaveMessageResponse> => {
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
    salvarMensagem: async (
      payload: SaveMessagePayload
    ): Promise<SaveMessageResponse> => api.prospeccao.saveMessage(payload),

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
        const res = await fetch(
          `${API}/prospeccao/whatsapp/recent?since_secs=${sinceSecs}`
        );
        return handle(res);
      },
      summary: async () => {
        const res = await fetch(`${API}/prospeccao/whatsapp/summary`);
        return handle(res);
      },

      worker: {
        /**
         * @deprecated Worker remoto substituído pelo Agente Local.
         * Mantido apenas para compatibilidade de chamadas legadas.
         */
        start: async () => {
          const res = await fetch(`${API}/whatsapp/worker/start`, {
            method: "POST",
          });
          return handle(res);
        },
        /**
         * @deprecated Worker remoto substituído pelo Agente Local.
         */
        stop: async () => {
          const res = await fetch(`${API}/whatsapp/worker/stop`, {
            method: "POST",
          });
          return handle(res);
        },
        status: async (): Promise<{ running: boolean }> => {
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
  },

  // -------- AUTH (MVP) --------
  auth: {
    login: async (email: string, password: string) => {
      const res = await fetch(`${AUTH}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include", // cookie httpOnly
        body: JSON.stringify({ email, password }),
      });
      return handleWithCreds(res); // { email, role }
    },

    me: async () => {
      const res = await fetch(`${AUTH}/me`, {
        credentials: "include", // envia cookie
      });
      return handleWithCreds(res); // { email, role }
    },

    logout: async () => {
      const res = await fetch(`${AUTH}/logout`, {
        method: "POST",
        credentials: "include",
      });
      return handleWithCreds(res); // { ok: true }
    },
  },

  agents: {
    overview: async (hours = 24): Promise<AgentsOverview> => {
      const res = await fetch(`${API}/agents/overview?hours=${hours}`);
      return handle(res);
    },
    enqueueTestJob: async (payload: { type?: string; payload?: Record<string, any>; priority?: number }) => {
      const res = await fetch(`${API}/agents/test-job`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload ?? {}),
      });
      return handle(res);
    },
  },
};
