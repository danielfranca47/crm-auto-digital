import { readAdminToken } from "@/lib/admin-token";

const CORE_BASE = (import.meta.env.VITE_CORE_BASE as string) || "http://localhost:8001";
const CRM_BASE = (import.meta.env.VITE_CRM_BASE as string) || "http://localhost:8000";

function adminHeaders(): HeadersInit {
  const token = readAdminToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function coreGet<T>(path: string): Promise<T> {
  const res = await fetch(`${CORE_BASE}${path}`, { headers: adminHeaders() });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function corePost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${CORE_BASE}${path}`, {
    method: "POST",
    headers: adminHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function corePatch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${CORE_BASE}${path}`, {
    method: "PATCH",
    headers: adminHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function crmGet<T>(path: string): Promise<T> {
  const res = await fetch(`${CRM_BASE}${path}`, { headers: adminHeaders() });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function crmPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${CRM_BASE}${path}`, {
    method: "POST",
    headers: adminHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export type AdminStats = {
  total_users: number;
  active_subscriptions: number;
  instances_total: number;
  instances_online: number;
  instances_offline: number;
  subscriptions_by_plan: Array<{ plan: string; count: number }>;
};

export type AdminUser = {
  id: number;
  email: string;
  name?: string;
  status: string;
  created_at: string;
  enabled_extensions?: string[];
  plan_name?: string;
  plan_code?: string;
  subscription_status?: string;
  subscription_period_start?: string;
  subscription_period_end?: string;
  subscription_is_trial?: boolean;
};

export type CrmPlan = {
  code: string;
  name: string;
  billing_period: string;
  product_code: string;
};

export type PlanLimits = {
  plan_code: string;
  plan_name: string;
  max_leads: number | null;
  max_ia_conversas_monthly: number | null;
  max_whatsapp_send_daily: number | null;
  follow_up_enabled: boolean | null;
  playground_monthly_limit: number | null;
  max_agents_local: number | null;
};

export type AdminInstance = {
  id: number;
  instance_id: string;
  user_id: number;
  user_email: string;
  phone_e164: string | null;
  provider: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
};

export type AgentStage = {
  key: string;
  label: string;
  description: string;
  sample_questions?: string[];
  tone_rule?: string;
  followup_attempts?: number[];
  followup_outcomes?: Record<string, string>;
};

export type AgentModeOverview = {
  key: string;
  name: string;
  description: string;
  canonical_agent_mode: string;
  max_chars?: number;
  response_style?: string;
  default_next_action?: string;
  tone_rule?: string;
  has_warming: boolean;
  has_followup_attempts: boolean;
  has_followup_outcomes: boolean;
  stages: AgentStage[];
};

export type AgentsOverview = {
  agent_modes: AgentModeOverview[];
  queried_at: string;
};

export type UserProfile = {
  user_id: number;
  email?: string;
  name?: string;
  brand_name?: string;
  niche?: string;
  template_key?: string;
  agent_mode?: string;
  presentation_variant?: string;
  hybrid_flow_style?: string;
  offer_pack?: unknown;
  llm_provider?: string;
  llm_provider_model?: string | null;
  qualification_score_threshold?: number;
  qualification_required_fields?: string[];
  qualification_extraction_tolerance?: string;
  followup_max_attempts?: number;
  has_custom_config: boolean;
};

export type AgentsUsers = {
  users: UserProfile[];
};

export type UserDetail = {
  user_id: number;
  profile: Record<string, unknown>;
  playbook: {
    key: string;
    name: string;
    description: string;
    canonical_agent_mode: string;
    max_chars?: number;
    response_style?: string;
    tone_rule?: string;
    stages: AgentStage[];
  };
  diff: Record<string, { default: unknown; user: unknown }>;
  has_custom_config: boolean;
  default_qual_fields_for_mode: string[];
};

// ── API ───────────────────────────────────────────────────────────────────────

export const api = {
  login: (secret: string) =>
    corePost<{ access_token: string }>("/admin/login", { secret }),

  getStats: () => coreGet<AdminStats>("/admin/stats"),

  listUsers: (search?: string) => {
    const qs = search ? `?search=${encodeURIComponent(search)}` : "";
    return coreGet<AdminUser[]>(`/admin/users${qs}`);
  },

  setExtensions: (userId: number, extensions: string[]) =>
    corePatch<{ ok: boolean; enabled_extensions: string[] }>(
      `/admin/users/${userId}/extensions`,
      { enabled_extensions: extensions }
    ),

  createUser: (email: string, name?: string) =>
    corePost<{ ok: boolean; user_id: number; email: string; email_sent: boolean }>(
      "/admin/users",
      { email, ...(name ? { name } : {}) }
    ),

  listCrmPlans: () => coreGet<CrmPlan[]>("/plans?product_code=crm"),

  assignPlan: (userId: number, planCode: string, months: number, isTrial: boolean) =>
    corePost<{ ok: boolean; plan_name: string; current_period_end: string }>(
      `/admin/users/${userId}/subscription`,
      { plan_code: planCode, months, is_trial: isTrial }
    ),

  refundUser: (email: string) =>
    crmPost<{ ok: boolean; refunded: boolean; plan_code: string }>(
      "/admin/billing/refund",
      { email }
    ),

  adminListPlans: () => coreGet<PlanLimits[]>("/admin/plans"),

  listInstances: () => coreGet<AdminInstance[]>("/admin/instances"),

  reconnectInstance: (instanceId: string) =>
    corePost<{ ok: boolean; error?: string; result?: unknown }>(
      `/admin/instances/${instanceId}/reconnect`
    ),

  getAgentsOverview: () => crmGet<AgentsOverview>("/admin/agents/overview"),

  getAgentsUsers: () => crmGet<AgentsUsers>("/admin/agents/users"),

  getAgentUserDetail: (userId: number) =>
    crmGet<UserDetail>(`/admin/agents/users/${userId}`),
};
