/**
 * DebugAiProfile — Página de debug para testar a UI da Fase 4
 *
 * Simula a experiência completa do AiProfile / CamadaQualificacao
 * com as implementações da Fase 4 do plano-implementacao.md:
 *  - Toggle response_style (ativo/passivo) no topo
 *  - SDR: F1/F2/F3 com modo obrigatório/opcional/desligado por pergunta
 *  - Outros agentes: lista plana de QualificationField
 *  - Drawer de edição de campo (question + passive_hint)
 *  - Campos personalizados
 *  - Sugestão ao trocar de modo
 *  - Painel JSON do contrato derivado
 *
 * Sem chamadas de API — tudo em estado local React.
 */

import { useState, useCallback } from 'react';
import { OrionShell } from '@/components/agente/OrionShell';

// ─── Tipos ────────────────────────────────────────────────────

type AgentMode = 'sdr_scheduler' | 'closer' | 'direto' | 'agenda' | 'consultivo';
type ResponseStyle = 'active' | 'passive';
type FieldMode = 'required' | 'optional' | 'off';
type FilterGroup = 'f1' | 'f2' | 'f3';

interface QualificationField {
  key: string;
  label: string;
  question: string;
  passive_hint: string;
  mode: FieldMode;
  group?: FilterGroup; // apenas para SDR
  is_custom?: boolean;
}

// ─── Constantes ───────────────────────────────────────────────

const AGENT_MODE_LABELS: Record<AgentMode, string> = {
  sdr_scheduler: 'SDR · Agendador',
  closer: 'Closer',
  direto: 'Direto',
  agenda: 'Agendador',
  consultivo: 'Consultivo',
};

const AGENT_MODE_DESC: Record<AgentMode, string> = {
  sdr_scheduler: 'Pipeline sequencial F1→F2→F3. Qualificação em etapas.',
  closer: 'Fechamento rápido. Poucas perguntas, foco em converter.',
  direto: 'Sem rodeios. Filtra e fecha.',
  agenda: 'Foco em agendar. Disponibilidade é o campo central.',
  consultivo: 'Atendimento profundo. Entende contexto antes de propor.',
};

const PREDEFINED_FIELDS: Omit<QualificationField, 'mode' | 'group'>[] = [
  {
    key: 'service_interest',
    label: 'Serviço de interesse',
    question: 'O que você busca exatamente?',
    passive_hint: 'Inferir pelo serviço que o lead mencionar',
  },
  {
    key: 'availability_window',
    label: 'Disponibilidade',
    question: 'Qual o melhor horário para você?',
    passive_hint: 'Se lead mencionar horário, data ou "semana que vem"',
  },
  {
    key: 'price_acceptance',
    label: 'Aceitação de preço',
    question: 'O valor de R$ X funciona para você?',
    passive_hint: 'Se lead não reclamar do preço após mencionado',
  },
  {
    key: 'location_preference',
    label: 'Preferência de local',
    question: 'Você prefere presencial, online ou domicílio?',
    passive_hint: 'Se lead mencionar cidade, endereço ou "online"',
  },
  {
    key: 'urgency',
    label: 'Urgência',
    question: 'Isso é urgente para você ou pode esperar um pouco?',
    passive_hint: 'Se lead usar "urgente", "preciso logo", "esta semana"',
  },
  {
    key: 'decision_role',
    label: 'Decisor',
    question: 'A decisão de contratar é só sua ou envolve mais alguém?',
    passive_hint: 'Se lead falar "preciso consultar alguém" → não é decisor',
  },
  {
    key: 'budget_or_price_acceptance',
    label: 'Orçamento',
    question: 'Qual faixa de investimento você tem em mente?',
    passive_hint: 'Se lead mencionar faixa ou comparar preços',
  },
  {
    key: 'constraints',
    label: 'Restrições',
    question: 'Tem alguma restrição de horário, local ou outra limitação?',
    passive_hint: 'Se lead mencionar limitações específicas',
  },
];

