// services/api.ts
import { apiClient, API_BASE, CORE_AUTH_BASE, coreClient } from "../lib/api-client";
import { clearAuthToken, persistAuthToken } from "../lib/auth-token";

export type CorePlan = {
  code: string;
  name?: string;
  billing_period?: string | null;
  product_code?: string;
  active?: boolean;
};

export type CoreProduct = {
  code: string;
  name?: string;
};

export type CoreUser = {
  id?: number;
  email?: string | null;
  status?: string;
  created_at?: string;
};

export type EntitlementsResponse = {
  products?: Array<{ product_code?: string; plan_code?: string; status?: string }>;
  limits?: Record<string, number | null>;
};

export type AiTemplate = {
  key: string;
  name: string;
  description?: string;
};

export type AiProfilePayload = {
  template_key: string;
  name: string;
  brand_name: string;
  tone_of_voice: string;
  timezone?: string | null;
  niche: string;
  target_audience: string;
  offer_description: string;
  goals: string;
  custom_instructions?: string | null;
  agent_mode?: "sdr_scheduler" | "closer" | null;
  identity_mode?: "virtual_assistant" | "human_agent" | "user_clone";
  handoff_policy?: "disable_bot" | "keep_active_notify" | "ignore";
  handoff_custom_text?: string | null;
};

export type AiProfile = AiProfilePayload & {
  id?: number;
  user_id?: number;
  created_at?: string;
  updated_at?: string;
};

export type KnowledgeItem = {
  id: number;
  user_id: number;
  title: string;
  source_type: "manual" | "file";
  content_text: string;
  file_path?: string | null;
  created_at: string;
  updated_at: string;
};

export type WhatsappQrPayload = {
  kind: "base64" | "text" | "url" | null;
  value: string | null;
};

export type WhatsappConnectResponse = {
  instance_id: string;
  status?: string | null;
  qr: WhatsappQrPayload;
};

export type WhatsappStatusResponse = {
  instance_id: string;
  status?: string | null;
  phone_e164?: string | null;
  last_updated?: string | null;
};

const AUTH_BASE = CORE_AUTH_BASE;
const CORE_BASE = CORE_AUTH_BASE.replace(/\/auth$/, "");

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
  queued: { lead_id: number; message_id: number }[];
  skipped: { lead_id: number; reason: string }[];
};

