import { useState, useEffect, useRef } from 'react';
import { FieldHelp } from './FieldHelp';
import { SuggestInput, SuggestTextarea } from './SuggestField';
import type { AgentConfig, QualificationField } from '@/types/agente';
import { api } from '@/services/api';

interface CamadaQualificacaoProps {
  config: AgentConfig;
  onUpdate: (partial: Partial<AgentConfig>) => void;
}

// ─── Sugestões por agent_mode ─────────────────────────────────

const SUGGESTIONS: Record<string, QualificationField[]> = {
  sdr_scheduler: [
    { key: 'location_preference', label: 'Localização', question: 'Você está em [cidade/região]?', passive_hint: 'Capturar se lead mencionar cidade ou bairro', mode: 'required', group: 'f1' },
    { key: 'decision_role', label: 'Decisor', question: 'Você toma as decisões de compra?', passive_hint: 'Capturar se lead mencionar outra pessoa', mode: 'required', group: 'f1' },
    { key: 'service_interest', label: 'Serviço de interesse', question: 'O que você busca?', passive_hint: 'Inferir pelo contexto da conversa', mode: 'required', group: 'f2' },
    { key: 'urgency', label: 'Urgência', question: 'Quão urgente é para você?', passive_hint: 'Capturar expressões de urgência', mode: 'optional', group: 'f2' },
    { key: 'availability_window', label: 'Disponibilidade', question: 'Qual horário funciona para você?', passive_hint: 'Capturar se lead mencionar horário ou data', mode: 'required', group: 'f3', allow_closing_question: true, closing_question: 'Você teria disponibilidade na quinta às 14h ou na sexta às 10h?' },
    { key: 'price_acceptance', label: 'Aceitação de preço', question: 'Já tem um valor em mente?', passive_hint: 'Capturar se lead mencionar valor', mode: 'optional', group: 'f3' },
  ],
  agenda: [
    { key: 'availability_window', label: 'Disponibilidade', question: 'Qual o melhor horário para você?', passive_hint: 'Capturar horários ou datas mencionadas', mode: 'required', allow_closing_question: true, closing_question: 'Você prefere às 14h ou às 16h?' },
    { key: 'service_interest', label: 'Serviço de interesse', question: 'O que você busca?', passive_hint: 'Inferir pelo contexto', mode: 'optional' },
    { key: 'location_preference', label: 'Local', question: 'Prefere presencial ou online?', passive_hint: 'Capturar preferência de formato', mode: 'optional' },
    { key: 'decision_role', label: 'Decisor', question: 'Você decide ou precisa consultar alguém?', passive_hint: 'Capturar menção de terceiros', mode: 'required' },
  ],
  closer: [
    { key: 'service_interest', label: 'Serviço de interesse', question: 'O que você precisa?', passive_hint: 'Inferir pelo contexto', mode: 'required' },
    { key: 'decision_role', label: 'Decisor', question: 'Você toma as decisões?', passive_hint: 'Capturar menção de terceiros', mode: 'required' },
    { key: 'budget_or_price_acceptance', label: 'Orçamento', question: 'Qual o seu orçamento?', passive_hint: 'Capturar menção de valores', mode: 'optional' },
  ],
  direto: [
    { key: 'service_interest', label: 'Serviço de interesse', question: 'O que você precisa?', passive_hint: 'Inferir pelo contexto', mode: 'required' },
    { key: 'decision_role', label: 'Decisor', question: 'Você decide?', passive_hint: 'Capturar menção de terceiros', mode: 'required' },
    { key: 'urgency', label: 'Urgência', question: 'Quando precisa resolver?', passive_hint: 'Capturar expressões de timing', mode: 'optional' },
  ],
  consultivo: [
    { key: 'service_interest', label: 'Serviço de interesse', question: 'O que você busca?', passive_hint: 'Inferir pelo contexto', mode: 'required' },
    { key: 'urgency', label: 'Urgência', question: 'Qual o prazo ideal?', passive_hint: 'Capturar expressões de urgência', mode: 'required' },
    { key: 'decision_role', label: 'Decisor', question: 'Quem participa da decisão?', passive_hint: 'Capturar menção de terceiros', mode: 'optional' },
    { key: 'budget_or_price_acceptance', label: 'Orçamento', question: 'Tem orçamento definido?', passive_hint: 'Capturar menção de valores', mode: 'optional' },
    { key: 'constraints', label: 'Restrições', question: 'Tem alguma limitação de horário?', passive_hint: 'Capturar limitações mencionadas', mode: 'optional' },
    { key: 'location_preference', label: 'Local preferido', question: 'Prefere presencial ou online?', passive_hint: 'Capturar preferência de formato', mode: 'optional' },
  ],
};

const MODE_LABELS: Record<string, string> = {
  sdr_scheduler: 'SDR Agendador',
  agenda: 'Agendador',
  closer: 'Closer',
  direto: 'Direto',
  consultivo: 'Consultivo',
};

// ─── Helpers ──────────────────────────────────────────────────

function slugify(label: string): string {
  return label.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
}

function deriveF1F2F3(fields: QualificationField[]) {
  return {
    f1_questions: fields.filter(f => f.group === 'f1' && f.mode !== 'off').map(f => f.question ?? f.label),
    f2_questions: fields.filter(f => f.group === 'f2' && f.mode !== 'off').map(f => f.question ?? f.label),
    f3_questions: fields.filter(f => f.group === 'f3' && f.mode !== 'off').map(f => f.question ?? f.label),
    qualification_required_fields: fields.filter(f => f.mode === 'required').map(f => f.key),
  };
}

function cycleMode(mode: QualificationField['mode']): QualificationField['mode'] {
  if (mode === 'required') return 'optional';
  if (mode === 'optional') return 'off';
  return 'required';
}

// ─── 4.1 — Toggle response_style ─────────────────────────────

