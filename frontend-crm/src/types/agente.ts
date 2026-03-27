// ─────────────────────────────────────────────────────────────
// Tipos do módulo de Agente (dashboard + configuração)
// ─────────────────────────────────────────────────────────────

/** Resposta de GET /api/agents/ (agente local / runner)
 *  A API serializa com alias: o campo JSON é "id", não "agent_id"
 */
export interface AgenteRunner {
  id: string;
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
  handoff_custom_text: string;
  requires_handoff: boolean;
  human_in_loop: boolean;
  timezone: string;
  custom_instructions: string;

  // ── Camada 1 — Contexto de abertura ──────────────────────
  origin_inbound_opener: string;
  origin_outbound_opener: string;
  warming_social_proof: string;
  warming_session_preview: string;

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

  // ── Camada 2 — Qualificação avançada ─────────────────────
  qualification_score_threshold: number;
  nurture_vs_discard_rule: boolean;
  buying_signal_keywords: string[];

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

  // ── Camada 3 — Follow-up avançado ────────────────────────
  followup_max_attempts: number;
  followup_first_offset: number;
  followup_cadence: string;
  followup_allowed_hours: string;

  // ── Apresentação e agendamento ───────────────────────────
  appointment_reminder_h1: number;
  appointment_reminder_h2: number;
  briefing_enabled: boolean;
  briefing_channel: string;
  briefing_lead_time: number;
  operator_whatsapp: string;
  calendar_integration: string;

  // ── Oferta e pagamento ───────────────────────────────────
  offer_media_url: string;
  offer_media_type: string;
  offer_anchor_price: string;
  offer_guarantee_text: string;
  offer_upsell_message: string;
  payment_gateway: string;
  payment_webhook_url: string;
  payment_webhook_secret: string;
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
  handoff_custom_text: '',
  requires_handoff: false,
  human_in_loop: false,
  timezone: 'America/Sao_Paulo',
  custom_instructions: '',

  origin_inbound_opener: '',
  origin_outbound_opener: '',
  warming_social_proof: '',
  warming_session_preview: '',

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

  qualification_score_threshold: 6,
  nurture_vs_discard_rule: false,
  buying_signal_keywords: [],

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

  followup_max_attempts: 3,
  followup_first_offset: 60,
  followup_cadence: '60,1440,4320',
  followup_allowed_hours: '08:00-20:00',

  appointment_reminder_h1: 24,
  appointment_reminder_h2: 2,
  briefing_enabled: false,
  briefing_channel: 'whatsapp',
  briefing_lead_time: 1,
  operator_whatsapp: '',
  calendar_integration: 'none',

