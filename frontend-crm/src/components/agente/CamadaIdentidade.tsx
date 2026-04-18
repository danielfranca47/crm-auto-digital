import { useState } from 'react';
import { FieldHelp } from './FieldHelp';
import { SuggestInput, SuggestTextarea } from './SuggestField';
import type { AgentConfig } from '@/types/agente';
import {
  AGENT_MODE_LABELS,
  IDENTITY_MODE_LABELS,
  HANDOFF_LABELS,
  AGENT_PRESETS,
  getActivePreset,
} from '@/types/agente';
import { buildVariableList } from '@/types/variables';
import { VariableTextarea } from './VariableTextarea';
import { CustomVariablesManager } from './CustomVariablesManager';

interface CamadaIdentidadeProps {
  config: AgentConfig;
  onUpdate: (partial: Partial<AgentConfig>) => void;
  /** Se true, renderiza os cards em modo resumo (para o painel "Resumo") */
  resumo?: boolean;
}

// ─── Drawer: Nome do agente ───────────────────────────────────
function DrawerNome({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  return (
    <DrawerBase title="Nome do agente" sub="Como o agente se apresenta ao lead" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Nome <FieldHelp text="Este nome aparece em todas as mensagens. Escolha um nome que combine com a personalidade e o posicionamento da marca." /></label>
        <div className="o-field-hint">Este nome aparecerá em todas as mensagens enviadas.</div>
        <SuggestInput className="o-input" value={local} maxLength={40} onChange={e => setLocal(e.target.value)} placeholder="Ex: Sofia, Max, Atendente…" />
        <div className="o-char-count">{local.length}/40</div>
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Empresa ──────────────────────────────────────────
function DrawerEmpresa({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  return (
    <DrawerBase title="Nome da empresa" sub="Usado no perfil do agente e nas mensagens" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Empresa</label>
        <input className="o-input" value={local} maxLength={60} onChange={e => setLocal(e.target.value)} />
        <div className="o-char-count">{local.length}/60</div>
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Nicho ────────────────────────────────────────────
function DrawerNicho({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  return (
    <DrawerBase title="Nicho de mercado" sub="Segmento em que o agente atua" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Nicho</label>
        <SuggestInput className="o-input" value={local} maxLength={80} onChange={e => setLocal(e.target.value)} placeholder="Ex: Estética corporal, Imóveis, Coaching…" />
        <div className="o-char-count">{local.length}/80</div>
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Fuso horário ─────────────────────────────────────
function DrawerTimezone({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const opts = [
    { v: 'America/Sao_Paulo', label: 'América/São Paulo (BRT, UTC−3)' },
    { v: 'America/Manaus',    label: 'América/Manaus (AMT, UTC−4)' },
    { v: 'America/Fortaleza', label: 'América/Fortaleza (BRT, UTC−3)' },
    { v: 'America/Belem',     label: 'América/Belém (BRT, UTC−3)' },
    { v: 'America/Noronha',   label: 'América/Noronha (FNT, UTC−2)' },
    { v: 'Europe/Lisbon',     label: 'Europa/Lisboa (WET/WEST)' },
    { v: 'Europe/London',     label: 'Europa/Londres (GMT/BST)' },
    { v: 'UTC',               label: 'UTC (Tempo Universal)' },
  ];
  return (
    <DrawerBase title="Fuso horário" sub="Usado para agendar follow-ups e lembretes no horário correto" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Fuso horário</label>
        <select className="o-select" value={local} onChange={e => setLocal(e.target.value)}>
          {opts.map(o => <option key={o.v} value={o.v}>{o.label}</option>)}
        </select>
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Goals ────────────────────────────────────────────
function DrawerGoals({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  return (
    <DrawerBase title="Prioridades do atendimento" sub="Objetivos que o agente deve ter em toda conversa" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Prioridades (uma por linha) <FieldHelp text="Liste as prioridades em ordem de importância. O agente usa essas instruções para decidir como conduzir cada conversa." /></label>
        <div className="o-field-hint">Ex: "1. Qualificar em até 5 mensagens" · "2. Sempre perguntar sobre urgência"</div>
        <SuggestTextarea className="o-textarea" style={{ minHeight: 140 }} value={local} maxLength={600} onChange={e => setLocal(e.target.value)} placeholder="1. Identificar a dor principal&#10;2. Apresentar a solução de forma consultiva&#10;3. Conduzir para o agendamento" />
        <div className="o-char-count">{local.length}/600</div>
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Handoff ─────────────────────────────────────────
function DrawerHandoff({ policy, text, customVars, onSave, onClose }: {
  policy: string; text: string; customVars: Record<string, string>;
  onSave: (policy: string, text: string) => void; onClose: () => void;
}) {
  const [localPolicy, setLocalPolicy] = useState(policy);
  const [localText, setLocalText] = useState(text);
  const variables = buildVariableList(customVars);
  return (
    <DrawerBase title="Política de handoff" sub="O que acontece quando um humano precisa assumir a conversa" onClose={onClose} onSave={() => onSave(localPolicy, localText)}>
      <div className="o-field">
        <label className="o-field-label">Comportamento ao fazer handoff <FieldHelp text="Define o que o bot faz quando um humano assume: desabilitar para não atrapalhar, manter ativo notificando o lead, ou não tomar ação alguma." /></label>
        <select className="o-select" value={localPolicy} onChange={e => setLocalPolicy(e.target.value)}>
          <option value="keep_active_notify">Manter bot ativo e notificar operador</option>
          <option value="disable_bot">Desabilitar bot imediatamente</option>
          <option value="ignore">Ignorar — sem ação automática</option>
        </select>
      </div>
      <div className="o-field">
        <label className="o-field-label">Mensagem personalizada de handoff <FieldHelp text="Enviada ao lead no momento da transferência para humano. Use variáveis como {{agente.nome}} para personalizar." /></label>
        <div className="o-field-hint">Enviada ao lead quando o bot encaminha para humano. Deixe em branco para usar o padrão do sistema.</div>
        <VariableTextarea
          value={localText}
          onChange={setLocalText}
          variables={variables}
          maxLength={400}
          placeholder="Ex: Oi! Vou passar sua conversa para um especialista que vai te ajudar melhor. Aguarde um momento 🙂"
        />
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Opener inbound ───────────────────────────────────
function DrawerOpenerInbound({ value, customVars, onSave, onClose }: { value: string; customVars: Record<string, string>; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const variables = buildVariableList(customVars);
  return (
    <DrawerBase title="Mensagem de abertura · Inbound" sub="Primeira mensagem quando o lead entra em contato" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Texto de abertura</label>
        <div className="o-field-hint">Digite <kbd style={{ fontFamily: 'monospace', padding: '0 3px', borderRadius: 2, background: 'var(--o-b1)', fontSize: 10 }}>/</kbd> para inserir variáveis como <code style={{ fontSize: 11 }}>{'{{saudacao}}'}</code>, <code style={{ fontSize: 11 }}>{'{{lead.nome}}'}</code>, <code style={{ fontSize: 11 }}>{'{{agente.nome}}'}</code>.</div>
        <VariableTextarea
          value={local}
          onChange={setLocal}
          variables={variables}
          maxLength={500}
          minHeight={120}
          placeholder={`{{saudacao}}! Sou {{agente.nome}} da {{negocio.nome}} 😊 Vi que você entrou em contato. Como posso te ajudar hoje?`}
        />
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Opener outbound ──────────────────────────────────
function DrawerOpenerOutbound({ value, customVars, onSave, onClose }: { value: string; customVars: Record<string, string>; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const variables = buildVariableList(customVars);
  return (
    <DrawerBase title="Mensagem de abertura · Outbound" sub="Primeira mensagem quando o bot inicia o contato" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Texto de abertura</label>
        <div className="o-field-hint">Digite <kbd style={{ fontFamily: 'monospace', padding: '0 3px', borderRadius: 2, background: 'var(--o-b1)', fontSize: 10 }}>/</kbd> para inserir variáveis como <code style={{ fontSize: 11 }}>{'{{lead.nome}}'}</code>, <code style={{ fontSize: 11 }}>{'{{saudacao}}'}</code>, <code style={{ fontSize: 11 }}>{'{{negocio.nome}}'}</code>.</div>
        <VariableTextarea
          value={local}
          onChange={setLocal}
          variables={variables}
          maxLength={500}
          minHeight={120}
          placeholder={`{{saudacao}}, {{lead.nome}}! Sou {{agente.nome}} da {{negocio.nome}}. Tudo bem? Entrei em contato pois tenho algo que pode te interessar…`}
        />
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Social proof ─────────────────────────────────────
function DrawerSocialProof({ value, customVars, onSave, onClose }: { value: string; customVars: Record<string, string>; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const variables = buildVariableList(customVars);
  return (
    <DrawerBase title="Social proof para aquecimento" sub="Prova social usada para gerar confiança no início da conversa" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Texto de social proof</label>
        <div className="o-field-hint">Ex: depoimentos, números de clientes, resultados alcançados.</div>
        <VariableTextarea
          value={local}
          onChange={setLocal}
          variables={variables}
          maxLength={500}
          minHeight={120}
          placeholder="Ex: Já ajudamos mais de 500 clientes a atingir resultados. Nossa taxa de satisfação é de 98%."
        />
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Session preview ──────────────────────────────────
function DrawerSessionPreview({ value, customVars, onSave, onClose }: { value: string; customVars: Record<string, string>; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const variables = buildVariableList(customVars);
  return (
    <DrawerBase title="Preview da sessão/serviço" sub="O que o lead pode esperar ao começar com você" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Descrição do que acontece ao contratar</label>
        <div className="o-field-hint">Use na fase de aquecimento para preparar o lead mentalmente para a compra.</div>
        <VariableTextarea
          value={local}
          onChange={setLocal}
          variables={variables}
          maxLength={500}
          minHeight={120}
          placeholder="Ex: Na nossa primeira sessão, vamos fazer um diagnóstico completo. É rápido e você já sai com um plano de ação."
        />
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Variáveis personalizadas ────────────────────────
function DrawerVariaveis({ variables, onSave, onClose }: {
  variables: Record<string, string>;
  onSave: (vars: Record<string, string>) => void;
  onClose: () => void;
}) {
  const [local, setLocal] = useState<Record<string, string>>(variables);
  return (
    <DrawerBase title="Variáveis personalizadas" sub="Crie variáveis reutilizáveis nos seus templates de mensagem" onClose={onClose} onSave={() => onSave(local)}>
      <CustomVariablesManager variables={local} onChange={setLocal} />
    </DrawerBase>
  );
}

// ─── Drawer: Modo de resposta ─────────────────────────────────
function DrawerResponseStyle({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value || 'active');
  const options = [
    {
      v: 'active',
      label: 'Ativo — faz perguntas',
      desc: 'O agente qualifica o lead fazendo perguntas estruturadas antes de responder sobre serviços ou preços. Ideal para funis consultivos onde é importante entender o perfil do cliente.',
    },
    {
      v: 'passive',
      label: 'Passivo — responde primeiro',
      desc: 'O agente responde primeiro às perguntas directas do cliente (serviços, preços, localização) e depois, de forma natural, recolhe as informações de qualificação. Ideal para negócios onde o cliente já chegou com dúvidas concretas.',
    },
  ];
  return (
    <DrawerBase title="Modo de resposta" sub="Como o agente reage às perguntas do cliente" onClose={onClose} onSave={() => onSave(local)}>
      {options.map(o => (
        <div
          key={o.v}
          onClick={() => setLocal(o.v)}
          style={{
            padding: '12px 14px',
            borderRadius: 6,
            border: `1px solid ${local === o.v ? 'var(--o-purple)' : 'var(--o-b1)'}`,
            background: local === o.v ? 'rgba(139,92,246,0.06)' : 'transparent',
            cursor: 'pointer',
            marginBottom: 10,
          }}
        >
          <div style={{ fontWeight: 500, fontSize: 13, color: local === o.v ? 'var(--o-purple)' : 'var(--o-text)', marginBottom: 4 }}>
            {o.label}
          </div>
          <div style={{ fontSize: 12, color: 'var(--o-sub)', lineHeight: 1.4 }}>{o.desc}</div>
        </div>
      ))}
    </DrawerBase>
  );
}

// ─── Drawer: Tom ─────────────────────────────────────────────
function DrawerTom({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  return (
    <DrawerBase title="Tom de comunicação" sub="Estilo de linguagem em todas as mensagens" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Tom</label>
        <SuggestInput className="o-input" value={local} onChange={e => setLocal(e.target.value)} placeholder="Ex: equilibrado, formal, descontraído…" />
        <div className="o-field-hint">Texto livre — descreva o tom que o agente deve usar.</div>
      </div>
    </DrawerBase>
  );
}

// ─── Modal: Modo de identidade ───────────────────────────────
function ModalIdentidade({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const options = [
    { v: 'virtual_assistant', label: '🤖 Assistente Virtual', desc: 'Se apresenta claramente como IA.' },
    { v: 'human_agent',       label: '🤝 Humano do Time',     desc: 'Age como colaborador da empresa sem revelar que é IA.' },
    { v: 'user_clone',        label: '🪄 Clone do Usuário',   desc: 'Replica o perfil e estilo de comunicação do próprio dono.' },
  ];
  return (
    <ModalBase title="Modo de identidade" sub="Como o agente se apresentará para o lead" onClose={onClose} onSave={() => onSave(local)}>
      {options.map(o => (
        <OptCard key={o.v} selected={local === o.v} onClick={() => setLocal(o.v)} label={o.label} desc={o.desc} />
      ))}
    </ModalBase>
  );
}

// ─── Modal: Perfil gerado (custom_instructions) ───────────────
function ModalPerfil({ value, name, brand, agentMode, tone, onSave, onClose }: {
  value: string; name: string; brand: string; agentMode: string; tone: string;
  onSave: (v: string) => void; onClose: () => void;
}) {
  const [local, setLocal] = useState(value);

  function regenerate() {
    setLocal(
      `Você é ${name || 'o agente'}, colaborador(a) da ${brand || 'empresa'}, atuando como ${AGENT_MODE_LABELS[agentMode] ?? agentMode}.\n\nSeu tom de comunicação é ${tone || 'natural e equilibrado'}. Você usa uma abordagem consultiva para entender as necessidades do lead e apresentar a solução de forma personalizada.\n\nSeu objetivo é qualificar e conduzir leads com naturalidade, gerando confiança e valor em cada interação.`
    );
  }

  return (
    <ModalBase title="Perfil do agente" sub="Instruções personalizadas injetadas no system prompt" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Instruções personalizadas</label>
        <div className="o-field-hint">
          Este texto é adicionado ao system prompt do agente. Edite livremente ou use o botão para regenerar a partir das configurações.
        </div>
        <textarea
          className="o-textarea"
          style={{ minHeight: 220 }}
          maxLength={1500}
          value={local}
          onChange={e => setLocal(e.target.value)}
        />
        <div className="o-char-count">{local.length}/1500</div>
      </div>
      <button className="o-btn" onClick={regenerate} style={{ marginTop: 4 }}>↺ Regenerar a partir das configurações</button>
    </ModalBase>
  );
}

// ─────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────

type DrawerKey = 'nome' | 'empresa' | 'nicho' | 'timezone' | 'tom' | 'goals' | 'handoff' | 'inbound_opener' | 'outbound_opener' | 'social_proof' | 'session_preview' | 'response_style' | 'variaveis' | null;
type ModalKey  = 'identidade' | 'perfil' | null;

export function CamadaIdentidade({ config, onUpdate, resumo }: CamadaIdentidadeProps) {
  const [drawer, setDrawer] = useState<DrawerKey>(null);
  const [modal, setModal]   = useState<ModalKey>(null);

  const profilePreview = config.custom_instructions
    ? config.custom_instructions.slice(0, 60) + '…'
    : 'Ainda não configurado';

  const showHandoff = config.identity_mode !== 'virtual_assistant';
  const activePreset = getActivePreset(config.template_key, config.agent_mode);

  return (
    <>
      {/* Seletor de tipo de agente */}
      <div style={{ marginBottom: 24 }}>
        <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)', marginBottom: 12 }}>
          Tipo de agente
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {AGENT_PRESETS.map(preset => {
            const selected = activePreset?.key === preset.key;
            return (
              <button
                key={preset.key}
                onClick={() => onUpdate({ template_key: preset.template_key, agent_mode: preset.agent_mode })}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  background: selected ? 'var(--o-active-bg, rgba(var(--o-active-rgb,99,102,241),0.08))' : 'var(--o-card)',
                  border: `1.5px solid ${selected ? 'var(--o-active)' : 'var(--o-b1)'}`,
                  borderRadius: 12,
                  padding: '14px 16px',
                  cursor: 'pointer',
                  transition: 'border-color 0.15s, background 0.15s',
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  gap: 12,
                }}
              >
                <div>
                  <div style={{ fontSize: 10, color: 'var(--o-sub)', marginBottom: 2, letterSpacing: 0.5 }}>{preset.chip}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--o-text)', marginBottom: 1 }}>{preset.title}</div>
                  <div style={{ fontSize: 11, color: 'var(--o-sub)', marginBottom: 6, fontWeight: 300 }}>{preset.subtitle}</div>
                  <div style={{ fontSize: 12, color: 'var(--o-text)', lineHeight: 1.5, marginBottom: 8 }}>{preset.desc}</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {preset.useCases.map(uc => (
                      <span key={uc} style={{ fontSize: 10, background: 'var(--o-muted)', borderRadius: 6, padding: '2px 8px', color: 'var(--o-sub)' }}>{uc}</span>
                    ))}
                  </div>
                </div>
                <div style={{
                  width: 18, height: 18, borderRadius: '50%', flexShrink: 0, marginTop: 2,
                  border: `2px solid ${selected ? 'var(--o-active)' : 'var(--o-b1)'}`,
                  background: selected ? 'var(--o-active)' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {selected && <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff' }} />}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Seção: Identidade */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard label="Nome do agente"    value={config.name || '—'}       sub="Como se apresenta ao lead"       onClick={() => setDrawer('nome')}    help="Nome com que o agente se identifica nas conversas. Aparece nas mensagens de abertura e no perfil gerado automaticamente." />
        <EditCard label="Empresa"           value={config.brand_name || '—'} sub="Marca ou empresa representada"   onClick={() => setDrawer('empresa')} help="Nome da empresa representada. Usado em mensagens de apresentação e na base de conhecimento." />
        <EditCard label="Nicho de mercado"  value={config.niche || '—'}      sub="Segmento de atuação"             onClick={() => setDrawer('nicho')}   help="Segmento de mercado (ex: clínica odontológica, consultoria de RH). Orienta o tom e o vocabulário do agente." />
        <EditCard label="Fuso horário"      value={config.timezone || '—'}   sub="Para follow-ups e lembretes"     onClick={() => setDrawer('timezone')} help="Fuso horário do negócio. Usado para agendar follow-ups e lembretes no horário correto para o lead." />
        <EditCard
          label="Modo de identidade"
          value={IDENTITY_MODE_LABELS[config.identity_mode] || config.identity_mode || '—'}
          sub="Como se apresenta ao lead"
          onClick={() => setModal('identidade')}
          help="Como o agente se apresenta: Assistente Virtual (transparente sobre ser IA), Agente Humano (persona humana) ou Clone do Usuário (imita você mesmo). Afeta confiança e tom da conversa."
        />
        <EditCard
          label="Perfil gerado"
          value={profilePreview}
          sub="Instruções personalizadas do system prompt"
          onClick={() => setModal('perfil')}
          italic
          help="Perfil detalhado injetado no system prompt. Define personalidade, contexto e regras internas do agente. Edite livremente ou regenere a partir das configurações."
        />
      </div>

      {/* Seção: Comunicação */}
      {!resumo && (
        <>
          <div className="o-section-hdr">
            <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
              Comunicação e prioridades
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
            <EditCard label="Tom de comunicação" value={config.tone_of_voice || '—'} sub="Estilo de linguagem" onClick={() => setDrawer('tom')} help="Descreva o tom ideal: formal, descontraído, técnico, empático etc. O agente adapta o estilo de escrita de acordo." />
            <EditCard
              label="Prioridades do atendimento"
              value={config.goals ? config.goals.slice(0, 50) + '…' : 'Não configurado'}
              sub="Objetivos de cada conversa"
              onClick={() => setDrawer('goals')}
              italic
              help="Prioridades de atendimento em ordem. Ex: 1. Qualificar em até 5 mensagens · 2. Sempre perguntar urgência. Orienta o foco do agente em cada conversa."
            />
          </div>

          {/* Seção: Modo de resposta (só Agente 03 · Híbrido) */}
          {config.template_key === 'hybrid_scheduler' && (
            <>
              <div className="o-section-hdr">
                <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
                  Modo de resposta · Híbrido Agendador
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
                <EditCard
                  label="Modo de resposta"
                  value={config.response_style === 'passive' ? 'Passivo — responde primeiro' : 'Ativo — faz perguntas'}
                  sub={config.response_style === 'passive' ? 'Responde dúvidas antes de qualificar' : 'Qualifica antes de responder'}
                  onClick={() => setDrawer('response_style')}
                  help="Ativo: o agente faz perguntas diretas para qualificar. Passivo: responde primeiro às dúvidas do lead e captura dados de forma natural. Recomendado Passivo para alto ticket."
                />
              </div>
            </>
          )}

          {/* Seção: Contexto de abertura */}
          <div className="o-section-hdr">
            <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
              Contexto de abertura
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
            <EditCard
              label="Abertura · Inbound"
              value={config.origin_inbound_opener ? config.origin_inbound_opener.slice(0, 50) + '…' : 'Não configurado'}
              sub="Lead entra em contato primeiro"
              onClick={() => setDrawer('inbound_opener')}
              italic
              help="Primeira mensagem enviada quando o lead chega por conta própria (inbound). Define o tom de boas-vindas. Use variáveis como {{lead.nome}} para personalizar."
            />
            <EditCard
              label="Abertura · Outbound"
              value={config.origin_outbound_opener ? config.origin_outbound_opener.slice(0, 50) + '…' : 'Não configurado'}
              sub="Bot inicia o contato"
              onClick={() => setDrawer('outbound_opener')}
              italic
              help="Primeira mensagem enviada em prospecção ativa (outbound). Deve ser direta e gerar curiosidade sem parecer spam. Use {{lead.nome}} para personalizar."
            />
            <EditCard
              label="Social proof"
              value={config.warming_social_proof ? config.warming_social_proof.slice(0, 50) + '…' : 'Não configurado'}
              sub="Prova social para aquecimento"
              onClick={() => setDrawer('social_proof')}
              italic
              help="Prova social enviada durante o aquecimento. Ex: depoimentos, número de clientes, resultados alcançados. Aumenta credibilidade antes da oferta."
            />
            <EditCard
              label="Preview da sessão"
              value={config.warming_session_preview ? config.warming_session_preview.slice(0, 50) + '…' : 'Não configurado'}
              sub="O que o lead pode esperar"
              onClick={() => setDrawer('session_preview')}
              italic
              help="Preview do que acontecerá na sessão ou reunião. Reduz ansiedade e aumenta o comparecimento ao preparar o lead mentalmente para a compra."
            />
          </div>

          {/* Seção: Variáveis personalizadas */}
          <div className="o-section-hdr">
            <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
              Variáveis dinâmicas
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
            <EditCard
              label="Variáveis personalizadas"
              value={
                Object.keys(config.custom_variables || {}).length > 0
                  ? `${Object.keys(config.custom_variables).length} variável(is) configurada(s)`
                  : 'Nenhuma configurada'
              }
              sub="Use / nos campos de mensagem para inserir"
              onClick={() => setDrawer('variaveis')}
              help="Variáveis reutilizáveis injetáveis em qualquer mensagem via {{variavel}}. Ex: link do calendário, nome do responsável, endereço do escritório."
            />
          </div>

          {/* Seção: Handoff (condicional) */}
          {showHandoff && (
            <>
              <div className="o-section-hdr">
                <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
                  Atendimento humano (handoff)
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
                <EditCard
                  label="Política de handoff"
                  value={HANDOFF_LABELS[config.handoff_policy] || config.handoff_policy || '—'}
                  sub="Ação ao transferir para humano"
                  onClick={() => setDrawer('handoff')}
                  help="O que o agente faz quando um humano assume a conversa: desativar o bot, continuar ativo avisando o lead, ou não fazer nada."
                />
                <EditCard
                  label="Mensagem de handoff"
                  value={config.handoff_custom_text ? config.handoff_custom_text.slice(0, 50) + '…' : 'Usar mensagem padrão'}
                  sub="Texto enviado ao transferir"
                  onClick={() => setDrawer('handoff')}
                  italic
                  help="Mensagem enviada ao lead quando o bot passa para atendimento humano. Deixe em branco para usar o texto padrão do sistema."
                />
              </div>
            </>
          )}
        </>
      )}

      {/* Drawers */}
      {drawer === 'nome' && (
        <DrawerNome value={config.name} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ name: v }); setDrawer(null); }} />
      )}
      {drawer === 'empresa' && (
        <DrawerEmpresa value={config.brand_name} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ brand_name: v }); setDrawer(null); }} />
      )}
      {drawer === 'nicho' && (
        <DrawerNicho value={config.niche} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ niche: v }); setDrawer(null); }} />
      )}
      {drawer === 'timezone' && (
        <DrawerTimezone value={config.timezone} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ timezone: v }); setDrawer(null); }} />
      )}
      {drawer === 'tom' && (
        <DrawerTom value={config.tone_of_voice} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ tone_of_voice: v }); setDrawer(null); }} />
      )}
      {drawer === 'goals' && (
        <DrawerGoals value={config.goals} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ goals: v }); setDrawer(null); }} />
      )}
      {drawer === 'handoff' && (
        <DrawerHandoff
          policy={config.handoff_policy}
          text={config.handoff_custom_text}
          customVars={config.custom_variables || {}}
          onClose={() => setDrawer(null)}
          onSave={(policy, text) => { onUpdate({ handoff_policy: policy as AgentConfig['handoff_policy'], handoff_custom_text: text }); setDrawer(null); }}
        />
      )}
      {drawer === 'inbound_opener' && (
        <DrawerOpenerInbound value={config.origin_inbound_opener} customVars={config.custom_variables || {}} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ origin_inbound_opener: v }); setDrawer(null); }} />
      )}
      {drawer === 'outbound_opener' && (
        <DrawerOpenerOutbound value={config.origin_outbound_opener} customVars={config.custom_variables || {}} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ origin_outbound_opener: v }); setDrawer(null); }} />
      )}
      {drawer === 'social_proof' && (
        <DrawerSocialProof value={config.warming_social_proof} customVars={config.custom_variables || {}} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ warming_social_proof: v }); setDrawer(null); }} />
      )}
      {drawer === 'session_preview' && (
        <DrawerSessionPreview value={config.warming_session_preview} customVars={config.custom_variables || {}} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ warming_session_preview: v }); setDrawer(null); }} />
      )}
      {drawer === 'variaveis' && (
        <DrawerVariaveis variables={config.custom_variables || {}} onClose={() => setDrawer(null)} onSave={vars => { onUpdate({ custom_variables: vars }); setDrawer(null); }} />
      )}
      {drawer === 'response_style' && (
        <DrawerResponseStyle value={config.response_style} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ response_style: v as AgentConfig['response_style'] }); setDrawer(null); }} />
      )}

      {/* Modais */}
      {modal === 'identidade' && (
        <ModalIdentidade value={config.identity_mode} onClose={() => setModal(null)} onSave={v => { onUpdate({ identity_mode: v as AgentConfig['identity_mode'] }); setModal(null); }} />
      )}
      {modal === 'perfil' && (
        <ModalPerfil
          value={config.custom_instructions}
          name={config.name}
          brand={config.brand_name}
          agentMode={config.agent_mode}
          tone={config.tone_of_voice}
          onClose={() => setModal(null)}
          onSave={v => { onUpdate({ custom_instructions: v }); setModal(null); }}
        />
      )}
    </>
  );
}