function ToggleResponseStyle({ value, onChange }: {
  value: 'active' | 'passive';
  onChange: (v: 'active' | 'passive') => void;
}) {
  return (
    <div style={{
      border: '1px solid var(--o-b2)',
      borderRadius: 8,
      marginBottom: 24,
      overflow: 'hidden',
    }}>
      <div style={{ padding: '10px 16px', background: 'var(--o-b1)', borderBottom: '1px solid var(--o-b2)' }}>
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Como o agente coleta informações
        </span>
        <div style={{ fontSize: 11, color: 'var(--o-dim)', marginTop: 4 }}>
          Ambos os modos respondem perguntas e capturam dados mencionados automaticamente.
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
        <button
          onClick={() => onChange('active')}
          style={{
            padding: '14px 16px', border: 'none', cursor: 'pointer', textAlign: 'left',
            background: value === 'active' ? 'color-mix(in srgb, var(--o-purple) 10%, transparent)' : 'transparent',
            borderRight: '1px solid var(--o-b2)',
            borderBottom: 'none',
            outline: value === 'active' ? '2px solid var(--o-purple)' : 'none',
            outlineOffset: -2,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div style={{
              width: 16, height: 16, borderRadius: '50%',
              border: `2px solid ${value === 'active' ? 'var(--o-purple)' : 'var(--o-dim)'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              {value === 'active' && <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--o-purple)' }} />}
            </div>
            <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--o-text)' }}>Conduz a conversa</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--o-sub)', paddingLeft: 24, lineHeight: 1.5 }}>
            Pergunta proativamente quando um campo está em falta
          </div>
          <div style={{ fontSize: 10, color: 'var(--o-dim)', paddingLeft: 24, marginTop: 4 }}>
            Todos os campos · Sem restrição
          </div>
        </button>
        <button
          onClick={() => onChange('passive')}
          style={{
            padding: '14px 16px', border: 'none', cursor: 'pointer', textAlign: 'left',
            background: value === 'passive' ? 'color-mix(in srgb, var(--o-purple) 10%, transparent)' : 'transparent',
            outline: value === 'passive' ? '2px solid var(--o-purple)' : 'none',
            outlineOffset: -2,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div style={{
              width: 16, height: 16, borderRadius: '50%',
              border: `2px solid ${value === 'passive' ? 'var(--o-purple)' : 'var(--o-dim)'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              {value === 'passive' && <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--o-purple)' }} />}
            </div>
            <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--o-text)' }}>Responde com persuasão</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--o-sub)', paddingLeft: 24, lineHeight: 1.5 }}>
            Guia para o próximo passo sem perguntas de qualificação
          </div>
          <div style={{ fontSize: 10, color: 'var(--o-dim)', paddingLeft: 24, marginTop: 4 }}>
            ⚡ Apenas perguntas de fechamento permitidas em F3
          </div>
        </button>
      </div>
    </div>
  );
}

// ─── 4.6 — Banner de sugestão por agent_mode ─────────────────

function BannerSugestao({ mode, onApply, onDismiss }: {
  mode: string;
  onApply: () => void;
  onDismiss: () => void;
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '10px 14px', marginBottom: 16, borderRadius: 6,
      background: 'color-mix(in srgb, var(--o-purple) 8%, transparent)',
      border: '1px solid color-mix(in srgb, var(--o-purple) 30%, transparent)',
    }}>
      <div>
        <div style={{ fontSize: 12.5, color: 'var(--o-text)', fontWeight: 500 }}>
          ⚙ Sugestão para "{MODE_LABELS[mode] ?? mode}"
        </div>
        <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 3 }}>
          Campos típicos para este tipo de agente foram pré-selecionados.
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexShrink: 0, marginLeft: 16 }}>
        <button className="o-btn o-btn-primary" style={{ fontSize: 11, padding: '4px 12px' }} onClick={onApply}>
          Aplicar sugestão
        </button>
        <button className="o-btn" style={{ fontSize: 11, padding: '4px 10px' }} onClick={onDismiss}>
          Manter atual
        </button>
      </div>
    </div>
  );
}

// ─── Badge de modo de campo ───────────────────────────────────

function ModeBadge({ mode, passive, onClick }: {
  mode: QualificationField['mode'];
  passive?: boolean;
  onClick?: () => void;
}) {
  const labels: Record<string, [string, string]> = passive
    ? { required: ['●', 'Essencial'], optional: ['○', 'Desejável'], off: ['×', 'Ignorar'] }
    : { required: ['●', 'Obrigatório'], optional: ['○', 'Opcional'], off: ['×', 'Desligado'] };

  const colors: Record<string, string> = {
    required: 'var(--o-purple)',
    optional: 'var(--o-warn)',
    off: 'var(--o-dim)',
  };

  const [icon, label] = labels[mode];
  return (
    <button
      onClick={onClick}
      title={onClick ? 'Clique para alternar' : undefined}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 8px',
        borderRadius: 4, border: `1px solid ${colors[mode]}`, background: 'transparent',
        color: colors[mode], fontSize: 11, fontWeight: 500, cursor: onClick ? 'pointer' : 'default',
        whiteSpace: 'nowrap', flexShrink: 0,
      }}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

// ─── 4.4 — Drawer: Editor de campo ───────────────────────────

function DrawerCampo({ field, isSdr, onSave, onClose, onRemove }: {
  field: QualificationField;
  isSdr: boolean;
  onSave: (f: QualificationField) => void;
  onClose: () => void;
  onRemove?: () => void;
}) {
  const [local, setLocal] = useState<QualificationField>({ ...field });

  function up<K extends keyof QualificationField>(key: K, val: QualificationField[K]) {
    setLocal(prev => ({ ...prev, [key]: val }));
  }

  const isCustom = local.key.startsWith('custom_');

  return (
    <DrawerBase title="Editar campo" sub="Configure como o agente coleta esta informação" onClose={onClose} onSave={() => onSave(local)}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Label */}
        <div className="o-field">
          <label className="o-field-label">Nome do campo</label>
          {isCustom
            ? <SuggestInput className="o-input" value={local.label} onChange={e => up('label', e.target.value)} placeholder="Ex: Nome do pet" />
            : <div style={{ fontSize: 13, color: 'var(--o-text)', padding: '8px 0' }}>{local.label}</div>
          }
        </div>

        {/* Mode */}
        <div className="o-field">
          <label className="o-field-label">Importância</label>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            {(['required', 'optional', 'off'] as const).map(m => (
              <button
                key={m}
                onClick={() => up('mode', m)}
                style={{
                  flex: 1, padding: '7px 0', borderRadius: 5, border: '1px solid',
                  cursor: 'pointer', fontSize: 11.5, fontWeight: 500,
                  borderColor: local.mode === m ? 'var(--o-purple)' : 'var(--o-b2)',
                  background: local.mode === m ? 'color-mix(in srgb, var(--o-purple) 15%, transparent)' : 'transparent',
                  color: local.mode === m ? 'var(--o-purple)' : 'var(--o-sub)',
                }}
              >
                {m === 'required' ? '● Obrigatório' : m === 'optional' ? '○ Opcional' : '× Desligado'}
              </button>
            ))}
          </div>
        </div>

        {/* Group (SDR only) */}
        {isSdr && (
          <div className="o-field">
            <label className="o-field-label">Filtro (SDR)</label>
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              {(['f1', 'f2', 'f3'] as const).map(g => (
                <button
                  key={g}
                  onClick={() => up('group', g)}
                  style={{
                    flex: 1, padding: '7px 0', borderRadius: 5, border: '1px solid',
                    cursor: 'pointer', fontSize: 11.5, fontWeight: 500,
                    borderColor: local.group === g ? 'var(--o-purple)' : 'var(--o-b2)',
                    background: local.group === g ? 'color-mix(in srgb, var(--o-purple) 15%, transparent)' : 'transparent',
                    color: local.group === g ? 'var(--o-purple)' : 'var(--o-sub)',
                  }}
                >
                  {g === 'f1' ? 'F1 · Fit' : g === 'f2' ? 'F2 · Dor' : 'F3 · Fechamento'}
                </button>
              ))}
            </div>
            {local.group === 'f3' && (
              <div style={{ fontSize: 10.5, color: 'var(--o-dim)', marginTop: 6 }}>
                ⚡ Campos F3 podem ter pergunta estratégica de fechamento no modo passivo
              </div>
            )}
          </div>
        )}

        {/* Divider */}
        <div style={{ borderTop: '1px solid var(--o-b2)', paddingTop: 4 }}>
          <div style={{ fontSize: 10, color: 'var(--o-dim)', letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 12 }}>
            Modo ativo
          </div>

          <div className="o-field">
            <label className="o-field-label">Pergunta direta</label>
            <div className="o-field-hint">Usada quando o agente pergunta proativamente.</div>
            <SuggestTextarea
              className="o-textarea"
              rows={2}
              value={local.question ?? ''}
              onChange={e => up('question', e.target.value)}
              placeholder="Ex: Qual o melhor horário para você?"
            />
          </div>
        </div>

        {/* Passive section */}
        <div style={{ borderTop: '1px solid var(--o-b2)', paddingTop: 4 }}>
          <div style={{ fontSize: 10, color: 'var(--o-dim)', letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 12 }}>
            Modo passivo
          </div>

          <div className="o-field">
            <label className="o-field-label">Como capturar passivamente</label>
            <div className="o-field-hint">Orienta o agente a detectar o dado sem perguntar.</div>
            <SuggestTextarea
              className="o-textarea"
              rows={2}
              value={local.passive_hint ?? ''}
              onChange={e => up('passive_hint', e.target.value)}
              placeholder="Ex: Capturar se lead mencionar horário, data ou 'semana que vem'"
            />
          </div>

          {/* Closing question */}
          <div className="o-field" style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <div
                onClick={() => up('allow_closing_question', !local.allow_closing_question)}
                style={{
                  width: 36, height: 20, borderRadius: 10, cursor: 'pointer',
                  background: local.allow_closing_question ? 'var(--o-purple)' : 'var(--o-dim)',
                  position: 'relative', flexShrink: 0, transition: 'background .2s',
                }}
              >
                <div style={{
                  position: 'absolute', top: 3,
                  left: local.allow_closing_question ? 18 : 3,
                  width: 14, height: 14, borderRadius: '50%', background: '#fff', transition: 'left .2s',
                }} />
              </div>
              <label className="o-field-label" style={{ marginBottom: 0, cursor: 'pointer' }}
                onClick={() => up('allow_closing_question', !local.allow_closing_question)}>
                ⚡ Pergunta estratégica de fechamento
              </label>
            </div>
            {local.allow_closing_question && (
              <>
                <SuggestTextarea
                  className="o-textarea"
                  rows={2}
                  value={local.closing_question ?? ''}
                  onChange={e => up('closing_question', e.target.value)}
                  placeholder="Ex: Você teria disponibilidade na quinta às 14h ou na sexta às 10h?"
                />
                <div style={{ fontSize: 10.5, color: 'var(--o-dim)', marginTop: 6 }}>
                  Única pergunta permitida no modo passivo. Use alternativas binárias ou confirmações — nunca perguntas abertas.
                </div>
              </>
            )}
          </div>
        </div>

        {/* Remove custom field */}
        {onRemove && (
          <div style={{ borderTop: '1px solid var(--o-b2)', paddingTop: 12 }}>
            <button
              onClick={onRemove}
              style={{
                background: 'transparent', border: '1px solid var(--o-warn)',
                color: 'var(--o-warn)', borderRadius: 5, padding: '5px 12px', cursor: 'pointer', fontSize: 12,
              }}
            >
              Remover campo
            </button>
          </div>
        )}
      </div>
    </DrawerBase>
  );
}

