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

export type OfferPack = {
  items?: Array<{
    name?: string;
    price?: string;
    description?: string;
    checkout_link?: string;
    bullets?: string[];
  }> | null;
  checkout_link?: string | null;
  cta_text?: string | null;
  disclaimers?: string[] | null;
  // Mídia rica — Tarefa 3.6
  media_url?: string | null;
  media_type?: "image" | "video" | "audio" | null;
  anchor_price?: string | null;
  guarantee_text?: string | null;
  upsell_message?: string | null;
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
  agent_mode?: "consultivo" | "agenda" | "direto" | "sdr_scheduler" | "closer" | null;
  identity_mode?: "virtual_assistant" | "human_agent" | "user_clone";
  handoff_policy?: "disable_bot" | "keep_active_notify" | "ignore";
  handoff_custom_text?: string | null;
  requires_handoff?: boolean | null;
  human_in_loop?: boolean | null;
  followup_cadence?: number[] | null;
  followup_max_attempts?: number | null;
  followup_first_offset?: number | null;
  followup_allowed_hours?: string | null;
  origin_inbound_opener?: string | null;
  origin_outbound_opener?: string | null;
  objection_common?: string | null;
  qualification_score_threshold?: number | null;
  nurture_vs_discard_rule?: "nurture" | "discard" | null;
  warming_social_proof?: string | null;
  warming_session_preview?: string | null;
  offer_pack?: OfferPack | null;
  appointment_reminder_offsets?: number[] | null;
  briefing_enabled?: boolean | null;
  briefing_channel?: "whatsapp" | "internal" | null;
  briefing_lead_time?: number | null;
  operator_whatsapp?: string | null;
  buying_signal_keywords?: string[] | null;
  calendar_integration?: "none" | "google_calendar" | "calendly" | null;
  payment_gateway?: "hotmart" | "kiwify" | "stripe" | "generico" | null;
};

export type AiProfile = AiProfilePayload & {
  id?: number;
  user_id?: number;
  created_at?: string;
  updated_at?: string;
  payment_webhook_secret?: string | null;
  payment_webhook_url?: string | null;
};

export type FollowUpContract = {
  status: string;
  attempts: number;
  max_attempts: number;
  followup_variant?: string | null;
  next_followup_at: string | null;
  last_followup_at?: string | null;
  stop_reason?: string | null;
  manually_paused_at?: string | null;
  followup_goal?: string | null;
  meeting_or_session_happened?: string | null;
  outcome?: string | null;
  operator_note?: string | null;
  scheduled_message?: ScheduledMessage | null;
};

export type ScheduledMessage = {
  content: string;
  media_url?: string | null;
  media_type?: string | null;
  edited_by_user?: boolean;
  saved_at?: string | null;
};

export type FollowUpEditData = {
  lead_id: number;
  companyName: string;
  contactName: string | null;
  phone: string | null;
  agent_type: string | null;
  followup_status: string | null;
  next_followup_at: string | null;
  scheduled_message: ScheduledMessage | Record<string, never>;
  contract: FollowUpContract | null;
};

export type FollowUpLead = {
  id: number;
  companyName: string;
  contactName: string | null;
  phone: string | null;
  agent_type: string | null;
  followup_status: string | null;
  next_followup_at: string | null;
  followup_contract: FollowUpContract | null;
  lastMovement: string | null;
  createdAt: string | null;
  bot_disabled: number;
};

export type FollowUpStats = {
  total_active: number;
  hot_active: number;
  urgent_count: number;
  replied_today: number;
};