  offer_media_url: '',
  offer_media_type: 'image',
  offer_anchor_price: '',
  offer_guarantee_text: '',
  offer_upsell_message: '',
  payment_gateway: '',
  payment_webhook_url: '',
  payment_webhook_secret: '',
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

// ─── Presets de agente (mapeiam os 3 arquétipos de /agentes-info) ──
export const AGENT_PRESETS = [
  {
    key: 'a1',
    chip: 'Agente 01 · Robusto',
    title: 'SDR de Alto Ticket',
    subtitle: '+ Follow-up Pós-Apresentação',
    desc: 'Qualifica profundamente antes de acionar o humano. Ideal para ciclos longos e alto ticket.',
    useCases: ['Imóveis · Advocacia', 'Clínicas estéticas', 'Consultorias B2B', 'Alto ticket'],
    template_key: 'sdr_padrao',
    agent_mode: 'sdr_scheduler' as const,
  },
  {
    key: 'a2',
    chip: 'Agente 02 · Direto',
    title: 'Vendedor Autônomo',
    subtitle: 'Low Ticket',
    desc: '100% automatizado — qualifica, apresenta e fecha sem intervenção humana.',
    useCases: ['Infoprodutos', 'E-commerce', 'Cursos · Assinaturas'],
    template_key: 'closer_agressivo',
    agent_mode: 'direto' as const,
  },
  {
    key: 'a3',
    chip: 'Agente 03 · Híbrido',
    title: 'Assistente Comercial',
    subtitle: 'com Agendamento Inteligente',
    desc: 'Qualifica, agenda e entrega o lead preparado para o profissional. Não fecha — mas faz tudo antes.',
    useCases: ['Coaches · Terapeutas', 'Personal Trainers', 'Consultores solo'],
    template_key: 'hybrid_scheduler',
    agent_mode: 'agenda' as const,
  },
] as const;

/** Retorna o preset ativo com base nos valores atuais, ou null se for combinação customizada */
export function getActivePreset(template_key: string, agent_mode: string) {
  return AGENT_PRESETS.find(
    p => p.template_key === template_key && p.agent_mode === agent_mode,
  ) ?? null;
}

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

export const CALENDAR_INTEGRATION_LABELS: Record<string, string> = {
  none:            'Sem integração',
  google_calendar: 'Google Calendar',
  calendly:        'Calendly',
};

// ─── Camada 4: Categorias de Conhecimento por Preset ─────────

export interface KnowledgeCategory {
  key: string;
  label: string;
  description: string;
  hint: string;
  placeholder: string;
  importance: 'critical' | 'recommended' | 'optional';
}

const CAT_SOCIAL_PROOF_SDR: KnowledgeCategory = {
  key: 'social_proof',
  label: 'Prova Social',
  description: 'Casos de sucesso com resultados concretos para usar no F3 e no aquecimento.',
  hint: 'Escreva 2–4 casos reais: nome do cliente (ou perfil), problema que tinha, resultado obtido em números. Ex: "Empresa de logística com 80 colaboradores — reduziu custo de aquisição em 35% em 3 meses."',
  placeholder: 'Cliente 1: [setor/perfil] — Problema: [...] — Resultado: [...]\nCliente 2: [setor/perfil] — Problema: [...] — Resultado: [...]',
  importance: 'critical',
};

const CAT_OBJECTIONS_SDR: KnowledgeCategory = {
  key: 'objections_faq',
  label: 'Objeções e Respostas',
  description: 'As objeções mais comuns antes de aceitar uma reunião e como o agente deve responder.',
  hint: 'Liste cada objeção e a resposta recomendada. Foque em: preço ("está caro"), timing ("não é o momento"), decisor ("preciso consultar meu sócio"), concorrência ("já uso outra solução").',
  placeholder: 'Objeção: "Está caro para o nosso momento."\nResposta: "Entendo. Muitos dos nossos clientes disseram o mesmo antes — e descobrimos que o custo de não resolver isso costuma ser maior. Posso te mostrar como calculamos isso?"\n\nObjeção: "Preciso falar com meu sócio."\nResposta: "Faz todo sentido. Para facilitar, posso montar um resumo de 1 página para você apresentar — ou podemos incluí-lo na próxima conversa diretamente?"',
  importance: 'critical',
};

const CAT_COMPANY_PROFILE: KnowledgeCategory = {
  key: 'company_profile',
  label: 'Perfil da Empresa',
  description: 'Quem é a empresa, o que oferece, diferenciais e mercado de atuação.',
  hint: 'Descreva: nome oficial, segmento, o que entrega, para quem, e o principal diferencial competitivo. O agente usa isso para responder "quem vocês são?" durante a qualificação.',
  placeholder: 'Nome: [Empresa]\nSegmento: [Ex: Software B2B para gestão financeira]\nO que entrega: [Ex: Plataforma de automação de contas a pagar com conciliação bancária]\nPara quem: [Ex: Empresas de médio porte com faturamento acima de R$ 5M/ano]\nDiferencial: [Ex: Implementação em 2 semanas, sem migração de dados manual]',
  importance: 'critical',
};

const CAT_QUALIFICATION_CRITERIA: KnowledgeCategory = {
  key: 'qualification_criteria',
  label: 'Critérios de Qualificação',
  description: 'O que define um lead qualificado: setor, porte, budget mínimo, cargo do decisor.',
  hint: 'Defina os critérios de aprovação para F1 e F3. O agente usa isso para decidir se avança ou encerra a conversa.',
  placeholder: 'Aprovado se:\n- Faturamento acima de R$ 2M/ano\n- Setor: [indústria, logística, varejo B2B]\n- Decisor: sócio, CEO, CFO ou diretor\n- Budget: mínimo R$ 3.000/mês\n- Timing: necessidade nos próximos 90 dias\n\nDesqualificado se:\n- Empresa com menos de 10 funcionários\n- Apenas operacional tomando a decisão',
  importance: 'recommended',
};

const CAT_PRE_MEETING_FAQ: KnowledgeCategory = {
  key: 'pre_meeting_faq',
  label: 'FAQ Pré-Reunião',
  description: 'Perguntas frequentes que o lead faz antes de aceitar agendar uma reunião.',
  hint: 'Liste perguntas e respostas curtas. Ex: duração, formato (presencial/online), o que precisa preparar, se é uma venda ou uma conversa exploratória.',
  placeholder: '"Quanto tempo dura a reunião?" → 30–40 minutos.\n"É presencial ou online?" → Online via Google Meet, com link enviado na confirmação.\n"Vou ser pressionado a comprar?" → Não — é uma conversa de diagnóstico. Você só decide se fizer sentido.\n"Preciso preparar algo?" → Não é necessário, mas se puder, nos diga o maior desafio atual.',
  importance: 'recommended',
};

const CAT_PRICE_POLICY: KnowledgeCategory = {
  key: 'price_policy',
  label: 'Política de Preço',
  description: 'O que o agente pode e não pode dizer sobre preço antes da reunião com o vendedor.',
  hint: 'Defina se o agente deve citar faixas de preço, dizer que o preço é apresentado na reunião, ou dar uma âncora de valor. Seja específico para evitar que o agente improvise.',
  placeholder: 'O agente NÃO deve citar preços específicos antes da reunião.\nSe perguntado, responder: "O investimento varia conforme o tamanho e as necessidades da sua operação — por isso a reunião existe, para entendermos o que faz sentido para vocês."\nFaixa de referência (para citar apenas se o lead insistir): a partir de R$ X/mês.',
  importance: 'recommended',
};

const CAT_PITCH_SCRIPT: KnowledgeCategory = {
  key: 'pitch_script',
  label: 'Script de Pitch',
  description: 'A apresentação completa do produto que o agente usa para fechar a venda.',
  hint: 'Escreva o script seguindo a estrutura: 1) Dor (eco da dor do lead), 2) Solução (o que é o produto), 3) Benefícios (3 resultados concretos), 4) Prova social (1 caso de sucesso rápido), 5) Oferta (preço, o que inclui), 6) Urgência (por que agir agora).',
  placeholder: '🔴 Dor: "Você me disse que [dor]. Isso é exatamente o que nosso produto resolve."\n\n✅ Solução: [Nome do produto] é [descrição em 1 frase].\n\n📈 Benefícios:\n1. [Resultado concreto 1]\n2. [Resultado concreto 2]\n3. [Resultado concreto 3]\n\n⭐ Prova social: "[Nome ou perfil de cliente] conseguiu [resultado] em [tempo]."\n\n💰 Oferta: [Preço] por [período]. Inclui: [lista rápida].\n\n⏰ Urgência: [Ex: "Essa condição é válida até [data] / Restam X vagas com esse preço."]',
  importance: 'critical',
};

const CAT_OBJECTIONS_CLOSER: KnowledgeCategory = {
  key: 'objections_faq',
  label: 'FAQ de Objeções',
  description: 'As 5–10 objeções mais comuns durante o pitch e as respostas que o bot deve usar.',
  hint: 'Liste cada objeção e a resposta exata (ou roteiro de resposta) que o agente deve dar. Seja direto — em low ticket a conversa é rápida e o agente precisa de respostas prontas.',
  placeholder: '"Está caro." → "Entendo. Para te dar um parâmetro: clientes nossos costumam recuperar o valor em [X dias/semanas] com [benefício específico]. Faz sentido?"\n\n"Vou pensar." → "Sem problema! Só lembrando que [urgência/condição especial] termina [data/condição]. Posso reservar sua vaga enquanto você decide?"\n\n"Já tentei algo parecido antes." → "O que não funcionou naquela época? [Aguardar resposta] — entendo. Nosso diferencial em relação a isso é [diferencial específico]."',
  importance: 'critical',
};

const CAT_SOCIAL_PROOF_CLOSER: KnowledgeCategory = {
  key: 'social_proof',
  label: 'Depoimentos e Provas Sociais',
  description: 'Depoimentos e resultados que o bot pode citar durante o pitch para reduzir resistência.',
  hint: 'Escreva depoimentos reais (ou compostos) com resultado específico. O bot os cita naturalmente durante o pitch. Inclua: perfil do cliente, resultado obtido, tempo para resultado.',
  placeholder: '"Consegui [resultado] em [X semanas] depois de [ação]. Simplesmente funcionou." — [Perfil: ex. mãe de 2 filhos, 34 anos]\n\n"Eu estava cético no início, mas em [X dias] já vi [resultado concreto]." — [Perfil: ex. professor de educação física]\n\n"Melhor investimento que fiz esse ano." — [Perfil]',
  importance: 'critical',
};

const CAT_PRODUCT_DETAILS: KnowledgeCategory = {
  key: 'product_details',
  label: 'Detalhes do Produto',
  description: 'O que está incluído na compra: módulos, bônus, formato de entrega.',
  hint: 'Descreva tudo que o cliente recebe ao comprar. O agente usa isso para responder "o que vem junto?" durante o pitch.',
  placeholder: 'O produto inclui:\n- [Módulo/item 1]: [descrição breve]\n- [Módulo/item 2]: [descrição breve]\n- Bônus: [nome do bônus] (valor: R$ X)\n- Acesso: [Ex: vitalício / 12 meses / imediato após pagamento]\n- Suporte: [Ex: grupo no WhatsApp / e-mail / sem suporte]',
  importance: 'recommended',
};

const CAT_GUARANTEE: KnowledgeCategory = {
  key: 'guarantee_policy',
  label: 'Política de Garantia',
  description: 'Como funciona a garantia, prazo e como o cliente solicita reembolso.',
  hint: 'Descreva a garantia de forma clara. O agente usa isso para reduzir o risco percebido antes do pagamento.',
  placeholder: 'Garantia de X dias. Se não ficar satisfeito por qualquer motivo, basta enviar um e-mail para [contato] dentro do prazo e o reembolso é feito em até [X dias úteis]. Sem perguntas, sem burocracia.',
  importance: 'recommended',
};

const CAT_URGENCY_OFFER: KnowledgeCategory = {
  key: 'urgency_offer',
  label: 'Condição Atual da Oferta',
  description: 'Prazo, vagas, desconto ou bônus vigente — a urgência real que o bot comunica.',
  hint: 'Descreva a condição especial atual com precisão. IMPORTANTE: mantenha atualizado. O agente só cria urgência real se a informação for verdadeira.',
  placeholder: 'Condição vigente até [data]: preço de R$ X (de R$ Y cheio).\nVagas disponíveis nessa condição: [número ou "últimas unidades"].\nBônus exclusivo para quem comprar até [data]: [nome do bônus].',
  importance: 'recommended',
};

const CAT_UPSELL: KnowledgeCategory = {
  key: 'upsell_content',
  label: 'Conteúdo de Upsell',
  description: 'O próximo produto a oferecer imediatamente após a compra ser confirmada.',
  hint: 'Descreva o produto de upsell, o argumento para oferecê-lo e o preço especial. O bot apresenta logo após confirmar o pagamento.',
  placeholder: 'Upsell: [Nome do produto]\nArgumento: "Clientes que levaram [produto principal] normalmente levam isso junto porque [benefício complementar]."\nPreço especial pós-compra: R$ X (normal: R$ Y)\nLink: [URL do upsell]',
  importance: 'optional',
};

const CAT_PROFESSIONAL_BIO: KnowledgeCategory = {
  key: 'professional_bio',
  label: 'Bio do Profissional',
  description: 'Quem é o profissional, formação, especialidade e o que o torna único.',
  hint: 'Escreva como o agente deve se apresentar em nome do profissional. Inclua: nome, especialidade, formação relevante, anos de experiência, tipo de cliente atendido, diferencial.',
  placeholder: '[Nome] é [especialidade] com [X anos] de experiência em [área]. Formado em [formação] e especializado em [nicho específico]. Atende [perfil de cliente] que querem [resultado]. Seu diferencial é [o que o torna único — método, abordagem, resultado recorrente].',
  importance: 'critical',
};

const CAT_SOCIAL_PROOF_HYBRID: KnowledgeCategory = {
  key: 'social_proof',
  label: 'Histórias de Transformação',
  description: 'Casos de clientes com perfil similar ao lead, usados no aquecimento antes do agendamento.',
  hint: 'Escreva 2–3 histórias de transformação com: perfil do cliente (sem nome completo), situação inicial, o que mudou após trabalhar com o profissional, e o resultado em detalhes. O agente as cita naturalmente para aquecer o lead antes de propor o agendamento.',
  placeholder: 'História 1: [Perfil] — Chegou com [situação inicial]. Depois de [período] trabalhando com [Nome do profissional], [resultado concreto]. Hoje [situação atual].\n\nHistória 2: [Perfil] — [Situação inicial]. O principal avanço foi [resultado específico].',
  importance: 'critical',
};

const CAT_SESSION_PREVIEW: KnowledgeCategory = {
  key: 'session_preview',
  label: 'Preview da Sessão',
  description: 'Como funciona a 1ª sessão: duração, formato e o que o lead pode esperar.',
  hint: 'Descreva a sessão do ponto de vista do lead. O agente usa isso para reduzir ansiedade antes do agendamento e aumentar o comparecimento.',
  placeholder: 'A sessão dura [X minutos] e acontece [online via Google Meet / presencialmente em X].\nNo encontro, [Nome] vai: 1) Entender sua situação atual, 2) Identificar os principais bloqueios, 3) Mostrar o caminho mais direto para [resultado].\nNão é uma consulta de vendas — é um diagnóstico real. Você sai com [entregável: um plano / clareza sobre os próximos passos / X insight].',
  importance: 'critical',
};

const CAT_PAIN_QUESTIONS: KnowledgeCategory = {
  key: 'pain_questions',
  label: 'Roteiro de Perguntas de Dor',
  description: 'Perguntas abertas que o agente usa para aprofundar o problema e compor o briefing ao profissional.',
  hint: 'Escreva as perguntas que o agente deve fazer para entender o problema do lead. As respostas viram o briefing enviado ao profissional antes da sessão. Foque em perguntas abertas, não binárias.',
  placeholder: '"Qual é o seu principal desafio em relação a [área] no momento?"\n"Como isso impacta o seu [dia a dia / resultados / bem-estar]?"\n"O que você já tentou fazer para resolver isso?"\n"O que mudaria na sua vida se você resolvesse isso nos próximos 3 meses?"',
  importance: 'recommended',
};

const CAT_SCHEDULING_POLICY: KnowledgeCategory = {
  key: 'scheduling_policy',
  label: 'Política de Agendamento',
  description: 'Regras de cancelamento, reagendamento e no-show.',
  hint: 'Defina as regras com clareza para que o agente comunique ao lead durante e após o agendamento.',
  placeholder: 'Cancelamento: até [X horas antes], pelo WhatsApp ou pelo link da confirmação.\nReagendamento: possível uma vez sem custo. Para reagendar, responder esta mensagem.\nNo-show: se o lead não comparecer sem avisar, o agente reagenda automaticamente e envia uma mensagem de retorno.',
  importance: 'recommended',
};

const CAT_SERVICE_FAQ: KnowledgeCategory = {
  key: 'service_faq',
  label: 'FAQ do Serviço',
  description: 'Perguntas frequentes sobre preço, formato, frequência e o que está incluído.',
  hint: 'Antecipe as perguntas mais comuns que o lead faz antes de agendar. O agente responde com essas informações diretamente na conversa.',
  placeholder: '"Qual o valor da sessão?" → R$ X por [duração]. Pacotes a partir de [X sessões].\n"É online ou presencial?" → [Resposta]\n"Quantas sessões precisarei?" → Depende do objetivo — na 1ª sessão [Nome] faz o diagnóstico e indica o melhor formato.\n"Você aceita plano de saúde?" → [Resposta]',
  importance: 'recommended',
};

const CAT_PRE_SESSION_MATERIAL: KnowledgeCategory = {
  key: 'pre_session_material',
  label: 'Material Pré-Sessão',
  description: 'Formulário ou tarefa que o lead recebe antes da 1ª sessão.',
  hint: 'Descreva o que o lead precisa fazer antes de comparecer — e o texto exato que o agente envia. Pode ser um link de formulário, perguntas por texto ou uma tarefa simples.',
  placeholder: 'Texto que o agente envia 24h antes:\n"Antes da nossa sessão, [Nome do profissional] gostaria que você respondesse rapidinho 3 perguntas — leva menos de 5 minutos e deixa a sessão muito mais aproveitada: [LINK DO FORMULÁRIO]"',
  importance: 'optional',
};

export const KNOWLEDGE_CATEGORIES_BY_TEMPLATE: Record<string, KnowledgeCategory[]> = {
  sdr_padrao: [
    CAT_COMPANY_PROFILE,
    CAT_SOCIAL_PROOF_SDR,
    CAT_OBJECTIONS_SDR,
    CAT_QUALIFICATION_CRITERIA,
    CAT_PRE_MEETING_FAQ,
    CAT_PRICE_POLICY,
  ],
  consultor_especialista: [
    CAT_COMPANY_PROFILE,
    CAT_SOCIAL_PROOF_SDR,
    CAT_OBJECTIONS_SDR,
    CAT_QUALIFICATION_CRITERIA,
    CAT_PRE_MEETING_FAQ,
    CAT_PRICE_POLICY,
  ],
  closer_agressivo: [
    CAT_PITCH_SCRIPT,
    CAT_OBJECTIONS_CLOSER,
    CAT_SOCIAL_PROOF_CLOSER,
    CAT_PRODUCT_DETAILS,
    CAT_GUARANTEE,
    CAT_URGENCY_OFFER,
    CAT_UPSELL,
  ],
  hybrid_scheduler: [
    CAT_PROFESSIONAL_BIO,
    CAT_SOCIAL_PROOF_HYBRID,
    CAT_SESSION_PREVIEW,
    CAT_PAIN_QUESTIONS,
    CAT_SCHEDULING_POLICY,
    CAT_SERVICE_FAQ,
    CAT_PRE_SESSION_MATERIAL,
  ],
};

export const KNOWLEDGE_IMPORTANCE_LABELS: Record<KnowledgeCategory['importance'], string> = {
  critical: 'Crítico',
  recommended: 'Recomendado',
  optional: 'Opcional',
};

export const PAYMENT_GATEWAY_LABELS: Record<string, string> = {
  hotmart:  'Hotmart',
  kiwify:   'Kiwify',
  stripe:   'Stripe',
  generico: 'Link genérico',
};

export const OFFER_MEDIA_TYPE_LABELS: Record<string, string> = {
  image: 'Imagem',
  video: 'Vídeo',
  audio: 'Áudio',
};

export const BRIEFING_CHANNEL_LABELS: Record<string, string> = {
  whatsapp: 'WhatsApp',
  internal: 'Interno (CRM)',
};