// ─── 4.2 — Modal de filtro SDR (com badges de modo) ──────────

function ModalFiltroSDR({ group, responseStyle, fields, onUpdate, onClose, onAddField }: {
  group: 'f1' | 'f2' | 'f3';
  responseStyle: 'active' | 'passive';
  fields: QualificationField[];
  onUpdate: (fields: QualificationField[]) => void;
  onClose: () => void;
  onAddField: () => void;
}) {
  const [editingField, setEditingField] = useState<QualificationField | null>(null);
  const [filterPreview, setFilterPreview] = useState<QualificationField[] | null>(null);
  const [filterExplanation, setFilterExplanation] = useState('');
  const [isFilterGenerating, setIsFilterGenerating] = useState(false);
  const [filterGenError, setFilterGenError] = useState<string | null>(null);

  const titles = { f1: 'Filtro 1 · Perfil e fit', f2: 'Filtro 2 · Intenção e dor', f3: 'Filtro 3 · 4Ps' };
  const subs = {
    f1: 'Perguntas binárias que validam se o lead está dentro do seu público-alvo',
    f2: 'Perguntas abertas que revelam contexto, urgência e a dor do lead',
    f3: 'Qualificação profunda via conversa consultiva — os 4Ps',
  };
  const passiveLabels = {
    f1: 'indícios de fit captados passivamente',
    f2: 'sinais de dor captados sem perguntar',
    f3: 'confirmações e perguntas de fechamento',
  };

  const groupFields = fields.filter(f => f.group === group);

  function handleCycleMode(key: string) {
    onUpdate(fields.map(f => f.key === key ? { ...f, mode: cycleMode(f.mode) } : f));
  }

  function handleSaveField(updated: QualificationField) {
    onUpdate(fields.map(f => f.key === updated.key ? updated : f));
    setEditingField(null);
  }

  function handleRemoveField(key: string) {
    onUpdate(fields.filter(f => f.key !== key));
    setEditingField(null);
  }

  const isPassive = responseStyle === 'passive';

  async function handleGenerateForFilter() {
    setIsFilterGenerating(true);
    setFilterGenError(null);
    try {
      const existingKeys = groupFields.map(f => f.key);
      const result = await api.agente.generateFieldsForFilter(group, existingKeys);
      setFilterPreview(result.fields);
      setFilterExplanation(result.explanation);
    } catch (err: unknown) {
      setFilterGenError(err instanceof Error ? err.message : 'Erro ao gerar campos');
    } finally {
      setIsFilterGenerating(false);
    }
  }

  function applyFilterPreview(mode: 'merge' | 'replace') {
    if (!filterPreview) return;
    if (mode === 'replace') {
      onUpdate([...fields.filter(f => f.group !== group), ...filterPreview]);
    } else {
      const existingKeys = new Set(groupFields.map(f => f.key));
      const toAdd = filterPreview.filter(f => !existingKeys.has(f.key));
      onUpdate([...fields, ...toAdd]);
    }
    setFilterPreview(null);
  }

  return (
    <>
      <ModalBase
        title={titles[group]}
        sub={isPassive ? passiveLabels[group] : subs[group]}
        onClose={onClose}
        onSave={onClose}
        disableBackdropClose={!!editingField || !!filterPreview}
      >
        {/* Botão Gerar com IA por filtro */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
          <button
            className="o-btn o-btn-sm"
            onClick={handleGenerateForFilter}
            disabled={isFilterGenerating}
            style={{ fontSize: 10, padding: '2px 8px', opacity: isFilterGenerating ? 0.6 : 1 }}
          >
            {isFilterGenerating ? '...' : '✦ Gerar com IA'}
          </button>
        </div>

        {/* Erro de geração */}
        {filterGenError && (
          <div style={{ fontSize: 11, color: 'var(--o-error, #f87171)', marginBottom: 8 }}>
            {filterGenError}
          </div>
        )}

        {/* Preview dos campos gerados */}
        {filterPreview && (
          <div style={{
            background: 'color-mix(in srgb, var(--o-purple) 5%, transparent)',
            border: '1px solid color-mix(in srgb, var(--o-purple) 30%, transparent)',
            borderRadius: 6, padding: 12, marginBottom: 12,
          }}>
            {filterExplanation && (
              <div style={{ fontSize: 11, color: 'var(--o-sub)', marginBottom: 10 }}>
                ✦ {filterExplanation}
              </div>
            )}
            {filterPreview.map(f => (
              <div key={f.key} style={{ fontSize: 12, marginBottom: 6, padding: '7px 10px', background: 'var(--o-b1)', borderRadius: 4 }}>
                <div style={{ fontWeight: 500, color: 'var(--o-text)' }}>{f.label}</div>
                {f.question && (
                  <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 2 }}>"{f.question}"</div>
                )}
              </div>
            ))}
            <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
              <button className="o-btn o-btn-primary o-btn-sm" onClick={() => applyFilterPreview('merge')}
                style={{ fontSize: 11, padding: '3px 10px' }}>
                Adicionar ao filtro
              </button>
              <button className="o-btn o-btn-sm" onClick={() => applyFilterPreview('replace')}
                style={{ fontSize: 11, padding: '3px 10px' }}>
                Substituir campos do filtro
              </button>
              <button className="o-btn o-btn-sm" onClick={() => setFilterPreview(null)}
                style={{ fontSize: 11, padding: '3px 10px' }}>
                Descartar
              </button>
            </div>
          </div>
        )}

        {isPassive && (
          <div style={{
            padding: '8px 12px', marginBottom: 12, borderRadius: 5,
            background: 'color-mix(in srgb, var(--o-purple) 8%, transparent)',
            fontSize: 11, color: 'var(--o-sub)',
          }}>
            {group === 'f3'
              ? '⚡ Modo passivo · Campos com pergunta de fechamento configurada a exibirão abaixo.'
              : '○ Modo passivo · O agente capta passivamente — sem perguntar. Use o hint de captura.'}
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {groupFields.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--o-dim)', padding: '12px 0', textAlign: 'center' }}>
              Nenhum campo neste filtro. Clique em "Adicionar" para começar.
            </div>
          )}
          {groupFields.map((f, i) => (
            <div
              key={f.key}
              style={{
                display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px',
                background: f.mode === 'off' ? 'transparent' : 'var(--o-b1)',
                border: '1px solid var(--o-b2)', borderRadius: 6,
                opacity: f.mode === 'off' ? 0.5 : 1,
              }}
            >
              <span className="font-mono-orion" style={{ fontSize: 10, color: 'var(--o-dim)', paddingTop: 3, minWidth: 20, flexShrink: 0 }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12.5, color: 'var(--o-text)', fontWeight: 500 }}>{f.label}</div>
                {isPassive
                  ? <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 3 }}>
                      {group === 'f3' && f.allow_closing_question && f.closing_question
                        ? <><span style={{ color: 'var(--o-purple)' }}>⚡</span> {f.closing_question}</>
                        : f.passive_hint ? `○ ${f.passive_hint}` : '—'
                      }
                    </div>
                  : f.question && <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 3 }}>"{f.question}"</div>
                }
              </div>
              <ModeBadge mode={f.mode} passive={isPassive} onClick={() => handleCycleMode(f.key)} />
              <button
                onClick={() => setEditingField(f)}
                style={{ background: 'transparent', border: 'none', color: 'var(--o-sub)', cursor: 'pointer', padding: '2px 4px', fontSize: 14, flexShrink: 0 }}
                title="Editar campo"
              >›</button>
            </div>
          ))}
        </div>
        <button className="o-q-add" style={{ marginTop: 12 }} onClick={onAddField}>＋ Adicionar campo ao {titles[group]}</button>
      </ModalBase>

      {editingField && (
        <DrawerCampo
          field={editingField}
          isSdr={true}
          onClose={() => setEditingField(null)}
          onSave={handleSaveField}
          onRemove={editingField.key.startsWith('custom_') ? () => handleRemoveField(editingField.key) : undefined}
        />
      )}
    </>
  );
}