export type KnowledgeItem = {
  id: number;
  user_id: number;
  title: string;
  source_type: "manual" | "file";
  content_text: string;
  file_path?: string | null;
  category?: string | null;
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

export type AppNotification = {
  id: number;
  lead_id: number | null;
  type: string;
  created_at: string;
  companyName?: string | null;
  contactName?: string | null;
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
    country_code?: string | null;
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
      country_code: payload.country_code ?? null,
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

  startFollowup: async (payload: {
    lead_id: string | number;
    agent_type: "agent_1" | "agent_3";
    meeting_or_session_happened: "yes" | "no_show" | "canceled" | "needs_reschedule";
    outcome?: string | null;
    followup_goal?: string | null;
    proposal_sent?: boolean | null;
    operator_note?: string | null;
  }) => {
    return apiClient.post(`/leads/start-followup`, payload);
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
    regenerateWebhookSecret: async () =>
      coreClient.post<{ payment_webhook_secret: string; payment_webhook_url: string | null }>(
        `/ai-profiles/me/regenerate-webhook-secret`
      ),
  },

  crm: {
    getKnowledgeList: async () => apiClient.get<KnowledgeItem[]>(`/knowledge`),
    createKnowledgeManual: async (payload: { title: string; content_text: string; category?: string | null }) =>
      apiClient.post<KnowledgeItem>(`/knowledge`, payload),
    updateKnowledge: async (
      id: number,
      payload: Partial<{ title: string; content_text: string; category: string | null }>
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
      return apiClient.get<{ agents: any[] }>(`/agents/overview?seconds=${seconds}`);
    },
    summary: async () => {
      return apiClient.get(`/agents/jobs/summary`);
    },
    /** Lista todos os agentes locais (runners) do usuário autenticado */
    list: async (): Promise<import('../types/agente').AgenteRunner[]> => {
      const data = await apiClient.get<any[]>(`/agents/`);
      if (!Array.isArray(data)) return [];
      return data as import('../types/agente').AgenteRunner[];
    },
  },

  /** Métodos específicos do módulo de configuração do agente */
  agente: {
    /**
     * Carrega o perfil de IA + offer_pack e monta um AgentConfig completo.
     * Lê de GET /ai-profiles/me (backend-core).
     */
    getConfig: async (): Promise<import('../types/agente').AgentConfig> => {
      const profile = await coreClient.get<AiProfile>('/ai-profiles/me');
      const pack = (profile as any)?.offer_pack ?? {};
      const { DEFAULT_AGENT_CONFIG } = await import('../types/agente');

      return {
        // Camada 1
        name:              (profile as any)?.name              ?? DEFAULT_AGENT_CONFIG.name,
        brand_name:        (profile as any)?.brand_name        ?? DEFAULT_AGENT_CONFIG.brand_name,
        tone_of_voice:     (profile as any)?.tone_of_voice     ?? DEFAULT_AGENT_CONFIG.tone_of_voice,
        agent_mode:        (profile as any)?.agent_mode        ?? DEFAULT_AGENT_CONFIG.agent_mode,
        identity_mode:     (profile as any)?.identity_mode     ?? DEFAULT_AGENT_CONFIG.identity_mode,
        template_key:      (profile as any)?.template_key      ?? DEFAULT_AGENT_CONFIG.template_key,
        handoff_policy:    (profile as any)?.handoff_policy    ?? DEFAULT_AGENT_CONFIG.handoff_policy,
        requires_handoff:  (profile as any)?.requires_handoff  ?? DEFAULT_AGENT_CONFIG.requires_handoff,
        human_in_loop:     (profile as any)?.human_in_loop     ?? DEFAULT_AGENT_CONFIG.human_in_loop,
        timezone:          (profile as any)?.timezone          ?? DEFAULT_AGENT_CONFIG.timezone,
        custom_instructions: (profile as any)?.custom_instructions ?? DEFAULT_AGENT_CONFIG.custom_instructions,

        // Camada 2
        niche:            (profile as any)?.niche            ?? DEFAULT_AGENT_CONFIG.niche,
        target_audience:  (profile as any)?.target_audience  ?? DEFAULT_AGENT_CONFIG.target_audience,
        offer_description:(profile as any)?.offer_description ?? DEFAULT_AGENT_CONFIG.offer_description,
        goals:            (profile as any)?.goals            ?? DEFAULT_AGENT_CONFIG.goals,
        ticket_range:     pack.ticket_range   ?? DEFAULT_AGENT_CONFIG.ticket_range,
        main_pain:        pack.main_pain      ?? DEFAULT_AGENT_CONFIG.main_pain,
        main_objection:   pack.main_objection ?? DEFAULT_AGENT_CONFIG.main_objection,
        f1_questions:     pack.f1_questions   ?? DEFAULT_AGENT_CONFIG.f1_questions,
        f2_questions:     pack.f2_questions   ?? DEFAULT_AGENT_CONFIG.f2_questions,
        f3_questions:     pack.f3_questions   ?? DEFAULT_AGENT_CONFIG.f3_questions,

        // Camada 1 — Contexto de abertura
        handoff_custom_text:    pack.handoff_custom_text    ?? DEFAULT_AGENT_CONFIG.handoff_custom_text,
        origin_inbound_opener:  pack.origin_inbound_opener  ?? DEFAULT_AGENT_CONFIG.origin_inbound_opener,
        origin_outbound_opener: pack.origin_outbound_opener ?? DEFAULT_AGENT_CONFIG.origin_outbound_opener,
        warming_social_proof:   pack.warming_social_proof   ?? DEFAULT_AGENT_CONFIG.warming_social_proof,
        warming_session_preview:pack.warming_session_preview?? DEFAULT_AGENT_CONFIG.warming_session_preview,

        // Camada 3
        media_fallback:     pack.media_fallback     ?? DEFAULT_AGENT_CONFIG.media_fallback,
        media_fallback_msg: pack.media_fallback_msg ?? DEFAULT_AGENT_CONFIG.media_fallback_msg,
        opt_out_keywords:   pack.opt_out_keywords   ?? DEFAULT_AGENT_CONFIG.opt_out_keywords,
        opt_out_disable:    pack.opt_out_disable     ?? DEFAULT_AGENT_CONFIG.opt_out_disable,
        opt_out_notify:     pack.opt_out_notify      ?? DEFAULT_AGENT_CONFIG.opt_out_notify,
        opt_out_confirm:    pack.opt_out_confirm     ?? DEFAULT_AGENT_CONFIG.opt_out_confirm,
        opt_out_confirm_msg:pack.opt_out_confirm_msg ?? DEFAULT_AGENT_CONFIG.opt_out_confirm_msg,
        lgpd_mode:          pack.lgpd_mode           ?? DEFAULT_AGENT_CONFIG.lgpd_mode,
        lgpd_msg:           pack.lgpd_msg            ?? DEFAULT_AGENT_CONFIG.lgpd_msg,
        reactivation_mode:  pack.reactivation_mode   ?? DEFAULT_AGENT_CONFIG.reactivation_mode,
        reactivation_msg:   pack.reactivation_msg    ?? DEFAULT_AGENT_CONFIG.reactivation_msg,
        followup_h1:        pack.followup_h1         ?? DEFAULT_AGENT_CONFIG.followup_h1,
        followup_h2:        pack.followup_h2         ?? DEFAULT_AGENT_CONFIG.followup_h2,
        followup_h3:        pack.followup_h3         ?? DEFAULT_AGENT_CONFIG.followup_h3,
        daily_limit:        pack.daily_limit         ?? DEFAULT_AGENT_CONFIG.daily_limit,
        interval_min:       pack.interval_min        ?? DEFAULT_AGENT_CONFIG.interval_min,
        interval_max:       pack.interval_max        ?? DEFAULT_AGENT_CONFIG.interval_max,

        // Camada 2 — Qualificação avançada
        qualification_score_threshold: pack.qualification_score_threshold ?? DEFAULT_AGENT_CONFIG.qualification_score_threshold,
        nurture_vs_discard_rule:        pack.nurture_vs_discard_rule        ?? DEFAULT_AGENT_CONFIG.nurture_vs_discard_rule,
        buying_signal_keywords:         pack.buying_signal_keywords         ?? DEFAULT_AGENT_CONFIG.buying_signal_keywords,

        // Camada 3 — Follow-up avançado
        followup_max_attempts:  pack.followup_max_attempts  ?? DEFAULT_AGENT_CONFIG.followup_max_attempts,
        followup_first_offset:  pack.followup_first_offset  ?? DEFAULT_AGENT_CONFIG.followup_first_offset,
        followup_cadence:       pack.followup_cadence       ?? DEFAULT_AGENT_CONFIG.followup_cadence,
        followup_allowed_hours: pack.followup_allowed_hours ?? DEFAULT_AGENT_CONFIG.followup_allowed_hours,

        // Apresentação e agendamento
        appointment_reminder_h1: pack.appointment_reminder_h1 ?? DEFAULT_AGENT_CONFIG.appointment_reminder_h1,
        appointment_reminder_h2: pack.appointment_reminder_h2 ?? DEFAULT_AGENT_CONFIG.appointment_reminder_h2,
        briefing_enabled:        pack.briefing_enabled        ?? DEFAULT_AGENT_CONFIG.briefing_enabled,
        briefing_channel:        pack.briefing_channel        ?? DEFAULT_AGENT_CONFIG.briefing_channel,
        briefing_lead_time:      pack.briefing_lead_time      ?? DEFAULT_AGENT_CONFIG.briefing_lead_time,
        operator_whatsapp:       pack.operator_whatsapp       ?? DEFAULT_AGENT_CONFIG.operator_whatsapp,
        calendar_integration:    pack.calendar_integration    ?? DEFAULT_AGENT_CONFIG.calendar_integration,

        // Oferta e pagamento
        offer_media_url:      pack.media_url      ?? DEFAULT_AGENT_CONFIG.offer_media_url,
        offer_media_type:     pack.media_type     ?? DEFAULT_AGENT_CONFIG.offer_media_type,
        offer_anchor_price:   pack.anchor_price   ?? DEFAULT_AGENT_CONFIG.offer_anchor_price,
        offer_guarantee_text: pack.guarantee_text ?? DEFAULT_AGENT_CONFIG.offer_guarantee_text,
        offer_upsell_message: pack.upsell_message ?? DEFAULT_AGENT_CONFIG.offer_upsell_message,
        payment_gateway:      (profile as any)?.payment_gateway      ?? DEFAULT_AGENT_CONFIG.payment_gateway,
        payment_webhook_url:  (profile as any)?.payment_webhook_url  ?? DEFAULT_AGENT_CONFIG.payment_webhook_url,
        payment_webhook_secret:(profile as any)?.payment_webhook_secret ?? DEFAULT_AGENT_CONFIG.payment_webhook_secret,
      };
    },

    /**
     * Salva configuração: campos de ai_profile via PUT /ai-profiles/me,
     * campos extras via offer_pack no mesmo payload.
     */
    saveConfig: async (config: import('../types/agente').AgentConfig): Promise<void> => {
      const offer_pack = {
        // Camada 1 — Contexto de abertura
        handoff_custom_text:     config.handoff_custom_text,
        origin_inbound_opener:   config.origin_inbound_opener,
        origin_outbound_opener:  config.origin_outbound_opener,
        warming_social_proof:    config.warming_social_proof,
        warming_session_preview: config.warming_session_preview,

        // Camada 2
        ticket_range:        config.ticket_range,
        main_pain:           config.main_pain,
        main_objection:      config.main_objection,
        f1_questions:        config.f1_questions,
        f2_questions:        config.f2_questions,
        f3_questions:        config.f3_questions,

        // Camada 2 — Qualificação avançada
        qualification_score_threshold: config.qualification_score_threshold,
        nurture_vs_discard_rule:        config.nurture_vs_discard_rule,
        buying_signal_keywords:         config.buying_signal_keywords,

        // Camada 3
        media_fallback:      config.media_fallback,
        media_fallback_msg:  config.media_fallback_msg,
        opt_out_keywords:    config.opt_out_keywords,
        opt_out_disable:     config.opt_out_disable,
        opt_out_notify:      config.opt_out_notify,
        opt_out_confirm:     config.opt_out_confirm,
        opt_out_confirm_msg: config.opt_out_confirm_msg,
        lgpd_mode:           config.lgpd_mode,
        lgpd_msg:            config.lgpd_msg,
        reactivation_mode:   config.reactivation_mode,
        reactivation_msg:    config.reactivation_msg,
        followup_h1:         config.followup_h1,
        followup_h2:         config.followup_h2,
        followup_h3:         config.followup_h3,
        daily_limit:         config.daily_limit,
        interval_min:        config.interval_min,
        interval_max:        config.interval_max,

        // Camada 3 — Follow-up avançado
        followup_max_attempts:  config.followup_max_attempts,
        followup_first_offset:  config.followup_first_offset,
        followup_cadence:       config.followup_cadence,
        followup_allowed_hours: config.followup_allowed_hours,

        // Apresentação e agendamento
        appointment_reminder_h1: config.appointment_reminder_h1,
        appointment_reminder_h2: config.appointment_reminder_h2,
        briefing_enabled:        config.briefing_enabled,
        briefing_channel:        config.briefing_channel,
        briefing_lead_time:      config.briefing_lead_time,
        operator_whatsapp:       config.operator_whatsapp,
        calendar_integration:    config.calendar_integration,

        // Oferta e pagamento
        media_url:      config.offer_media_url,
        media_type:     config.offer_media_type,
        anchor_price:   config.offer_anchor_price,
        guarantee_text: config.offer_guarantee_text,
        upsell_message: config.offer_upsell_message,
      };

      await coreClient.put('/ai-profiles/me', {
        name:                config.name,
        brand_name:          config.brand_name,
        tone_of_voice:       config.tone_of_voice,
        agent_mode:          config.agent_mode,
        identity_mode:       config.identity_mode,
        template_key:        config.template_key,
        handoff_policy:      config.handoff_policy,
        requires_handoff:    config.requires_handoff,
        human_in_loop:       config.human_in_loop,
        timezone:            config.timezone,
        custom_instructions: config.custom_instructions,
        niche:               config.niche,
        target_audience:     config.target_audience,
        offer_description:   config.offer_description,
        goals:               config.goals,
        payment_gateway:     config.payment_gateway,
        offer_pack,
      });
    },
  },

  notifications: {
    getUnread: () => apiClient.get<AppNotification[]>("/notifications/unread"),
    markRead: (id: number) => apiClient.post(`/notifications/${id}/read`, {}),
    markAllRead: () => apiClient.post("/notifications/read-all", {}),
  },

  followUps: {
    listActive: () => apiClient.get<FollowUpLead[]>("/leads/followups/active"),
    getStats: () => apiClient.get<FollowUpStats>("/leads/followups/stats"),
    pause: (id: number) => apiClient.post(`/leads/${id}/followup/pause`),
    resume: (id: number) => apiClient.post(`/leads/${id}/followup/resume`),
    cancel: (id: number) => apiClient.post(`/leads/${id}/followup/cancel`),
    getScheduledMessage: (id: number) =>
      apiClient.get<FollowUpEditData>(`/leads/${id}/followup/scheduled-message`),
    saveScheduledMessage: (
      id: number,
      payload: { content: string; media_url?: string | null; media_type?: string | null }
    ) => apiClient.put(`/leads/${id}/followup/scheduled-message`, payload),
    regenerate: (id: number) =>
      apiClient.post<{ content: string; generated: boolean; attempts: number; max_attempts: number }>(
        `/leads/${id}/followup/regenerate`
      ),
    sendNow: (
      id: number,
      payload: { content: string; media_url?: string | null; media_type?: string | null }
    ) => apiClient.post(`/leads/${id}/followup/send-now`, payload),
    uploadMedia: async (id: number, file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return apiClient.post<{ ok: boolean; filename: string; media_url: string; ext: string }>(
        `/leads/${id}/followup/upload-media`,
        fd
      );
    },
  },
};