// Sugestões por modo (Fase 4.6)
const SUGGESTIONS: Record<AgentMode, QualificationField[]> = {
  sdr_scheduler: [
    { key: 'service_interest',    label: 'Serviço de interesse', question: 'O que você busca exatamente?',            passive_hint: 'Inferir pelo serviço mencionado', mode: 'required', group: 'f1' },
    { key: 'location_preference', label: 'Preferência de local', question: 'Você prefere presencial ou online?',      passive_hint: 'Se lead mencionar cidade ou "online"', mode: 'optional', group: 'f1' },
    { key: 'urgency',             label: 'Urgência',             question: 'Isso é urgente para você?',               passive_hint: 'Se lead usar "urgente" ou "esta semana"', mode: 'required', group: 'f2' },
    { key: 'decision_role',       label: 'Decisor',              question: 'A decisão é só sua?',                     passive_hint: 'Se mencionar "consultar alguém"', mode: 'optional', group: 'f2' },
    { key: 'availability_window', label: 'Disponibilidade',      question: 'Qual o melhor horário para você?',        passive_hint: 'Se lead mencionar horário ou data', mode: 'required', group: 'f3' },
    { key: 'price_acceptance',    label: 'Aceitação de preço',   question: 'O valor de R$ X funciona para você?',     passive_hint: 'Se lead não reclamar do preço', mode: 'optional', group: 'f3' },
  ],
  agenda: [
    { key: 'availability_window', label: 'Disponibilidade',      question: 'Qual o melhor horário para você?',        passive_hint: 'Se lead mencionar horário ou data', mode: 'required' },
    { key: 'service_interest',    label: 'Serviço de interesse', question: 'O que você busca exatamente?',            passive_hint: 'Inferir pelo serviço mencionado', mode: 'optional' },
  ],
  closer: [
    { key: 'service_interest',    label: 'Serviço de interesse', question: 'O que você busca?',                      passive_hint: 'Inferir pelo contexto', mode: 'required' },
    { key: 'price_acceptance',    label: 'Aceitação de preço',   question: 'O valor funciona para você?',             passive_hint: 'Se não reclamar do preço', mode: 'required' },
  ],
  direto: [
    { key: 'service_interest',    label: 'Serviço de interesse', question: 'O que você busca?',                      passive_hint: 'Inferir pelo contexto', mode: 'required' },
    { key: 'price_acceptance',    label: 'Aceitação de preço',   question: 'O valor funciona para você?',             passive_hint: 'Se não reclamar do preço', mode: 'required' },
    { key: 'urgency',             label: 'Urgência',             question: 'Quando você precisa resolver isso?',      passive_hint: 'Se mencionar data ou prazo', mode: 'optional' },
  ],
  consultivo: [
    { key: 'service_interest',    label: 'Serviço de interesse', question: 'O que você busca exatamente?',            passive_hint: 'Inferir pelo serviço mencionado', mode: 'required' },
    { key: 'urgency',             label: 'Urgência',             question: 'Isso é urgente ou pode esperar?',         passive_hint: 'Se lead usar "urgente" ou prazo', mode: 'required' },
    { key: 'decision_role',       label: 'Decisor',              question: 'A decisão é só sua?',                     passive_hint: 'Se mencionar "consultar alguém"', mode: 'optional' },
    { key: 'constraints',         label: 'Restrições',           question: 'Tem alguma limitação?',                   passive_hint: 'Se lead mencionar restrições', mode: 'optional' },
  ],
};

const FILTER_LABELS: Record<FilterGroup, { title: string; sub: string }> = {
  f1: { title: 'Filtro 1 · Perfil e fit',    sub: 'Localização · uso pessoal · decisor' },
  f2: { title: 'Filtro 2 · Intenção e dor',  sub: 'Abertas · exploratórias · contexto' },
  f3: { title: 'Filtro 3 · 4Ps',             sub: 'Poder · prioridade · preço · timing' },
};

const MODE_COLORS: Record<FieldMode, { bg: string; border: string; text: string; label: string }> = {
  required: { bg: 'color-mix(in srgb, var(--o-purple) 15%, transparent)', border: 'var(--o-purple)', text: 'var(--o-purple)', label: 'Obrigatório' },
  optional:  { bg: 'color-mix(in srgb, #22c55e 10%, transparent)',        border: '#22c55e',          text: '#22c55e',          label: 'Opcional'    },
  off:       { bg: 'var(--o-b1)',                                          border: 'transparent',      text: 'var(--o-dim)',     label: 'Desligado'   },
};

// ─── Estado inicial ───────────────────────────────────────────

function buildInitialFields(mode: AgentMode): QualificationField[] {
  return SUGGESTIONS[mode];
}

// ─── Componentes internos ─────────────────────────────────────