// ─── Componentes internos reutilizáveis ───────────────────────

function EditCard({ label, value, sub, onClick, italic, help }: {
  label: string; value: string; sub: string; onClick: () => void; italic?: boolean; help?: string;
}) {
  return (
    <div className="o-edit-card" onClick={onClick}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6, display: 'flex', alignItems: 'center' }}>
        {label}{help && <FieldHelp text={help} />}
      </div>
      <div style={{ fontSize: 13, color: 'var(--o-text)', marginBottom: 4, fontStyle: italic ? 'italic' : 'normal' }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300 }}>{sub}</div>
      <span className="o-edit-arrow">›</span>
    </div>
  );
}

function DrawerBase({ title, sub, onClose, onSave, children }: {
  title: string; sub: string; onClose: () => void; onSave: () => void; children: React.ReactNode;
}) {
  return (
    <>
      <div className="o-drawer-overlay open" onClick={onClose} />
      <div className="o-drawer open">
        <div className="o-drawer-header">
          <div>
            <div className="font-display" style={{ fontSize: 20, fontWeight: 400, color: 'var(--o-text)' }}>{title}</div>
            <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginTop: 4, fontWeight: 300 }}>{sub}</div>
          </div>
          <button className="o-close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="o-drawer-body">{children}</div>
        <div className="o-drawer-footer">
          <button className="o-btn o-btn-primary" onClick={onSave}>Salvar</button>
          <button className="o-btn" onClick={onClose}>Cancelar</button>
        </div>
      </div>
    </>
  );
}