// ─── 4.3 — Lista plana (agentes não-SDR) ─────────────────────

function SecaoCamposPlana({ fields, responseStyle, agentMode, onUpdate }: {
  fields: QualificationField[];
  responseStyle: 'active' | 'passive';
  agentMode: string;
  onUpdate: (fields: QualificationField[]) => void;
}) {
  const [editingField, setEditingField] = useState<QualificationField | null>(null);

  const modeDescriptions: Record<string, string> = {
    agenda: 'Foco em agendar. Disponibilidade é o campo essencial.',
    closer: 'Filtro rápido. Menos campos, mais conversão.',
    direto: 'Filtro rápido. Menos campos, mais conversão.',
    consultivo: 'Atendimento consultivo. Campos revelam contexto e urgência.',
  };

  function handleCycleMode(key: string) {
    onUpdate(fields.map(f => f.key === key ? { ...f, mode: cycleMode(f.mode) } : f));
  }

  function handleSaveField(updated: QualificationField) {
    onUpdate(fields.map(f => f.key === updated.key ? updated : f));
    setEditingField(null);
  }

  function handleRemoveField(key: string) {
    onUpdate(fields.filter(f => f.key !== key));
    setEditingField(null);
  }

  const isPassive = responseStyle === 'passive';
  const headerLabel = isPassive ? 'O que o agente precisa saber' : 'O que o agente deve descobrir';
  const headerSub = isPassive
    ? 'O agente não pergunta diretamente — capta naturalmente.'
    : modeDescriptions[agentMode] ?? '';

  return (
    <>
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          {headerLabel}
        </span>
        <span className="font-mono-orion" style={{ fontSize: 8, color: 'var(--o-dim)', border: '1px solid var(--o-b1)', padding: '1px 6px', borderRadius: 2 }}>
          {fields.filter(f => f.mode !== 'off').length} campo(s) ativo(s)
        </span>
      </div>

      {headerSub && (
        <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginBottom: 12, paddingLeft: 2 }}>{headerSub}</div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 24 }}>
        {fields.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--o-dim)', padding: '12px 0', textAlign: 'center' }}>
            Nenhum campo configurado. Clique em "Adicionar campo" para começar.
          </div>
        )}
        {fields.map(f => (
          <div
            key={f.key}
            style={{
              display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 14px',
              background: f.mode === 'off' ? 'transparent' : 'var(--o-b1)',
              border: '1px solid var(--o-b2)', borderRadius: 6,
              opacity: f.mode === 'off' ? 0.5 : 1,
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, color: 'var(--o-text)', fontWeight: 500 }}>{f.label}</div>
              {isPassive
                ? <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 3 }}>
                    {f.allow_closing_question && f.closing_question
                      ? <><span style={{ color: 'var(--o-purple)' }}>⚡</span> {f.closing_question}</>
                      : f.passive_hint ? `○ ${f.passive_hint}` : '—'
                    }
                  </div>
                : f.question && <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 3 }}>"{f.question}"</div>
              }
            </div>
            <ModeBadge mode={f.mode} passive={isPassive} onClick={() => handleCycleMode(f.key)} />
            <button
              onClick={() => setEditingField(f)}
              style={{ background: 'transparent', border: 'none', color: 'var(--o-sub)', cursor: 'pointer', padding: '2px 4px', fontSize: 14, flexShrink: 0 }}
              title="Editar campo"
            >›</button>
          </div>
        ))}

        <button className="o-q-add" onClick={() => {
          const key = `custom_novo_${Date.now()}`;
          const newField: QualificationField = { key, label: '', mode: 'optional' };
          setEditingField(newField);
        }}>＋ Adicionar campo</button>
      </div>

      {editingField && (
        <DrawerCampo
          field={editingField}
          isSdr={false}
          onClose={() => setEditingField(null)}
          onSave={(updated) => {
            const existing = fields.find(f => f.key === updated.key);
            if (existing) {
              handleSaveField(updated);
            } else {
              // new custom field — fix key from label
              const finalKey = updated.label.trim()
                ? `custom_${slugify(updated.label)}`
                : updated.key;
              // ensure key uniqueness
              const usedKeys = new Set(fields.map(f => f.key));
              let k = finalKey;
              let n = 2;
              while (usedKeys.has(k)) k = `${finalKey}_${n++}`;
              onUpdate([...fields, { ...updated, key: k }]);
              setEditingField(null);
            }
          }}
          onRemove={editingField.key.startsWith('custom_') ? () => handleRemoveField(editingField.key) : undefined}
        />
      )}
    </>
  );
}

// ─── Drawers simples ──────────────────────────────────────────

function DrawerTexto({ title, sub, value, placeholder, maxLen, onSave, onClose }: {
  title: string; sub: string; value: string; placeholder?: string; maxLen?: number;
  onSave: (v: string) => void; onClose: () => void;
}) {
  const [local, setLocal] = useState(value);
  const max = maxLen ?? 300;
  return (
    <DrawerBase title={title} sub={sub} onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <SuggestTextarea className="o-textarea" value={local} maxLength={max} placeholder={placeholder} onChange={e => setLocal(e.target.value)} />
        <div className="o-char-count">{local.length}/{max}</div>
      </div>
    </DrawerBase>
  );
}

