// ─────────────────────────────────────────────────────────────
// Tipos do módulo de Agente (dashboard + configuração)
// ─────────────────────────────────────────────────────────────

/** Resposta de GET /api/agents/ (agente local / runner) */
export interface AgenteRunner {
  agent_id: string;
  name: string | null;
  capabilities: string[] | null;
  status: 'online' | 'offline' | 'disabled' | null;
  last_seen_at: string | null;
  revoked: boolean;
  online: boolean;
}

// ─── Configuração central do agente ──────────────────────────

/** Campos da Camada 2 e 3 estendidos — armazenados em offer_pack */
export interface OfferPackExtra {
  // Camada 2 — Contexto do negócio
  ticket_range?: string;
  main_pain?: string;
  main_objection?: string;
  f1_questions?: string[];
  f2_questions?: string[];
  f3_questions?: string[];

  // Camada 3 — Comportamento por evento
  media_fallback?: string;
  media_fallback_msg?: string;
  opt_out_keywords?: string[];
  opt_out_disable?: boolean;
  opt_out_notify?: boolean;
  opt_out_confirm?: boolean;
  opt_out_confirm_msg?: string;
  lgpd_mode?: string;
  lgpd_msg?: string;
  reactivation_mode?: string;
  reactivation_msg?: string;

  // Camada 3 — Cadência
  followup_h1?: number;
  followup_h2?: number;
  followup_h3?: number;
  daily_limit?: number;
  interval_min?: number;
  interval_max?: number;
}

/** Estado completo do formulário de configuração do agente */
export interface AgentConfig {
  // ── Camada 1 — Identidade ────────────────────────────────
  name: string;
  brand_name: string;
  tone_of_voice: string;
  agent_mode: 'sdr_scheduler' | 'closer' | 'consultivo' | 'agenda' | 'direto';
  identity_mode: 'human_agent' | 'virtual_assistant' | 'user_clone';
  template_key: string;
  handoff_policy: 'disable_bot' | 'keep_active_notify' | 'ignore';
  requires_handoff: boolean;
  human_in_loop: boolean;
  timezone: string;
  custom_instructions: string;

  // ── Camada 2 — Qualificação ──────────────────────────────
  niche: string;
  target_audience: string;
  offer_description: string;
  goals: string;
  ticket_range: string;
  main_pain: string;
  main_objection: string;
  f1_questions: string[];
  f2_questions: string[];
  f3_questions: string[];

  // ── Camada 3 — Pipeline ──────────────────────────────────
  media_fallback: string;
  media_fallback_msg: string;
  opt_out_keywords: string[];
  opt_out_disable: boolean;
  opt_out_notify: boolean;
  opt_out_confirm: boolean;
  opt_out_confirm_msg: string;
  lgpd_mode: string;
  lgpd_msg: string;
  reactivation_mode: string;
  reactivation_msg: string;
  followup_h1: number;
  followup_h2: number;
  followup_h3: number;
  daily_limit: number;
  interval_min: number;
  interval_max: number;
}

/** Valores padrão para o estado inicial (antes de carregar da API) */
export const DEFAULT_AGENT_CONFIG: AgentConfig = {
  name: '',
  brand_name: '',
  tone_of_voice: 'equilibrado',
  agent_mode: 'sdr_scheduler',
  identity_mode: 'human_agent',
  template_key: 'sdr_padrao',
  handoff_policy: 'keep_active_notify',
  requires_handoff: false,
  human_in_loop: false,
  timezone: 'America/Sao_Paulo',
  custom_instructions: '',

  niche: '',
  target_audience: '',
  offer_description: '',
  goals: '',
  ticket_range: '',
  main_pain: '',
  main_objection: '',
  f1_questions: [],
  f2_questions: [],
  f3_questions: [],

  media_fallback: 'continuar',
  media_fallback_msg: 'Oi! Não consegui abrir o que você enviou. Pode me responder em texto? Assim consigo te ajudar melhor 😊',
  opt_out_keywords: ['PARAR', 'STOP', 'SAIR', 'CANCELAR', 'NÃO QUERO'],
  opt_out_disable: true,
  opt_out_notify: true,
  opt_out_confirm: true,
  opt_out_confirm_msg: 'Entendido! Você foi removido da nossa lista e não receberá mais mensagens. Se quiser retomar o contato, é só nos enviar uma mensagem. 😊',
  lgpd_mode: '',
  lgpd_msg: 'Olá! Para continuar, preciso da sua confirmação: você aceita receber mensagens nossas por este canal? Responda SIM para confirmar.',
  reactivation_mode: '',
  reactivation_msg: 'Que bom te ver de volta! Lembro que conversamos antes. O que mudou desde então?',
  followup_h1: 24,
  followup_h2: 72,
  followup_h3: 168,
  daily_limit: 200,
  interval_min: 3,
  interval_max: 8,
};

// ─── Dashboard ────────────────────────────────────────────────

/** Estatísticas computadas a partir dos leads para o dashboard */
export interface DashboardStats {
  leadsAtivos: number;
  qualificados: number;
  agendamentos: number;
  taxaResposta: number | null;
}

/** Item do funil para FunilAgente */
export interface FunilItem {
  stage: string;
  label: string;
  count: number;
  pct: number;
  color: string;
}

/** Lead "quente" para LeadsQuentes */
export interface LeadQuente {
  id: string | number;
  name: string;
  initials: string;
  stage: string;
  score: number;
  temp: 'hot' | 'warm' | 'cold';
}

/** Entrada do log de atividade */
export interface ActivityEntry {
  time: string;
  text: string;
  boldText?: string;
  color: string;
}

// ─── Labels legíveis ─────────────────────────────────────────

export const AGENT_MODE_LABELS: Record<string, string> = {
  sdr_scheduler: 'SDR · Agendamento',
  closer:        'Closer · Direto',
  consultivo:    'Consultivo',
  agenda:        'Foco em Agenda',
  direto:        'Vendedor Direto',
};

export const IDENTITY_MODE_LABELS: Record<string, string> = {
  human_agent:       'Humano do time',
  virtual_assistant: 'Assistente Virtual',
  user_clone:        'Clone do usuário',
};

export const TEMPLATE_KEY_LABELS: Record<string, string> = {
  sdr_padrao:           'SDR Padrão',
  consultor_especialista: 'Consultor Especialista',
  closer_agressivo:     'Closer Agressivo',
  hybrid_scheduler:     'Híbrido Agendador',
};

export const HANDOFF_LABELS: Record<string, string> = {
  disable_bot:        'Desabilitar bot',
  keep_active_notify: 'Manter ativo e notificar',
  ignore:             'Ignorar',
};

export const LGPD_LABELS: Record<string, string> = {
  inbound:  'Inbound implícito',
  explicit: 'Confirmação explícita',
  outbound: 'Apenas no outbound',
};

export const REATIVACAO_LABELS: Record<string, string> = {
  'reativar-notificar': 'Reativar e notificar operador',
  reiniciar:            'Reativar e reiniciar do início',
  retomar:              'Reativar e retomar do ponto exato',
  'notificar-somente':  'Manter arquivado e notificar',
};

export const MEDIA_FALLBACK_LABELS: Record<string, string> = {
  continuar: 'Responder e continuar',
  pausar:    'Responder e pausar',
  ignorar:   'Ignorar silenciosamente',
};