function ModalBase({ title, sub, onClose, onSave, children }: {
  title: string; sub: string; onClose: () => void; onSave: () => void; children: React.ReactNode;
}) {
  return (
    <div className="o-modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="o-modal">
        <div className="o-modal-header">
          <div>
            <div className="font-display" style={{ fontSize: 22, fontWeight: 400, color: 'var(--o-text)' }}>{title}</div>
            <div style={{ fontSize: 12, color: 'var(--o-sub)', fontWeight: 300, marginTop: 3 }}>{sub}</div>
          </div>
          <button className="o-close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="o-modal-body">{children}</div>
        <div className="o-modal-footer">
          <button className="o-btn o-btn-primary" onClick={onSave}>Salvar alterações</button>
          <button className="o-btn" onClick={onClose}>Cancelar</button>
        </div>
      </div>
    </div>
  );
}

function OptCard({ selected, onClick, label, desc, sub }: {
  selected: boolean; onClick: () => void; label: string; desc: string; sub?: string;
}) {
  return (
    <div className={`o-opt-card ${selected ? 'selected' : ''}`} onClick={onClick}>
      <div style={{
        width: 16, height: 16, borderRadius: '50%', flexShrink: 0, marginTop: 2,
        border: `2px solid ${selected ? 'var(--o-active)' : 'var(--o-b1)'}`,
        background: selected ? 'var(--o-active)' : 'transparent',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {selected && <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#fff' }} />}
      </div>
      <div>
        <div style={{ fontSize: 13.5, fontWeight: 500, marginBottom: 3, color: 'var(--o-text)' }}>{label}</div>
        <div style={{ fontSize: 12, color: 'var(--o-sub)', fontWeight: 300, lineHeight: 1.55 }}>{desc}</div>
        {sub && <div style={{ fontSize: 11, color: 'var(--o-dim)', marginTop: 4, fontStyle: 'italic' }}>{sub}</div>}
      </div>
    </div>
  );
}