function DrawerTicket({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const opts = ['Até R$ 500', 'R$ 500 – R$ 2.000', 'R$ 2.000 – R$ 10.000', 'R$ 10.000 – R$ 50.000', 'Acima de R$ 50.000'];
  return (
    <DrawerBase title="Ticket médio" sub="Valor aproximado por venda ou contrato" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Faixa de valor</label>
        <select className="o-select" value={local} onChange={e => setLocal(e.target.value)}>
          {opts.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    </DrawerBase>
  );
}

function DrawerScore({ value, onSave, onClose }: { value: number; onSave: (v: number) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  return (
    <DrawerBase title="Score mínimo de qualificação" sub="Lead precisa atingir esta pontuação para avançar no pipeline" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Score mínimo (0–12)</label>
        <div className="o-field-hint">Leads abaixo desta pontuação são descartados ou encaminhados para nurture. Cada campo qualificado vale 1 ponto.</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
          <input
            type="range" className="o-slider"
            min={0} max={12} step={1} value={local}
            onChange={e => setLocal(Number(e.target.value))}
          />
          <span className="font-mono-orion" style={{ fontSize: 14, color: 'var(--o-text)', minWidth: 28, textAlign: 'right' }}>{local}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--o-dim)', marginTop: 4 }}>
          <span>0 (sem filtro)</span>
          <span>6 (padrão)</span>
          <span>12 (máximo)</span>
        </div>
      </div>
    </DrawerBase>
  );
}

function ModalBuyingSignals({ keywords, onSave, onClose }: {
  keywords: string[]; onSave: (v: string[]) => void; onClose: () => void;
}) {
  const [local, setLocal] = useState<string[]>([...keywords]);
  const [input, setInput] = useState('');

  function addKw() {
    const v = input.trim();
    if (v && !local.includes(v)) setLocal(prev => [...prev, v]);
    setInput('');
  }
  function rmKw(kw: string) { setLocal(prev => prev.filter(k => k !== kw)); }
  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addKw(); }
  }

  return (
    <ModalBase title="Sinais de compra" sub="Palavras-chave que indicam intenção de compra do lead" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Palavras ou frases de interesse</label>
        <div className="o-field-hint">Ex: "quero comprar", "quanto custa", "quero agendar". Pressione Enter para adicionar.</div>
        <div className="o-tag-wrap" onClick={() => document.getElementById('bs-input')?.focus()}>
          {local.map(kw => (
            <span key={kw} className="o-kw-tag">
              {kw}
              <button onClick={() => rmKw(kw)}>×</button>
            </span>
          ))}
          <input
            id="bs-input"
            className="o-tag-input"
            placeholder="Adicionar sinal…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={addKw}
          />
        </div>
      </div>
    </ModalBase>
  );
}

// ─── Drawer: nova adição de campo SDR (com escolha de filtro) ──

function ModalAddCampoSDR({ fields, onAdd, onClose }: {
  fields: QualificationField[];
  onAdd: (f: QualificationField) => void;
  onClose: () => void;
}) {
  const [label, setLabel] = useState('');
  const [question, setQuestion] = useState('');
  const [passiveHint, setPassiveHint] = useState('');
  const [group, setGroup] = useState<'f1' | 'f2' | 'f3'>('f1');
  const [mode, setMode] = useState<QualificationField['mode']>('optional');

  function handleAdd() {
    if (!label.trim()) return;
    const baseKey = `custom_${slugify(label)}`;
    const usedKeys = new Set(fields.map(f => f.key));
    let k = baseKey;
    let n = 2;
    while (usedKeys.has(k)) k = `${baseKey}_${n++}`;
    onAdd({ key: k, label: label.trim(), question, passive_hint: passiveHint, mode, group });
  }

  return (
    <ModalBase title="Adicionar campo" sub="Campo personalizado para este perfil de agente" onClose={onClose} onSave={handleAdd}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div className="o-field">
          <label className="o-field-label">Nome do campo *</label>
          <SuggestInput className="o-input" value={label} onChange={e => setLabel(e.target.value)} placeholder="Ex: Nome do pet" />
        </div>
        <div className="o-field">
          <label className="o-field-label">Filtro (SDR)</label>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            {(['f1', 'f2', 'f3'] as const).map(g => (
              <button
                key={g}
                onClick={() => setGroup(g)}
                style={{
                  flex: 1, padding: '7px 0', borderRadius: 5, border: '1px solid',
                  cursor: 'pointer', fontSize: 11.5, fontWeight: 500,
                  borderColor: group === g ? 'var(--o-purple)' : 'var(--o-b2)',
                  background: group === g ? 'color-mix(in srgb, var(--o-purple) 15%, transparent)' : 'transparent',
                  color: group === g ? 'var(--o-purple)' : 'var(--o-sub)',
                }}
              >
                {g === 'f1' ? 'F1 · Fit' : g === 'f2' ? 'F2 · Dor' : 'F3 · Fechamento'}
              </button>
            ))}
          </div>
        </div>
        <div className="o-field">
          <label className="o-field-label">Importância</label>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            {(['required', 'optional', 'off'] as const).map(m => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{
                  flex: 1, padding: '7px 0', borderRadius: 5, border: '1px solid',
                  cursor: 'pointer', fontSize: 11, fontWeight: 500,
                  borderColor: mode === m ? 'var(--o-purple)' : 'var(--o-b2)',
                  background: mode === m ? 'color-mix(in srgb, var(--o-purple) 15%, transparent)' : 'transparent',
                  color: mode === m ? 'var(--o-purple)' : 'var(--o-sub)',
                }}
              >
                {m === 'required' ? '● Obrigatório' : m === 'optional' ? '○ Opcional' : '× Desligado'}
              </button>
            ))}
          </div>
        </div>
        <div className="o-field">
          <label className="o-field-label">Pergunta (modo ativo)</label>
          <SuggestInput className="o-input" value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ex: Qual o nome do seu pet?" />
        </div>
        <div className="o-field">
          <label className="o-field-label">Como capturar passivamente</label>
          <SuggestInput className="o-input" value={passiveHint} onChange={e => setPassiveHint(e.target.value)} placeholder="Ex: Capturar se lead mencionar nome de animal" />
        </div>
      </div>
    </ModalBase>
  );
}

// ─────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────

type DrawerKey = 'produto' | 'ticket' | 'publico' | 'dor' | 'objecao' | 'score' | null;
type ModalKey  = 'f1' | 'f2' | 'f3' | 'buying_signals' | 'add_campo_sdr' | null;

type GeneratePreview = {
  fields: QualificationField[];
  explanation: string;
} | null;