function ModeToggle({ value, onChange }: { value: FieldMode; onChange: (v: FieldMode) => void }) {
  const modes: FieldMode[] = ['required', 'optional', 'off'];
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {modes.map(m => {
        const active = value === m;
        const c = MODE_COLORS[m];
        return (
          <button
            key={m}
            onClick={() => onChange(m)}
            style={{
              fontSize: 9, letterSpacing: 1.5, textTransform: 'uppercase',
              padding: '3px 8px', borderRadius: 3, cursor: 'pointer',
              background: active ? c.bg : 'transparent',
              border: `1px solid ${active ? c.border : 'var(--o-b1)'}`,
              color: active ? c.text : 'var(--o-dim)',
              fontWeight: active ? 600 : 400,
              transition: 'all .15s',
            }}
          >
            {m === 'required' ? '● Obrig.' : m === 'optional' ? '○ Opc.' : '× Off'}
          </button>
        );
      })}
    </div>
  );
}

// ─── Drawer de edição de campo ────────────────────────────────

interface FieldEditorDrawerProps {
  field: QualificationField;
  agentMode: AgentMode;
  responseStyle: ResponseStyle;
  onSave: (updated: QualificationField) => void;
  onRemove: () => void;
  onClose: () => void;
}

function FieldEditorDrawer({ field, agentMode, responseStyle, onSave, onRemove, onClose }: FieldEditorDrawerProps) {
  const [local, setLocal] = useState<QualificationField>({ ...field });
  const isSdr = agentMode === 'sdr_scheduler';

  return (
    <>
      <div className="o-drawer-overlay open" onClick={onClose} />
      <div className="o-drawer open">
        <div className="o-drawer-header">
          <div>
            <div className="font-display" style={{ fontSize: 20, fontWeight: 400, color: 'var(--o-text)' }}>
              {local.is_custom ? 'Campo personalizado' : 'Editar campo'}
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginTop: 4, fontWeight: 300 }}>
              {local.label}
            </div>
          </div>
          <button className="o-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="o-drawer-body" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Nome do campo */}
          {local.is_custom && (
            <div className="o-field">
              <label className="o-field-label">Nome do campo</label>
              <input
                className="o-input"
                value={local.label}
                placeholder="Ex: Nome do pet, Região de interesse…"
                onChange={e => {
                  const label = e.target.value;
                  const key = 'custom_' + label.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
                  setLocal(v => ({ ...v, label, key }));
                }}
              />
              {local.key && (
                <div className="o-field-hint">
                  Chave gerada: <span style={{ fontFamily: 'monospace', color: 'var(--o-purple)' }}>{local.key}</span>
                </div>
              )}
            </div>
          )}

          {/* Importância */}
          <div className="o-field">
            <label className="o-field-label">Importância</label>
            <div className="o-field-hint" style={{ marginBottom: 8 }}>
              {local.mode === 'required' ? 'Lead não avança no Kanban sem este dado preenchido.' :
               local.mode === 'optional' ? 'Capturado quando surgir naturalmente. Não bloqueia.' :
               'Ignorado pelo agente e pelo guardrail.'}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['required', 'optional', 'off'] as FieldMode[]).map(m => {
                const c = MODE_COLORS[m];
                const active = local.mode === m;
                return (
                  <button
                    key={m}
                    onClick={() => setLocal(v => ({ ...v, mode: m }))}
                    style={{
                      flex: 1, padding: '8px 0', borderRadius: 6, cursor: 'pointer',
                      background: active ? c.bg : 'var(--o-b1)',
                      border: `1px solid ${active ? c.border : 'transparent'}`,
                      color: active ? c.text : 'var(--o-dim)',
                      fontSize: 11, fontWeight: active ? 600 : 400,
                    }}
                  >
                    {c.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Para SDR: filtro */}
          {isSdr && (
            <div className="o-field">
              <label className="o-field-label">Filtro (SDR)</label>
              <div className="o-field-hint" style={{ marginBottom: 8 }}>Em qual etapa do pipeline este campo é coletado?</div>
              <div style={{ display: 'flex', gap: 8 }}>
                {(['f1', 'f2', 'f3'] as FilterGroup[]).map(g => {
                  const active = local.group === g;
                  return (
                    <button
                      key={g}
                      onClick={() => setLocal(v => ({ ...v, group: g }))}
                      style={{
                        flex: 1, padding: '7px 0', borderRadius: 6, cursor: 'pointer',
                        background: active ? 'color-mix(in srgb, var(--o-purple) 12%, transparent)' : 'var(--o-b1)',
                        border: `1px solid ${active ? 'var(--o-purple)' : 'transparent'}`,
                        color: active ? 'var(--o-purple)' : 'var(--o-dim)',
                        fontSize: 11, fontWeight: active ? 600 : 400,
                      }}
                    >
                      {FILTER_LABELS[g].title.split(' · ')[0]}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Pergunta — modo ativo */}
          <div className="o-field">
            <label className="o-field-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              Pergunta
              <span style={{ fontSize: 9, letterSpacing: 1.5, padding: '1px 6px', borderRadius: 3, background: 'var(--o-b1)', color: 'var(--o-sub)', textTransform: 'uppercase' }}>
                modo ativo
              </span>
            </label>
            <div className="o-field-hint">O que o agente pergunta diretamente ao lead.</div>
            <textarea
              className="o-textarea"
              rows={2}
              value={local.question}
              placeholder="Ex: Qual o melhor horário para você?"
              style={{ opacity: responseStyle === 'passive' ? 0.5 : 1 }}
              onChange={e => setLocal(v => ({ ...v, question: e.target.value }))}
            />
          </div>

          {/* Dica passiva */}
          <div className="o-field">
            <label className="o-field-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              Como inferir
              <span style={{ fontSize: 9, letterSpacing: 1.5, padding: '1px 6px', borderRadius: 3, background: 'var(--o-b1)', color: 'var(--o-sub)', textTransform: 'uppercase' }}>
                modo passivo
              </span>
            </label>
            <div className="o-field-hint">Quando o agente não pergunta — como ele capta esta informação da conversa.</div>
            <textarea
              className="o-textarea"
              rows={2}
              value={local.passive_hint}
              placeholder='Ex: Se lead mencionar "semana que vem" ou um horário'
              style={{ opacity: responseStyle === 'active' ? 0.5 : 1 }}
              onChange={e => setLocal(v => ({ ...v, passive_hint: e.target.value }))}
            />
          </div>

          {/* Remover */}
          {local.is_custom && (
            <button
              onClick={onRemove}
              style={{
                background: 'transparent', border: '1px solid #ef4444', color: '#ef4444',
                borderRadius: 6, padding: '8px 0', cursor: 'pointer', fontSize: 12,
              }}
            >
              Remover campo
            </button>
          )}
        </div>

        <div className="o-drawer-footer">
          <button className="o-btn o-btn-primary" onClick={() => onSave(local)}>Salvar</button>
          <button className="o-btn" onClick={onClose}>Cancelar</button>
        </div>
      </div>
    </>
  );
}

// ─── Linha de campo (lista plana) ─────────────────────────────

function FieldRow({ field, responseStyle, onClick }: {
  field: QualificationField;
  responseStyle: ResponseStyle;
  onClick: () => void;
}) {
  const c = MODE_COLORS[field.mode];
  const hint = responseStyle === 'active' ? field.question : field.passive_hint;
  const hintLabel = responseStyle === 'active' ? '→ pergunta:' : '→ inferir:';

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '11px 14px', borderRadius: 8, cursor: 'pointer',
        background: field.mode === 'off' ? 'var(--o-b1)' : c.bg,
        border: `1px solid ${field.mode === 'off' ? 'var(--o-b1)' : c.border}`,
        opacity: field.mode === 'off' ? 0.55 : 1,
        transition: 'all .15s',
      }}
    >
      {/* Indicador de modo */}
      <div style={{
        flexShrink: 0, width: 7, height: 7, borderRadius: '50%',
        background: field.mode === 'off' ? 'var(--o-dim)' : c.border,
      }} />

      {/* Label + hint */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, color: 'var(--o-text)', fontWeight: 500 }}>{field.label}</span>
          {field.is_custom && (
            <span style={{ fontSize: 8, letterSpacing: 1.5, padding: '1px 5px', borderRadius: 2, background: 'var(--o-b1)', color: 'var(--o-dim)', textTransform: 'uppercase' }}>custom</span>
          )}
        </div>
        {hint && field.mode !== 'off' && (
          <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 2, display: 'flex', gap: 4 }}>
            <span style={{ color: 'var(--o-dim)' }}>{hintLabel}</span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{hint}</span>
          </div>
        )}
      </div>

      {/* Badge modo */}
      <span style={{
        fontSize: 9, letterSpacing: 1.5, padding: '2px 7px', borderRadius: 3, flexShrink: 0,
        textTransform: 'uppercase', fontWeight: 600,
        color: c.text, background: c.bg, border: `1px solid ${c.border}`,
      }}>
        {c.label}
      </span>

      <span style={{ color: 'var(--o-dim)', fontSize: 14 }}>›</span>
    </div>
  );
}