export type WhatsEnqueuePayload = {
  lead_ids: number[];
  message?: string;
  lead_messages?: Record<number, string>;
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
    const data = await apiClient.get<any[]>("/leads");
    if (!Array.isArray(data)) return data;
    return data.map((lead) => ({
      ...lead,
      nextScheduledAction: normalizeNextScheduledAction(
        (lead as any).nextScheduledAction
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
    category: string; // ex.: "to-prospect"
    customMessage?: string | null;
    observations?: string | null;
    priority?: number; // default no back = 1
  }) => {
    return apiClient.post("/leads", {
      companyName: payload.companyName,
      contactName: payload.contactName ?? null,
      phone: payload.phone ?? null,
      email: payload.email ?? null,
      origin: payload.origin ?? "Manual",
      category: payload.category,
      customMessage: payload.customMessage ?? null,
      observations: payload.observations ?? null,
      priority: payload.priority ?? 1, // <- **priority** (int), não "prioridade"
    });
  },

  updateLead: async (
    id: string | number,
    patch: Partial<{
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
    }>
  ) => {
    return apiClient.patch(`/leads/${id}`, {
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
        ? {
            lastMovement:
              patch.lastMovement instanceof Date
                ? patch.lastMovement.toISOString()
                : patch.lastMovement,
          }
        : {}),
    });
  },

  deleteLead: async (id: string | number) => {
    return apiClient.delete(`/leads/${id}`);
  },

  setLeadBotDisabled: async (
    leadId: string | number,
    payload: { disabled: boolean; reason?: string }
  ) => {
    return apiClient.post(`/leads/${leadId}/bot-disabled`, payload);
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
      const url = qs ? `/appointments?${qs}` : `/appointments`;
      return apiClient.get(url);
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
      return apiClient.post(`/appointments`, {
        lead_id: payload.leadId ? Number(payload.leadId) : null,
        title: payload.title,
        description: payload.description,
        type: payload.type,
        status: payload.status ?? "pending",
        start_at: payload.startTime,
        end_at: payload.endTime ?? null,
      });
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
      return apiClient.patch(`/appointments/${id}`, {
        ...(payload.leadId !== undefined
          ? {
              lead_id: payload.leadId === null ? null : Number(payload.leadId),
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
      });
    },

    cancel: async (
      arg: string | number | { id: string | number; leadId: string | number }
    ) => {
      if (
        typeof arg === "object" &&
        arg !== null &&
        "id" in arg &&
        "leadId" in arg
      ) {
        const { id, leadId } = arg as { id: string | number; leadId: string | number };
        return api.updateAppointment(String(leadId), String(id), {
          status: "canceled",
        });
      }

      return api.appointments.update(arg as string | number, {
        status: "canceled",
      });
    },

    setOutcome: async (
      appointmentId: string | number,
      payload: {
        outcome: "completed" | "no_show" | "rescheduled";
        note?: string;
        reschedule_start_at?: string;
        reschedule_end_at?: string | null;
        reactivate_bot?: boolean;
        move_lead_to?: string | null;
      }
    ) => {
      return apiClient.post(`/appointments/${appointmentId}/outcome`, payload);
    },

    /**
     * (opcional) Remoção tolerante: aceita { id, leadId } e usa a rota por lead
     */
    remove: async (
      arg: string | number | { id: string | number; leadId: string | number }
    ) => {
      if (
        typeof arg === "object" &&
        arg !== null &&
        "id" in arg &&
        "leadId" in arg
      ) {
        const { id, leadId } = arg as { id: string | number; leadId: string | number };
        return apiClient.delete(`/leads/${leadId}/appointments/${id}`);
      }
      return apiClient.delete(`/appointments/${arg}`);
    },
  },

  getAppointments: async (leadId: number | string) => {
    return apiClient.get(`/leads/${leadId}/appointments`);
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
    const data = await apiClient.post(`/leads/${leadId}/appointments`, {
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
            end_at: payload.endAt === null ? null : payload.endAt.toISOString(),
          }
        : {}),
    });
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
    return apiClient.patch(`/leads/${leadId}/appointments/${appointmentId}`, {
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
            end_at: payload.endAt === null ? null : payload.endAt.toISOString(),
          }
        : {}),
    });
  },

  deleteAppointment: async (
    leadId: number | string,
    appointmentId: number | string
  ) => {
    return apiClient.delete(`/leads/${leadId}/appointments/${appointmentId}`);
  },

  // -------- PESQUISA (automação) --------
  pesquisa: {
    executar: async (payload: SearchPayload): Promise<ManifestResponse> => {
      return apiClient.post(`/pesquisa/executar`, payload);
    },

    downloadUrl: (runId: string, kind: "xlsx_validado" | "xlsx" | "csv") =>
      `${API_BASE}/pesquisa/baixar/${encodeURIComponent(runId)}/${kind}`,
  },

  // -------- UPLOADS da página Assistente IA --------
  uploads: {
    enviar: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return apiClient.post(`/uploads`, fd);
    },
  },

  // -------- ASSISTENTE IA --------
  assistenteIA: {
    processar: async (payload: any) => {
      return apiClient.post(`/assistente-ia/processar`, payload);
    },

    mensagens: async (
      leadId: number | string,
      latest = true
    ): Promise<{ ok: boolean; messages: LeadMessage[] }> => {
      return apiClient.get(
        `/assistente-ia/messages/${leadId}?latest=${latest}`
      );
    },

    preview: async (payload: {
      upload_id: string;
      overwrite: "skip" | "update" | "duplicate";
    }) => {
      return apiClient.post(`/assistente-ia/preview`, payload);
    },
  },

  // -------- PROSPECÇÃO --------
  prospeccao: {
    selecionarMensagem: async (
      leadId: number,
      channel: Channel,
      messageId: number
    ) => {
      return apiClient.post(`/prospeccao/select-message`, {
        lead_id: leadId,
        channel,
        message_id: messageId,
      });
    },

    selecoesDoLead: async (leadId: number): Promise<Record<string, number>> => {
      const data = await apiClient.get(`/prospeccao/selection/${leadId}`);
      return (data as any)?.selections ?? {};
    },

    registrarLog: async (payload: ProspectionLogPayload) => {
      return apiClient.post(`/prospeccao/log`, payload);
    },

    // Normaliza a resposta do backend (message_id -> id)
    saveMessage: async (
      payload: SaveMessagePayload
    ): Promise<SaveMessageResponse> => {
      const data = await apiClient.post(`/prospeccao/save-message`, payload);
      return {
        ok: !!(data as any)?.ok,
        id: Number((data as any)?.message_id ?? (data as any)?.id),
        selected: (data as any)?.selected ?? undefined,
      };
    },

    // alias compatível
    salvarMensagem: async (
      payload: SaveMessagePayload
    ): Promise<SaveMessageResponse> => api.prospeccao.saveMessage(payload),

    // ===== WhatsApp (envio automático via fila) =====
    whatsapp: {
      enqueue: async (
        payload: WhatsEnqueuePayload
      ): Promise<WhatsEnqueueResp> => {
        return apiClient.post(`/prospeccao/whatsapp/enqueue`, payload);
      },

      queue: async (limit = 5): Promise<WhatsQueueItem[]> => {
        return apiClient.get(
          `/prospeccao/whatsapp/queue?limit=${limit}`
        );
      },

      mark: async (payload: {
        lead_id: number;
        message_id: number;
        ok: boolean;
        notes?: string;
      }) => {
        return apiClient.post(`/prospeccao/whatsapp/mark`, payload);
      },

      recent: async (sinceSecs = 300) => {
        return apiClient.get(
          `/prospeccao/whatsapp/recent?since_secs=${sinceSecs}`
        );
      },
      summary: async () => {
        return apiClient.get(`/prospeccao/whatsapp/summary`);
      },
    },
  },

  // -------- WHATSAPP (QR via Selenium) --------
  whatsapp: {
    iniciarQR: async () => {
      return apiClient.post(`/whatsapp/iniciar-qr`);
    },
    verificarLogin: async (opts?: { passive?: boolean }) => {
      const passive = opts?.passive !== false;
      const qs = passive ? "?passive=1" : "";
      return apiClient.get(`/whatsapp/verificar-login${qs}`);
    },
    novoQR: async () => {
      return apiClient.get(`/whatsapp/novo-qr`);
    },
    stop: async () => {
      return apiClient.post(`/whatsapp/stop`);
    },
  },

  // -------- AUTH (MVP) --------
  auth: {
    login: async (email: string, password: string) => {
      const data = await apiClient.post(`${AUTH_BASE}/login`, { email, password });

      const accessToken =
        (data as any)?.access_token ?? (data as any)?.token ?? (data as any)?.accessToken;

      if (accessToken) {
        persistAuthToken(accessToken);
      }

      return data;
    },

    me: async () => {
      return apiClient.get<CoreUser>(`${CORE_BASE}/users/me`);
    },

    logout: async () => {
      clearAuthToken();
      return { ok: true };
    },
  },

  core: {
    getPlans: async (productCode?: string) => {
      const qs = productCode ? `?product_code=${encodeURIComponent(productCode)}` : "";
      return coreClient.get<CorePlan[]>(`/plans${qs}`);
    },
    getProducts: async () => coreClient.get<CoreProduct[]>("/products"),
    getEntitlements: async () =>
      coreClient.get<EntitlementsResponse>("/me/entitlements"),
    getAiTemplates: async () => coreClient.get<AiTemplate[]>("/ai-templates"),
    getAiProfileMe: async () => coreClient.get<AiProfile>("/ai-profiles/me"),
    createAiProfile: async (payload: AiProfilePayload) =>
      coreClient.post<AiProfile>(`/ai-profiles`, payload),
    updateAiProfileMe: async (payload: Partial<AiProfilePayload>) =>
      coreClient.put<AiProfile>(`/ai-profiles/me`, payload),
  },

  crm: {
    getKnowledgeList: async () => apiClient.get<KnowledgeItem[]>(`/knowledge`),
    createKnowledgeManual: async (payload: { title: string; content_text: string }) =>
      apiClient.post<KnowledgeItem>(`/knowledge`, payload),
    updateKnowledge: async (
      id: number,
      payload: Partial<{ title: string; content_text: string }>
    ) => apiClient.put<KnowledgeItem>(`/knowledge/${id}`, payload),
    deleteKnowledge: async (id: number) => apiClient.delete(`/knowledge/${id}`),
    uploadKnowledgeFile: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiClient.post<KnowledgeItem>(`/knowledge/upload`, formData);
    },
    whatsappConnect: async () => apiClient.post<WhatsappConnectResponse>(`/whatsapp/connect`),
    whatsappStatus: async () => apiClient.get<WhatsappStatusResponse>(`/whatsapp/status`),
    whatsappRefreshQr: async () =>
      apiClient.post<WhatsappConnectResponse>(`/whatsapp/qr/refresh`),
  },

  agents: {
    overview: async (seconds = 120) => {
      return apiClient.get(`/agents/overview?seconds=${seconds}`);
    },
    summary: async () => {
      return apiClient.get(`/agents/jobs/summary`);
    },
  },
};