export function CamadaQualificacao({ config, onUpdate }: CamadaQualificacaoProps) {
  const [drawer, setDrawer] = useState<DrawerKey>(null);
  const [modal, setModal]   = useState<ModalKey>(null);
  // Banner de sugestão por agent_mode
  const [bannerMode, setBannerMode] = useState<string | null>(null);
  const prevModeRef = useRef(config.agent_mode);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatePreview, setGeneratePreview] = useState<GeneratePreview>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);

  useEffect(() => {
    if (prevModeRef.current !== config.agent_mode) {
      setBannerMode(config.agent_mode);
      prevModeRef.current = config.agent_mode;
    }
  }, [config.agent_mode]);

  const isSdr = config.agent_mode === 'sdr_scheduler';
  const showBuyingSignals = config.agent_mode === 'sdr_scheduler' || config.agent_mode === 'agenda'
    || config.template_key === 'sdr_padrao' || config.template_key === 'hybrid_scheduler';

  // Salvar qualification_fields + derivados
  function updateFields(fields: QualificationField[]) {
    const derived = deriveF1F2F3(fields);
    onUpdate({ qualification_fields: fields, ...derived });
  }

  // Aplicar sugestão
  function applySuggestion(mode: string) {
    const suggested = SUGGESTIONS[mode] ?? [];
    updateFields(suggested);
    setBannerMode(null);
  }

  async function handleGenerate() {
    setIsGenerating(true);
    setGenerateError(null);
    try {
      const result = await api.agente.generateQualificationFields();
      setGeneratePreview(result);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro ao gerar campos';
      setGenerateError(msg);
    } finally {
      setIsGenerating(false);
    }
  }

  function applyGeneratedFields(mode: 'replace' | 'merge', editedFields: QualificationField[]) {
    if (mode === 'replace') {
      updateFields(editedFields);
    } else {
      const existingKeys = new Set(config.qualification_fields.map(f => f.key));
      const newFields = editedFields.filter(f => !existingKeys.has(f.key));
      updateFields([...config.qualification_fields, ...newFields]);
    }
    setGeneratePreview(null);
  }

  // Adicionar campo SDR
  function handleAddCampoSDR(f: QualificationField) {
    updateFields([...config.qualification_fields, f]);
    setModal(null);
  }

  // Adicionar campo a grupo específico (a partir do modal do filtro SDR)
  function handleAddToGroup(group: 'f1' | 'f2' | 'f3') {
    setModal(group);
  }

  const f1Count = config.qualification_fields.filter(f => f.group === 'f1' && f.mode !== 'off').length;
  const f2Count = config.qualification_fields.filter(f => f.group === 'f2' && f.mode !== 'off').length;
  const f3Count = config.qualification_fields.filter(f => f.group === 'f3' && f.mode !== 'off').length;
  const isPassive = config.response_style === 'passive';

  return (
    <>
      {/* 4.1 — Toggle response_style */}
      <ToggleResponseStyle
        value={config.response_style}
        onChange={v => onUpdate({ response_style: v })}
      />

      {/* Contexto do negócio */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Contexto do negócio
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard label="Produto ou serviço" value={config.offer_description || '—'} sub="O que você vende em uma frase" onClick={() => setDrawer('produto')} help="Descreva o produto ou serviço em 1–2 frases. Quanto mais detalhado, melhor o agente contextualiza a oferta nas conversas." />
        <EditCard label="Ticket médio"       value={config.ticket_range || '—'}      sub="Valor por venda ou contrato"     onClick={() => setDrawer('ticket')} help="Faixa de preço do produto. Ajuda o agente a calibrar o tom — produtos de alto ticket exigem mais confiança e qualificação antes da oferta." />
        <EditCard label="Cliente ideal"      value={config.target_audience || '—'}   sub="Perfil e situação de vida"        onClick={() => setDrawer('publico')} help="Perfil do cliente ideal (persona). Usado para que o agente identifique leads alinhados e filtre os que não têm fit com a oferta." />
        <EditCard label="Principal dor"      value={config.main_pain || '—'}          sub="Problema antes de te contratar"  onClick={() => setDrawer('dor')} help="Principal dor ou problema que seu produto resolve. O agente usa isso para criar conexão emocional e aumentar relevância na conversa." />
        <EditCard label="Objeção mais comum" value={config.main_objection || '—'}     sub="O que o lead fala ao não comprar" onClick={() => setDrawer('objecao')} help="Objeção mais frequente antes da compra (ex: está caro, preciso pensar). O agente aprende a tratar esta objeção com antecedência." />
      </div>

      {/* 4.6 — Banner de sugestão */}
      {bannerMode && (
        <BannerSugestao
          mode={bannerMode}
          onApply={() => applySuggestion(bannerMode)}
          onDismiss={() => setBannerMode(null)}
        />
      )}

      {/* 4.2 — Filtros SDR  |  4.3 — Lista plana outros agentes */}
      {isSdr ? (
        <>
          <div className="o-section-hdr">
            <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
              Filtros de qualificação
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="font-mono-orion" style={{ fontSize: 8, color: 'var(--o-dim)', border: '1px solid var(--o-b1)', padding: '1px 6px', borderRadius: 2 }}>
                {f1Count + f2Count + f3Count} campos ativos
              </span>
              <button
                className="o-btn o-btn-sm"
                onClick={handleGenerate}
                disabled={isGenerating}
                style={{ fontSize: 10, padding: '2px 8px', opacity: isGenerating ? 0.6 : 1 }}
              >
                {isGenerating ? '...' : '✦ Gerar com IA'}
              </button>
            </div>
          </div>
          {generateError && (
            <div style={{ fontSize: 11, color: 'var(--o-error, #f87171)', marginBottom: 8, paddingLeft: 2 }}>
              {generateError}
            </div>
          )}
          {isPassive && (
            <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginBottom: 12, paddingLeft: 2 }}>
              Modo passivo · O agente capta naturalmente; apenas perguntas de fechamento (F3) são permitidas.
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
            <FiltroCard
              label={isPassive ? 'F1 · Fit e Perfil' : 'Filtro 1 · Perfil e fit'}
              count={f1Count}
              sub={isPassive ? 'indícios de fit captados passivamente' : 'Localização · uso pessoal · decisor'}
              onClick={() => setModal('f1')}
              help="Perguntas binárias que validam se o lead está dentro do público-alvo (localização, decisor, uso). Fase inicial de triagem — elimina leads sem fit antes de gastar mais tempo."
            />
            <FiltroCard
              label={isPassive ? 'F2 · Intenção e Dor' : 'Filtro 2 · Intenção e dor'}
              count={f2Count}
              sub={isPassive ? 'sinais de dor captados sem perguntar' : 'Abertas · exploratórias · contexto'}
              onClick={() => setModal('f2')}
              help="Perguntas abertas para revelar contexto, urgência e a dor do lead. Avança leads com intenção clara e dor identificada para a fase de fechamento."
            />
            <FiltroCard
              label={isPassive ? 'F3 · 4Ps · Fechamento' : 'Filtro 3 · 4Ps'}
              count={f3Count}
              sub={isPassive ? '⚡ confirmações e perguntas de fechamento' : 'Poder · prioridade · preço · timing'}
              onClick={() => setModal('f3')}
              highlight={isPassive}
              help="Qualificação profunda via os 4Ps: Problema, Prioridade, Poder de compra e Prazo. No modo passivo, apenas perguntas estratégicas de fechamento (alternativas binárias) são permitidas aqui."
            />
          </div>
        </>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
            <button
              className="o-btn o-btn-sm"
              onClick={handleGenerate}
              disabled={isGenerating}
              style={{ fontSize: 10, padding: '2px 8px', opacity: isGenerating ? 0.6 : 1 }}
            >
              {isGenerating ? '...' : '✦ Gerar com IA'}
            </button>
          </div>
          {generateError && (
            <div style={{ fontSize: 11, color: 'var(--o-error, #f87171)', marginBottom: 8, paddingLeft: 2 }}>
              {generateError}
            </div>
          )}
          <SecaoCamposPlana
            fields={config.qualification_fields}
            responseStyle={config.response_style}
            agentMode={config.agent_mode}
            onUpdate={updateFields}
          />
        </>
      )}

      {/* Parâmetros avançados */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Parâmetros avançados
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Score mínimo"
          value={`${config.qualification_score_threshold} / 12`}
          sub="Pontuação para avançar no pipeline"
          onClick={() => setDrawer('score')}
          help="Pontuação mínima para o lead avançar no pipeline. Cada campo de qualificação respondido vale 1 ponto. Leads abaixo são descartados ou enviados para nurture."
        />
        <div className="o-edit-card" onClick={() => onUpdate({ nurture_vs_discard_rule: !config.nurture_vs_discard_rule })}>
          <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6, display: 'flex', alignItems: 'center' }}>Nurture vs Descarte <FieldHelp text="Leads abaixo do score mínimo: Nurture — continua recebendo conteúdo e pode avançar depois; Descarte — arquivado imediatamente." /></div>
          <div style={{ fontSize: 13, color: 'var(--o-text)', marginBottom: 4 }}>{config.nurture_vs_discard_rule ? 'Nurture passivo' : 'Descarte imediato'}</div>
          <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 8 }}>Lead abaixo do score</div>
          <span className={`o-badge ${config.nurture_vs_discard_rule ? 'o-badge-ok' : 'o-badge-warn'}`}>
            {config.nurture_vs_discard_rule ? 'Nurture ativo' : 'Descarte'}
          </span>
          <span className="o-edit-arrow">›</span>
        </div>
        {showBuyingSignals && (
          <EditCard
            label="Sinais de compra"
            value={config.buying_signal_keywords.length > 0 ? `${config.buying_signal_keywords.length} sinal(is)` : 'Não configurado'}
            sub="Palavras que indicam intenção de compra"
            onClick={() => setModal('buying_signals')}
            help="Palavras ou frases que indicam intenção de compra do lead (ex: quanto custa, quero contratar, já decidi). Ao detectá-las, o agente acelera o funil automaticamente."
          />
        )}
      </div>

      {/* Drawers de contexto de negócio */}
      {drawer === 'produto' && (
        <DrawerTexto title="Produto ou serviço" sub="Descreva em 1–2 frases o que você vende" value={config.offer_description}
          placeholder="Ex: Pacotes de procedimentos estéticos corporais" onClose={() => setDrawer(null)} onSave={v => { onUpdate({ offer_description: v }); setDrawer(null); }} />
      )}
      {drawer === 'ticket' && (
        <DrawerTicket value={config.ticket_range} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ ticket_range: v }); setDrawer(null); }} />
      )}
      {drawer === 'publico' && (
        <DrawerTexto title="Cliente ideal" sub="Perfil, cargo, situação de vida ou tamanho de empresa" value={config.target_audience}
          placeholder="Ex: Mulheres 30–55 anos, renda acima de R$5k" onClose={() => setDrawer(null)} onSave={v => { onUpdate({ target_audience: v }); setDrawer(null); }} />
      )}
      {drawer === 'dor' && (
        <DrawerTexto title="Principal dor" sub="O problema central que o cliente tem antes de te contratar" value={config.main_pain}
          placeholder="Ex: Flacidez pós-gestação" onClose={() => setDrawer(null)} onSave={v => { onUpdate({ main_pain: v }); setDrawer(null); }} />
      )}
      {drawer === 'objecao' && (
        <DrawerTexto title="Objeção mais comum" sub="O que o lead fala quando não compra imediatamente" value={config.main_objection}
          placeholder='Ex: "está caro", "vou pensar"…' maxLen={200} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ main_objection: v }); setDrawer(null); }} />
      )}
      {drawer === 'score' && (
        <DrawerScore value={config.qualification_score_threshold} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ qualification_score_threshold: v }); setDrawer(null); }} />
      )}

      {/* Modais SDR */}
      {(modal === 'f1' || modal === 'f2' || modal === 'f3') && (
        <ModalFiltroSDR
          group={modal}
          responseStyle={config.response_style}
          fields={config.qualification_fields}
          onUpdate={updateFields}
          onClose={() => setModal(null)}
          onAddField={() => {
            // abre modal de adição com grupo pré-selecionado
            setModal('add_campo_sdr');
          }}
        />
      )}
      {modal === 'add_campo_sdr' && (
        <ModalAddCampoSDR
          fields={config.qualification_fields}
          onAdd={handleAddCampoSDR}
          onClose={() => setModal(null)}
        />
      )}
      {modal === 'buying_signals' && (
        <ModalBuyingSignals
          keywords={config.buying_signal_keywords}
          onClose={() => setModal(null)}
          onSave={v => { onUpdate({ buying_signal_keywords: v }); setModal(null); }}
        />
      )}

      {generatePreview && (
        <DrawerGerarCampos
          preview={generatePreview}
          isSdr={isSdr}
          onReplace={(fields) => applyGeneratedFields('replace', fields)}
          onMerge={(fields) => applyGeneratedFields('merge', fields)}
          onClose={() => setGeneratePreview(null)}
        />
      )}
    </>
  );
}