// ─── Card de filtro SDR ───────────────────────────────────────

function SdrFilterCard({ group, fields, responseStyle, onFieldClick }: {
  group: FilterGroup;
  fields: QualificationField[];
  responseStyle: ResponseStyle;
  onFieldClick: (field: QualificationField) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const { title, sub } = FILTER_LABELS[group];
  const required = fields.filter(f => f.mode === 'required').length;
  const optional  = fields.filter(f => f.mode === 'optional').length;

  const displayTitle = responseStyle === 'passive'
    ? title.replace('Filtro', 'Sinais a capturar ·').replace(/Filtro \d · /, '')
    : title;

  return (
    <div style={{ border: '1px solid var(--o-b1)', borderRadius: 10, overflow: 'hidden', marginBottom: 10 }}>
      {/* Header do card */}
      <div
        onClick={() => setExpanded(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
          cursor: 'pointer', background: 'var(--o-b1)',
        }}
      >
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12.5, color: 'var(--o-text)', fontWeight: 500 }}>{displayTitle}</div>
          <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 2 }}>
            {responseStyle === 'passive' ? 'O que o agente busca entender' : sub}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {required > 0 && (
            <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 3, background: MODE_COLORS.required.bg, border: `1px solid ${MODE_COLORS.required.border}`, color: MODE_COLORS.required.text }}>
              {required} obrig.
            </span>
          )}
          {optional > 0 && (
            <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 3, background: MODE_COLORS.optional.bg, border: `1px solid ${MODE_COLORS.optional.border}`, color: MODE_COLORS.optional.text }}>
              {optional} opc.
            </span>
          )}
          <span style={{ color: 'var(--o-dim)', fontSize: 14, transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform .2s' }}>›</span>
        </div>
      </div>

      {/* Perguntas expandidas */}
      {expanded && (
        <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {fields.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--o-dim)', padding: '8px 0' }}>
              Nenhum campo neste filtro.
            </div>
          )}
          {fields.map(field => (
            <FieldRow key={field.key} field={field} responseStyle={responseStyle} onClick={() => onFieldClick(field)} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Painel JSON derivado ─────────────────────────────────────

function JsonPanel({ fields }: { fields: QualificationField[] }) {
  const [open, setOpen] = useState(false);

  const qualification_required_fields = fields
    .filter(f => f.mode === 'required')
    .map(f => f.key);

  const contract = {
    qualification_fields: fields.map(({ key, label, question, passive_hint, mode, group }) =>
      ({ key, label, question: question || null, passive_hint: passive_hint || null, mode, ...(group ? { group } : {}) })
    ),
    qualification_required_fields,
    f1_questions: fields.filter(f => f.group === 'f1').map(f => f.question).filter(Boolean),
    f2_questions: fields.filter(f => f.group === 'f2').map(f => f.question).filter(Boolean),
    f3_questions: fields.filter(f => f.group === 'f3').map(f => f.question).filter(Boolean),
  };

  return (
    <div style={{ marginTop: 32, border: '1px solid var(--o-b1)', borderRadius: 10, overflow: 'hidden' }}>
      <div
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px', cursor: 'pointer', background: 'var(--o-b1)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-purple)', fontWeight: 600 }}>
            JSON derivado
          </span>
          <span style={{ fontSize: 11, color: 'var(--o-sub)' }}>
            — o que seria enviado para a API
          </span>
        </div>
        <span style={{ color: 'var(--o-dim)', fontSize: 14, transform: open ? 'rotate(90deg)' : 'none', transition: 'transform .2s' }}>›</span>
      </div>

      {open && (
        <div style={{ padding: 16 }}>
          {/* Campos obrigatórios derivados */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 10, letterSpacing: 1.5, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>
              qualification_required_fields (para guardrails)
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {qualification_required_fields.length === 0
                ? <span style={{ fontSize: 11.5, color: 'var(--o-warn)' }}>[] — agente sem obrigações de qualificação (modo passivo)</span>
                : qualification_required_fields.map(k => (
                  <span key={k} style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: MODE_COLORS.required.bg, border: `1px solid ${MODE_COLORS.required.border}`, color: MODE_COLORS.required.text, fontFamily: 'monospace' }}>
                    {k}
                  </span>
                ))
              }
            </div>
          </div>

          {/* JSON completo */}
          <pre style={{
            fontSize: 11, lineHeight: 1.6, color: 'var(--o-sub)',
            background: 'var(--o-bg)', padding: 14, borderRadius: 8,
            overflow: 'auto', maxHeight: 400,
            border: '1px solid var(--o-b1)',
          }}>
            {JSON.stringify(contract, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// ─── Página principal ─────────────────────────────────────────

export default function DebugAiProfile() {
  const [agentMode, setAgentMode] = useState<AgentMode>('sdr_scheduler');
  const [responseStyle, setResponseStyle] = useState<ResponseStyle>('active');
  const [fields, setFields] = useState<QualificationField[]>(buildInitialFields('sdr_scheduler'));
  const [editingField, setEditingField] = useState<QualificationField | null>(null);
  const [suggestionPending, setSuggestionPending] = useState<AgentMode | null>(null);
  const [addingField, setAddingField] = useState(false);

  const isSdr = agentMode === 'sdr_scheduler';

  // Trocar modo com sugestão
  const handleModeChange = useCallback((mode: AgentMode) => {
    if (mode === agentMode) return;
    setSuggestionPending(mode);
    setAgentMode(mode);
  }, [agentMode]);

  // Aplicar sugestão
  const handleApplySuggestion = () => {
    if (suggestionPending) {
      setFields(buildInitialFields(suggestionPending));
      setSuggestionPending(null);
    }
  };

  // Salvar campo editado
  const handleSaveField = (updated: QualificationField) => {
    if (addingField) {
      setFields(prev => [...prev, updated]);
      setAddingField(false);
    } else {
      setFields(prev => prev.map(f => f.key === updated.key ? updated : f));
    }
    setEditingField(null);
  };

  // Remover campo
  const handleRemoveField = () => {
    if (editingField) {
      setFields(prev => prev.filter(f => f.key !== editingField.key));
      setEditingField(null);
    }
  };

  // Novo campo personalizado vazio
  const newCustomField = (): QualificationField => ({
    key: '',
    label: '',
    question: '',
    passive_hint: '',
    mode: 'optional',
    group: isSdr ? 'f1' : undefined,
    is_custom: true,
  });

  // Campos por filtro (SDR)
  const fieldsByGroup = (group: FilterGroup) => fields.filter(f => f.group === group);
  const flatFields = fields;

  return (
    <OrionShell>
      {/* Topbar de debug */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        background: 'var(--o-bg)', borderBottom: '1px solid var(--o-b1)',
        display: 'flex', alignItems: 'center', gap: 16, padding: '10px 24px',
      }}>
        <span style={{ fontSize: 9, letterSpacing: 2.5, textTransform: 'uppercase', color: '#f59e0b', fontWeight: 700 }}>
          ⚡ Debug UI
        </span>
        <span style={{ fontSize: 12, color: 'var(--o-sub)' }}>
          Fase 4 — CamadaQualificacao dinâmica
        </span>
        <span style={{ fontSize: 10, color: 'var(--o-dim)', marginLeft: 'auto' }}>
          Sem API · Estado local · Apenas frontend
        </span>
      </div>

      <div style={{ maxWidth: 860, margin: '0 auto', padding: '32px 24px 80px' }}>

        {/* Título */}
        <div style={{ marginBottom: 32 }}>
          <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 3, textTransform: 'uppercase', color: 'var(--o-purple)', marginBottom: 8 }}>
            AI Profile · Camada 2 — Qualificação
          </div>
          <div className="font-display" style={{ fontSize: 28, fontWeight: 400, color: 'var(--o-text)', marginBottom: 6 }}>
            Nova experiência de qualificação
          </div>
          <div style={{ fontSize: 13, color: 'var(--o-sub)', fontWeight: 300 }}>
            Teste a UI da Fase 4: campos unificados, distinção obrigatório/opcional, editor por campo e modo passivo.
          </div>
        </div>

        {/* Seletor de tipo de agente */}
        <div style={{ marginBottom: 28 }}>
          <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 2.5, textTransform: 'uppercase', color: 'var(--o-sub)', marginBottom: 10 }}>
            Tipo de agente (Camada 1)
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {(Object.keys(AGENT_MODE_LABELS) as AgentMode[]).map(mode => {
              const active = mode === agentMode;
              return (
                <button
                  key={mode}
                  onClick={() => handleModeChange(mode)}
                  style={{
                    padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
                    background: active ? 'color-mix(in srgb, var(--o-purple) 15%, transparent)' : 'var(--o-b1)',
                    border: `1px solid ${active ? 'var(--o-purple)' : 'transparent'}`,
                    color: active ? 'var(--o-purple)' : 'var(--o-text)',
                    fontSize: 12.5, fontWeight: active ? 600 : 400,
                    transition: 'all .15s',
                  }}
                >
                  {AGENT_MODE_LABELS[mode]}
                </button>
              );
            })}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginTop: 8, fontStyle: 'italic' }}>
            {AGENT_MODE_DESC[agentMode]}
          </div>
        </div>

        {/* Banner de sugestão */}
        {suggestionPending && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 14,
            padding: '12px 16px', borderRadius: 8, marginBottom: 20,
            background: 'color-mix(in srgb, #f59e0b 10%, transparent)',
            border: '1px solid color-mix(in srgb, #f59e0b 40%, transparent)',
          }}>
            <span style={{ fontSize: 16 }}>⚙</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12.5, color: 'var(--o-text)', fontWeight: 500, marginBottom: 2 }}>
                Sugestão para "{AGENT_MODE_LABELS[suggestionPending]}"
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--o-sub)' }}>
                Campos típicos para este tipo de agente foram pré-selecionados.
              </div>
            </div>
            <button
              onClick={handleApplySuggestion}
              style={{
                padding: '6px 14px', borderRadius: 6, cursor: 'pointer',
                background: '#f59e0b', border: 'none', color: '#000',
                fontSize: 12, fontWeight: 600,
              }}
            >
              Aplicar sugestão
            </button>
            <button
              onClick={() => setSuggestionPending(null)}
              style={{
                padding: '6px 14px', borderRadius: 6, cursor: 'pointer',
                background: 'transparent', border: '1px solid var(--o-b1)',
                color: 'var(--o-sub)', fontSize: 12,
              }}
            >
              Manter atual
            </button>
          </div>
        )}

        {/* Toggle response_style — Fase 4.1 */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 0,
          border: '1px solid var(--o-b1)', borderRadius: 10, overflow: 'hidden', marginBottom: 28,
        }}>
          <div style={{ padding: '14px 18px', background: 'var(--o-b1)', flexShrink: 0 }}>
            <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 2.5, textTransform: 'uppercase', color: 'var(--o-sub)' }}>
              Como o agente coleta informações
            </div>
          </div>
          <div style={{ flex: 1, display: 'flex', padding: '10px 16px', gap: 12, alignItems: 'center' }}>
            <button
              onClick={() => setResponseStyle('active')}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 8, cursor: 'pointer',
                background: responseStyle === 'active' ? 'color-mix(in srgb, var(--o-purple) 12%, transparent)' : 'var(--o-b1)',
                border: `1px solid ${responseStyle === 'active' ? 'var(--o-purple)' : 'transparent'}`,
                color: responseStyle === 'active' ? 'var(--o-purple)' : 'var(--o-dim)',
                transition: 'all .2s',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: responseStyle === 'active' ? 600 : 400, marginBottom: 2 }}>
                Conduz a conversa
              </div>
              <div style={{ fontSize: 10.5, opacity: 0.75 }}>Pergunta ativamente</div>
            </button>
            <button
              onClick={() => setResponseStyle('passive')}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 8, cursor: 'pointer',
                background: responseStyle === 'passive' ? 'color-mix(in srgb, #22c55e 10%, transparent)' : 'var(--o-b1)',
                border: `1px solid ${responseStyle === 'passive' ? '#22c55e' : 'transparent'}`,
                color: responseStyle === 'passive' ? '#22c55e' : 'var(--o-dim)',
                transition: 'all .2s',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: responseStyle === 'passive' ? 600 : 400, marginBottom: 2 }}>
                Segue o ritmo do cliente
              </div>
              <div style={{ fontSize: 10.5, opacity: 0.75 }}>Responde e infere</div>
            </button>
          </div>
        </div>

        {/* Seção: campos de qualificação */}
        <div className="o-section-hdr" style={{ marginBottom: 14 }}>
          <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
            {responseStyle === 'active'
              ? (isSdr ? 'Filtros de qualificação' : 'O que o agente deve descobrir')
              : (isSdr ? 'Sinais a capturar' : 'O que o agente precisa saber')}
          </span>
          <span className="font-mono-orion" style={{ fontSize: 8, color: 'var(--o-dim)', border: '1px solid var(--o-b1)', padding: '1px 6px', borderRadius: 2 }}>
            {fields.filter(f => f.mode === 'required').length} obrigatório(s) · {fields.filter(f => f.mode === 'optional').length} opcional(is)
          </span>
        </div>

        {/* Contextual hint */}
        <div style={{ fontSize: 12, color: 'var(--o-sub)', marginBottom: 16, padding: '8px 12px', background: 'var(--o-b1)', borderRadius: 6 }}>
          {responseStyle === 'active'
            ? isSdr
              ? 'Agente pergunta na sequência F1→F2→F3. Cada filtro tem sua etapa da conversa.'
              : 'Agente pergunta diretamente quando o campo ainda não foi respondido.'
            : isSdr
              ? 'Agente não pergunta — observa e infere. Os filtros indicam o que ele busca entender em cada momento.'
              : 'Agente não pergunta diretamente. Capta dados ao responder. Use "Como inferir" para orientar.'}
        </div>

        {/* SDR: cards de filtro F1/F2/F3 */}
        {isSdr && (
          <div style={{ marginBottom: 16 }}>
            {(['f1', 'f2', 'f3'] as FilterGroup[]).map(group => (
              <SdrFilterCard
                key={group}
                group={group}
                fields={fieldsByGroup(group)}
                responseStyle={responseStyle}
                onFieldClick={setEditingField}
              />
            ))}
          </div>
        )}

        {/* Outros agentes: lista plana */}
        {!isSdr && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
            {flatFields.length === 0 && (
              <div style={{ fontSize: 12.5, color: 'var(--o-dim)', padding: '16px 0', textAlign: 'center' }}>
                Nenhum campo configurado. Adicione abaixo.
              </div>
            )}
            {flatFields.map(field => (
              <FieldRow
                key={field.key}
                field={field}
                responseStyle={responseStyle}
                onClick={() => setEditingField(field)}
              />
            ))}
          </div>
        )}

        {/* Botão de adicionar campo */}
        <button
          onClick={() => { setEditingField(newCustomField()); setAddingField(true); }}
          style={{
            width: '100%', padding: '10px 0', borderRadius: 8, cursor: 'pointer',
            background: 'transparent', border: '1px dashed var(--o-b1)',
            color: 'var(--o-sub)', fontSize: 13,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            transition: 'all .15s',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--o-purple)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--o-purple)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--o-b1)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--o-sub)'; }}
        >
          <span style={{ fontSize: 16 }}>＋</span>
          Adicionar campo personalizado
        </button>

        {/* Painel de legenda */}
        <div style={{ marginTop: 24, padding: '12px 16px', borderRadius: 8, background: 'var(--o-b1)' }}>
          <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 2.5, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 10 }}>
            Legenda dos modos de campo
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }}>
            {(['required', 'optional', 'off'] as FieldMode[]).map(m => {
              const c = MODE_COLORS[m];
              return (
                <div key={m} style={{ padding: '8px 12px', borderRadius: 6, background: c.bg, border: `1px solid ${c.border}` }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: c.text, marginBottom: 4 }}>{c.label}</div>
                  <div style={{ fontSize: 10.5, color: 'var(--o-sub)' }}>
                    {m === 'required'
                      ? 'Lead não avança no Kanban sem responder. Agente prioriza capturar.'
                      : m === 'optional'
                      ? 'Capturado se surgir. Não bloqueia avanço. Enriquece o perfil.'
                      : 'Ignorado pelo agente e pelo guardrail. Não aparece no pipeline.'}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Painel JSON */}
        <JsonPanel fields={fields} />

      </div>

      {/* Drawer de edição */}
      {editingField && (
        <FieldEditorDrawer
          field={editingField}
          agentMode={agentMode}
          responseStyle={responseStyle}
          onSave={handleSaveField}
          onRemove={handleRemoveField}
          onClose={() => { setEditingField(null); setAddingField(false); }}
        />
      )}
    </OrionShell>
  );
}