// ─── Componentes internos ─────────────────────────────────────

function EditCard({ label, value, sub, onClick, help }: { label: string; value: string; sub: string; onClick: () => void; help?: string }) {
  return (
    <div className="o-edit-card" onClick={onClick}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6, display: 'flex', alignItems: 'center' }}>{label}{help && <FieldHelp text={help} />}</div>
      <div style={{ fontSize: 13, color: 'var(--o-text)', marginBottom: 4 }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300 }}>{sub}</div>
      <span className="o-edit-arrow">›</span>
    </div>
  );
}

function FiltroCard({ label, count, sub, onClick, highlight, help }: {
  label: string; count: number; sub: string; onClick: () => void; highlight?: boolean; help?: string;
}) {
  const hasFields = count > 0;
  return (
    <div className="o-edit-card" onClick={onClick} style={highlight ? { borderColor: 'color-mix(in srgb, var(--o-purple) 40%, transparent)' } : undefined}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: highlight ? 'var(--o-purple)' : 'var(--o-dim)', marginBottom: 6, display: 'flex', alignItems: 'center' }}>{label}{help && <FieldHelp text={help} />}</div>
      <div style={{ fontSize: 13, color: 'var(--o-text)', marginBottom: 4 }}>
        {count === 0 ? 'Sem campos' : `${count} campo${count !== 1 ? 's' : ''} ativo${count !== 1 ? 's' : ''}`}
      </div>
      <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 8 }}>{sub}</div>
      <span className={`o-badge ${hasFields ? 'o-badge-ok' : 'o-badge-warn'}`}>
        {hasFields ? 'Editar campos' : 'Adicionar campos'}
      </span>
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

function ModalBase({ title, sub, onClose, onSave, children, disableBackdropClose }: {
  title: string; sub: string; onClose: () => void; onSave: () => void;
  children: React.ReactNode; disableBackdropClose?: boolean;
}) {
  return (
    <div className="o-modal-overlay open" onClick={e => { if (!disableBackdropClose && e.target === e.currentTarget) onClose(); }}>
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

// ─── DrawerGerarCampos ────────────────────────────────────────

const GROUP_LABELS: Record<string, string> = {
  f1: 'F1 · Perfil e Fit',
  f2: 'F2 · Intenção e Dor',
  f3: 'F3 · 4Ps',
};

function DrawerGerarCampos({
  preview,
  isSdr,
  onReplace,
  onMerge,
  onClose,
}: {
  preview: { fields: QualificationField[]; explanation: string };
  isSdr: boolean;
  onReplace: (fields: QualificationField[]) => void;
  onMerge: (fields: QualificationField[]) => void;
  onClose: () => void;
}) {
  const [editableFields, setEditableFields] = useState<QualificationField[]>(preview.fields);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<QualificationField | null>(null);
  const [isGeneratingMore, setIsGeneratingMore] = useState(false);
  const [generateMoreError, setGenerateMoreError] = useState<string | null>(null);

  const groups = isSdr ? (['f1', 'f2', 'f3'] as const) : null;

  function startEdit(f: QualificationField) {
    setEditingKey(f.key);
    setEditDraft({ ...f });
  }

  function cancelEdit() {
    if (editDraft && !editDraft.label.trim()) {
      setEditableFields(prev => prev.filter(f => f.key !== editDraft.key));
    }
    setEditingKey(null);
    setEditDraft(null);
  }

  function saveEdit() {
    if (!editDraft || !editDraft.label.trim()) return;
    setEditableFields(prev => prev.map(f => f.key === editDraft.key ? { ...editDraft } : f));
    setEditingKey(null);
    setEditDraft(null);
  }

  function removeField(key: string) {
    setEditableFields(prev => prev.filter(f => f.key !== key));
    if (editingKey === key) {
      setEditingKey(null);
      setEditDraft(null);
    }
  }

  function addBlankField(group?: 'f1' | 'f2' | 'f3') {
    const newKey = `custom_${Date.now()}`;
    const blank: QualificationField = { key: newKey, label: '', question: '', passive_hint: '', mode: 'required', group };
    setEditableFields(prev => [...prev, blank]);
    setEditingKey(newKey);
    setEditDraft({ ...blank });
  }

  async function handleGenerateMore() {
    setIsGeneratingMore(true);
    setGenerateMoreError(null);
    try {
      const result = await api.agente.generateQualificationFields();
      const existingKeys = new Set(editableFields.map(f => f.key));
      const newFields = result.fields.filter(f => !existingKeys.has(f.key));
      setEditableFields(prev => [...prev, ...newFields]);
    } catch (err: unknown) {
      setGenerateMoreError(err instanceof Error ? err.message : 'Erro ao gerar mais campos');
    } finally {
      setIsGeneratingMore(false);
    }
  }

  function renderField(f: QualificationField) {
    const isEditing = editingKey === f.key && editDraft;

    if (isEditing) {
      return (
        <div key={f.key} style={{ padding: '10px 12px', background: 'var(--o-b1)', borderRadius: 6, marginBottom: 8, border: '1px solid color-mix(in srgb, var(--o-purple, #7c3aed) 50%, transparent)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--o-dim)', marginBottom: 3 }}>Label</div>
              <input
                className="o-input"
                value={editDraft.label}
                onChange={e => setEditDraft(d => d ? { ...d, label: e.target.value } : d)}
                placeholder="Ex: Faturamento Anual"
                style={{ width: '100%', fontSize: 12 }}
                autoFocus
              />
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--o-dim)', marginBottom: 3 }}>Pergunta</div>
              <textarea
                className="o-input"
                value={editDraft.question ?? ''}
                onChange={e => setEditDraft(d => d ? { ...d, question: e.target.value } : d)}
                placeholder="Ex: Qual é o faturamento anual da empresa?"
                rows={2}
                style={{ width: '100%', fontSize: 12, resize: 'vertical' }}
              />
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--o-dim)', marginBottom: 3 }}>Capturar passivamente</div>
              <input
                className="o-input"
                value={editDraft.passive_hint ?? ''}
                onChange={e => setEditDraft(d => d ? { ...d, passive_hint: e.target.value } : d)}
                placeholder="Ex: Se o lead mencionar valores de faturamento"
                style={{ width: '100%', fontSize: 12 }}
              />
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: 10, color: 'var(--o-dim)', marginBottom: 3 }}>Modo</div>
                <select
                  className="o-input"
                  value={editDraft.mode}
                  onChange={e => setEditDraft(d => d ? { ...d, mode: e.target.value as 'required' | 'optional' } : d)}
                  style={{ fontSize: 12 }}
                >
                  <option value="required">Obrigatório</option>
                  <option value="optional">Opcional</option>
                </select>
              </div>
              {isSdr && (
                <div>
                  <div style={{ fontSize: 10, color: 'var(--o-dim)', marginBottom: 3 }}>Grupo</div>
                  <select
                    className="o-input"
                    value={editDraft.group ?? 'f1'}
                    onChange={e => setEditDraft(d => d ? { ...d, group: e.target.value as 'f1' | 'f2' | 'f3' } : d)}
                    style={{ fontSize: 12 }}
                  >
                    <option value="f1">F1 · Perfil e Fit</option>
                    <option value="f2">F2 · Intenção e Dor</option>
                    <option value="f3">F3 · 4Ps</option>
                  </select>
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="o-btn o-btn-primary o-btn-sm" onClick={saveEdit} disabled={!editDraft.label.trim()} style={{ fontSize: 11, padding: '3px 10px' }}>
                Salvar
              </button>
              <button className="o-btn o-btn-sm" onClick={cancelEdit} style={{ fontSize: 11, padding: '3px 10px' }}>
                Cancelar
              </button>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div key={f.key} style={{ padding: '10px 12px', background: 'var(--o-b1)', borderRadius: 6, marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: 'var(--o-text)', fontWeight: 500 }}>
              {f.label || <span style={{ color: 'var(--o-dim)' }}>Sem nome</span>}
            </span>
            <span className={`o-badge ${f.mode === 'required' ? 'o-badge-ok' : 'o-badge-warn'}`} style={{ fontSize: 9 }}>
              {f.mode === 'required' ? 'Obrigatório' : 'Opcional'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
            <button
              onClick={() => startEdit(f)}
              title="Editar"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--o-dim)', fontSize: 13, padding: '1px 5px', borderRadius: 3, lineHeight: 1 }}
            >✎</button>
            <button
              onClick={() => removeField(f.key)}
              title="Remover"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--o-dim)', fontSize: 13, padding: '1px 5px', borderRadius: 3, lineHeight: 1 }}
            >✕</button>
          </div>
        </div>
        {f.question && (
          <div style={{ fontSize: 11, color: 'var(--o-sub)', marginBottom: 2 }}>
            <span style={{ color: 'var(--o-dim)' }}>Pergunta:</span> {f.question}
          </div>
        )}
        {f.passive_hint && (
          <div style={{ fontSize: 11, color: 'var(--o-sub)' }}>
            <span style={{ color: 'var(--o-dim)' }}>Capturar:</span> {f.passive_hint}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="o-modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="o-modal" style={{ maxWidth: 560 }}>
        <div className="o-modal-header">
          <div>
            <div className="font-display" style={{ fontSize: 20, fontWeight: 400, color: 'var(--o-text)' }}>Campos gerados pela IA</div>
            <div style={{ fontSize: 12, color: 'var(--o-sub)', fontWeight: 300, marginTop: 3 }}>
              Revise e personalize antes de salvar
            </div>
          </div>
          <button className="o-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="o-modal-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
          {preview.explanation && (
            <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginBottom: 16, padding: '8px 12px', background: 'var(--o-b1)', borderRadius: 6, borderLeft: '2px solid var(--o-purple, #7c3aed)' }}>
              {preview.explanation}
            </div>
          )}

          {groups ? (
            groups.map(g => {
              const groupFields = editableFields.filter(f => f.group === g);
              return (
                <div key={g} style={{ marginBottom: 16 }}>
                  <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 8 }}>
                    {GROUP_LABELS[g]}
                  </div>
                  {groupFields.map(renderField)}
                  <button
                    className="o-btn o-btn-sm"
                    onClick={() => addBlankField(g)}
                    style={{ fontSize: 10, padding: '2px 8px', marginTop: 2 }}
                  >+ Adicionar campo</button>
                </div>
              );
            })
          ) : (
            <>
              {editableFields.map(renderField)}
              <button
                className="o-btn o-btn-sm"
                onClick={() => addBlankField()}
                style={{ fontSize: 10, padding: '2px 8px', marginTop: 4 }}
              >+ Adicionar campo</button>
            </>
          )}

          {editableFields.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--o-sub)', textAlign: 'center', padding: '16px 0' }}>
              Nenhum campo. Adicione manualmente ou gere com IA.
            </div>
          )}
        </div>

        {generateMoreError && (
          <div style={{ fontSize: 11, color: 'var(--o-error, #f87171)', padding: '4px 16px' }}>
            {generateMoreError}
          </div>
        )}

        <div className="o-modal-footer" style={{ justifyContent: 'space-between' }}>
          <button
            className="o-btn o-btn-sm"
            onClick={handleGenerateMore}
            disabled={isGeneratingMore}
            style={{ fontSize: 10, padding: '2px 8px', opacity: isGeneratingMore ? 0.6 : 1 }}
          >
            {isGeneratingMore ? '...' : '✦ Gerar mais com IA'}
          </button>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="o-btn o-btn-primary" onClick={() => onReplace(editableFields)}>Substituir todos</button>
            <button className="o-btn" onClick={() => onMerge(editableFields)}>Adicionar aos existentes</button>
            <button className="o-btn" onClick={onClose}>Cancelar</button>
          </div>
        </div>
      </div>
    </div>
  );
}
