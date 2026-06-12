/**
 * DebugAiProfile — Página de debug para testar a UI da Fase 4
 *
 * Fase 4 do plano-implementacao.md:
 *  - Toggle response_style (ativo/passivo) no topo
 *  - SDR: F1/F2/F3 com modo obrigatório/opcional/desligado por campo
 *  - Outros agentes: lista plana de QualificationField
 *  - Drawer de edição de campo (question + passive_hint + closing_question para F3)
 *  - Campos personalizados
 *  - Sugestão ao trocar de modo
 *  - Painel JSON do contrato derivado
 *
 * Sem chamadas de API — estado local React.
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
  /** Pergunta direta — usada exclusivamente no modo ativo. */
  question: string;
  /** Pista para capturar o dado sem perguntar — usado no modo passivo. */
  passive_hint: string;
  /**
   * Pergunta estratégica de fechamento — única pergunta permitida no modo passivo.
   * Reservada para confirmações e alternativas binárias (ex: "às 15h ou 16h?").
   * Configurável apenas em campos F3 ou campos marcados com allow_closing_question.
   */
  closing_question: string;
  /** Habilita closing_question para este campo no modo passivo. */
  allow_closing_question: boolean;
  mode: FieldMode;
  group?: FilterGroup; // apenas SDR
  is_custom?: boolean;
}

// ─── Constantes ───────────────────────────────────────────────

const AGENT_MODE_LABELS: Record<AgentMode, string> = {
  sdr_scheduler: 'A1 · SDR Alto Ticket',
  closer:        'A2 · Vendedor Autônomo',
  direto:        'A2 · Direto',
  agenda:        'A3 · Assistente + Agenda',
  consultivo:    'A3 · Consultivo',
};

const AGENT_MODE_DESC: Record<AgentMode, string> = {
  sdr_scheduler: 'Qualifica via F1→F2→F3 antes de agendar. Handoff com dossiê completo.',
  closer:        '100% automatizado. Qualifica em 1–2 perguntas → pitch → link de pagamento.',
  direto:        'Filtra rápido e fecha sem rodeios. Poucas perguntas, foco em converter.',
  agenda:        'Recepcionista comercial. Qualifica, aquece e agenda para o profissional.',
  consultivo:    'Aprofundamento antes de qualquer proposta. Entende contexto e dor real.',
};

const PREDEFINED_FIELDS: Omit<QualificationField, 'mode' | 'group' | 'allow_closing_question' | 'closing_question'>[] = [
  { key: 'service_interest',    label: 'Serviço de interesse',   question: 'O que você busca exatamente?',                     passive_hint: 'Capturar pelo serviço ou problema que o lead mencionar' },
  { key: 'availability_window', label: 'Disponibilidade',        question: 'Qual o melhor horário para você?',                  passive_hint: 'Capturar se lead mencionar horário, data ou "semana que vem"' },
  { key: 'price_acceptance',    label: 'Aceitação de preço',     question: 'O valor de R$ X funciona para você?',               passive_hint: 'Capturar se lead não questionar o preço após ser informado' },
  { key: 'location_preference', label: 'Preferência de local',   question: 'Você prefere presencial, online ou domicílio?',     passive_hint: 'Capturar se lead mencionar cidade, endereço ou "online"' },
  { key: 'urgency',             label: 'Urgência',               question: 'Isso é urgente para você ou pode esperar?',         passive_hint: 'Capturar se lead usar "urgente", "preciso logo", "esta semana"' },
  { key: 'decision_role',       label: 'Decisor',                question: 'A decisão é só sua ou envolve mais alguém?',        passive_hint: 'Capturar se lead disser "preciso consultar alguém" → não é decisor' },
  { key: 'budget_or_price_acceptance', label: 'Orçamento',       question: 'Qual faixa de investimento você tem em mente?',    passive_hint: 'Capturar se lead mencionar faixa ou comparar com concorrente' },
  { key: 'constraints',         label: 'Restrições',             question: 'Tem alguma limitação de horário, local ou outra?',  passive_hint: 'Capturar se lead mencionar restrições específicas' },
];

// Sugestões por modo — alinhadas ao pipeline de TiposAgentes.tsx
const SUGGESTIONS: Record<AgentMode, QualificationField[]> = {
  // A1: F1 (fit/perfil) → F2 (dor/intenção) → F3 (4Ps · fechamento)
  sdr_scheduler: [
    { key: 'service_interest',    label: 'Serviço de interesse',   question: 'Qual setor/produto você está avaliando?',    passive_hint: 'Capturar pelo problema ou produto citado',          closing_question: '', allow_closing_question: false, mode: 'required', group: 'f1' },
    { key: 'location_preference', label: 'Perfil de fit',          question: 'Vocês atuam em qual região/segmento?',       passive_hint: 'Capturar por setor ou localização mencionada',      closing_question: '', allow_closing_question: false, mode: 'required', group: 'f1' },
    { key: 'urgency',             label: 'Urgência',               question: 'Isso é uma prioridade agora ou futura?',    passive_hint: 'Capturar por prazo, evento ou "urgente" na fala',  closing_question: '', allow_closing_question: false, mode: 'required', group: 'f2' },
    { key: 'decision_role',       label: 'Decisor',                question: 'Quem participa da decisão além de você?',   passive_hint: 'Capturar se citar "meu sócio", "diretoria" etc.',  closing_question: '', allow_closing_question: false, mode: 'optional', group: 'f2' },
    { key: 'availability_window', label: 'Disponibilidade (timing)',question: 'Quando você precisa ter isso resolvido?',  passive_hint: 'Capturar por data, trimestre ou "o quanto antes"', closing_question: 'Você teria disponibilidade para uma conversa na quinta às 14h ou na sexta às 10h?', allow_closing_question: true, mode: 'required', group: 'f3' },
    { key: 'price_acceptance',    label: 'Orçamento / Preço',      question: 'Já definiram uma verba para isso?',          passive_hint: 'Capturar por comparação com preço ou confirmação', closing_question: 'Para avançarmos, consigo viabilizar o investimento de R$ X. Funciona para vocês?', allow_closing_question: true, mode: 'required', group: 'f3' },
  ],
  // A2 (closer): fit mínimo (1-2 perguntas) → pitch → link de pagamento
  closer: [
    { key: 'service_interest',    label: 'Confirmar interesse',    question: 'Você está buscando [solução] para [problema]?', passive_hint: 'Capturar pelo produto ou problema citado no clique/abordagem', closing_question: '', allow_closing_question: false, mode: 'required' },
    { key: 'price_acceptance',    label: 'Aceitação de preço',     question: 'O valor de R$ X funciona para você?',           passive_hint: 'Capturar se não questionar o preço após ser informado',       closing_question: 'O pagamento via Pix de R$ X agora funciona para você?', allow_closing_question: true, mode: 'required' },
  ],
  // A2 (direto): igual ao closer — flat list, foco em converter rápido
  direto: [
    { key: 'service_interest',    label: 'Confirmar interesse',    question: 'Você quer resolver [problema] agora?',          passive_hint: 'Capturar pelo interesse demonstrado no contato',              closing_question: '', allow_closing_question: false, mode: 'required' },
    { key: 'price_acceptance',    label: 'Aceitação de preço',     question: 'O valor de R$ X funciona?',                     passive_hint: 'Capturar se não questionar o preço',                          closing_question: 'Consigo garantir o desconto se fecharmos hoje. Fechamos?', allow_closing_question: true, mode: 'required' },
    { key: 'urgency',             label: 'Urgência',               question: 'Quando você precisa resolver isso?',            passive_hint: 'Capturar por prazo ou "o quanto antes"',                      closing_question: '', allow_closing_question: false, mode: 'optional' },
  ],
  // A3 (agenda): confirma fit → aprofunda dor → aquece → agenda
  agenda: [
    { key: 'service_interest',    label: 'O que está buscando',    question: 'O que te trouxe aqui hoje?',                    passive_hint: 'Capturar pelo problema ou objetivo que o lead mencionar',     closing_question: '', allow_closing_question: false, mode: 'required' },
    { key: 'availability_window', label: 'Disponibilidade',        question: 'Qual o melhor horário para a sua sessão?',      passive_hint: 'Capturar se lead mencionar data, hora ou "semana que vem"',  closing_question: 'Tenho disponibilidade na quinta às 14h ou na sexta às 10h — qual funciona melhor?', allow_closing_question: true, mode: 'required' },
    { key: 'urgency',             label: 'Contexto / dor',         question: 'Qual é o seu principal desafio hoje?',          passive_hint: 'Capturar na descrição livre do problema do lead',             closing_question: '', allow_closing_question: false, mode: 'optional' },
  ],
  // A3 (consultivo): aprofundamento → contexto → dor → timing → handoff
  consultivo: [
    { key: 'service_interest',    label: 'Objetivo central',       question: 'O que você quer alcançar com isso?',            passive_hint: 'Capturar pelo objetivo ou transformação desejada',            closing_question: '', allow_closing_question: false, mode: 'required' },
    { key: 'urgency',             label: 'Urgência',               question: 'Isso é uma prioridade agora ou futura?',       passive_hint: 'Capturar por prazo, evento ou "urgente"',                     closing_question: '', allow_closing_question: false, mode: 'required' },
    { key: 'decision_role',       label: 'Decisor',                question: 'Quem mais participa dessa decisão?',           passive_hint: 'Capturar se mencionar sócio, parceiro ou gestor',             closing_question: '', allow_closing_question: false, mode: 'optional' },
    { key: 'availability_window', label: 'Próximo passo / timing', question: 'Quando você quer dar o próximo passo?',        passive_hint: 'Capturar se lead mencionar data ou "o quanto antes"',         closing_question: 'Para darmos continuidade, que tal uma conversa de 30min na próxima semana?', allow_closing_question: true, mode: 'optional' },
  ],
};

const FILTER_LABELS: Record<FilterGroup, { title: string; sub: string; passiveSub: string }> = {
  f1: { title: 'F1 · Fit e Perfil',     sub: 'Validação binária — encaixe ou descarte imediato',  passiveSub: 'Indícios de fit detectados passivamente na conversa' },
  f2: { title: 'F2 · Intenção e Dor',   sub: 'Investigação — abertas · contexto · urgência',       passiveSub: 'Sinais de dor e intenção captados sem perguntar' },
  f3: { title: 'F3 · 4Ps · Fechamento', sub: 'Poder · Prioridade · Preço · Timing',                passiveSub: 'Confirmações e perguntas estratégicas de fechamento' },
};

const MODE_COLORS: Record<FieldMode, { bg: string; border: string; text: string; label: string }> = {
  required: { bg: 'color-mix(in srgb, var(--o-purple) 15%, transparent)', border: 'var(--o-purple)', text: 'var(--o-purple)', label: 'Obrigatório' },
  optional:  { bg: 'color-mix(in srgb, #22c55e 10%, transparent)',        border: '#22c55e',          text: '#22c55e',          label: 'Opcional'    },
  off:       { bg: 'var(--o-b1)',                                          border: 'transparent',      text: 'var(--o-dim)',     label: 'Desligado'   },
};

function buildInitialFields(mode: AgentMode): QualificationField[] {
  return SUGGESTIONS[mode];
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
  const isF3 = local.group === 'f3';

  // Campo pode ter closing_question se é F3 (SDR) ou se allow_closing_question foi habilitado
  const canHaveClosingQ = isSdr ? isF3 : local.allow_closing_question;

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
              {local.label || 'Novo campo'}
            </div>
          </div>
          <button className="o-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="o-drawer-body" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Nome do campo (só para custom) */}
          {local.is_custom && (
            <div className="o-field">
              <label className="o-field-label">Nome do campo</label>
              <input
                className="o-input"
                value={local.label}
                placeholder="Ex: Nome do pet, Região de interesse…"
                onChange={e => {
                  const label = e.target.value;
                  const key = 'custom_' + label.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
                  setLocal(v => ({ ...v, label, key }));
                }}
              />
              {local.key && (
                <div className="o-field-hint">
                  Chave: <span style={{ fontFamily: 'monospace', color: 'var(--o-purple)' }}>{local.key}</span>
                </div>
              )}
            </div>
          )}

          {/* Importância */}
          <div className="o-field">
            <label className="o-field-label">Importância no pipeline</label>
            <div className="o-field-hint" style={{ marginBottom: 8 }}>
              {local.mode === 'required' ? 'Lead não avança no Kanban sem este dado. Agente prioriza capturar.' :
               local.mode === 'optional'  ? 'Coletado se surgir. Não bloqueia avanço. Enriquece o contexto.' :
               'Ignorado pelo agente e pelo guardrail. Não afeta o pipeline.'}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['required', 'optional', 'off'] as FieldMode[]).map(m => {
                const c = MODE_COLORS[m];
                const active = local.mode === m;
                return (
                  <button key={m} onClick={() => setLocal(v => ({ ...v, mode: m }))}
                    style={{
                      flex: 1, padding: '8px 0', borderRadius: 6, cursor: 'pointer',
                      background: active ? c.bg : 'var(--o-b1)',
                      border: `1px solid ${active ? c.border : 'transparent'}`,
                      color: active ? c.text : 'var(--o-dim)',
                      fontSize: 11, fontWeight: active ? 600 : 400,
                    }}>
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
                  const labels: Record<FilterGroup, string> = { f1: 'F1 · Fit', f2: 'F2 · Dor', f3: 'F3 · Fechamento' };
                  return (
                    <button key={g} onClick={() => setLocal(v => ({ ...v, group: g, allow_closing_question: g === 'f3' ? v.allow_closing_question : false }))}
                      style={{
                        flex: 1, padding: '7px 0', borderRadius: 6, cursor: 'pointer',
                        background: active ? 'color-mix(in srgb, var(--o-purple) 12%, transparent)' : 'var(--o-b1)',
                        border: `1px solid ${active ? 'var(--o-purple)' : 'transparent'}`,
                        color: active ? 'var(--o-purple)' : 'var(--o-dim)',
                        fontSize: 11, fontWeight: active ? 600 : 400,
                      }}>
                      {labels[g]}
                    </button>
                  );
                })}
              </div>
              {isF3 && (
                <div style={{ marginTop: 8, fontSize: 11, color: 'var(--o-sub)', padding: '6px 10px', background: 'color-mix(in srgb, #f59e0b 8%, transparent)', borderRadius: 4, border: '1px solid color-mix(in srgb, #f59e0b 30%, transparent)' }}>
                  ⚡ Campos F3 podem ter uma pergunta estratégica de fechamento — a única pergunta permitida no modo passivo.
                </div>
              )}
            </div>
          )}

          {/* Para agentes não-SDR: toggle de closing_question */}
          {!isSdr && local.mode !== 'off' && (
            <div className="o-field">
              <div
                onClick={() => setLocal(v => ({ ...v, allow_closing_question: !v.allow_closing_question }))}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
                  background: 'var(--o-b1)', borderRadius: 6, cursor: 'pointer',
                }}>
                <div style={{
                  width: 36, height: 20, borderRadius: 10, flexShrink: 0, transition: 'background .2s',
                  background: local.allow_closing_question ? '#f59e0b' : 'var(--o-dim)', position: 'relative',
                }}>
                  <div style={{
                    position: 'absolute', top: 3,
                    left: local.allow_closing_question ? 18 : 3,
                    width: 14, height: 14, borderRadius: '50%', background: '#fff', transition: 'left .2s',
                  }} />
                </div>
                <div>
                  <div style={{ fontSize: 12.5, color: 'var(--o-text)', fontWeight: 500 }}>
                    Pergunta estratégica de fechamento
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 2 }}>
                    Permite uma pergunta de confirmação no modo passivo (ex: "às 15h ou 16h?")
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Divider entre modos */}
          <div style={{ height: 1, background: 'var(--o-b1)', margin: '0 -4px' }} />

          {/* MODO ATIVO: pergunta direta */}
          <div className="o-field">
            <label className="o-field-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              Pergunta direta
              <span style={{ fontSize: 9, letterSpacing: 1.5, padding: '1px 6px', borderRadius: 3, background: responseStyle === 'active' ? 'color-mix(in srgb, var(--o-purple) 15%, transparent)' : 'var(--o-b1)', color: responseStyle === 'active' ? 'var(--o-purple)' : 'var(--o-dim)', textTransform: 'uppercase', border: `1px solid ${responseStyle === 'active' ? 'var(--o-purple)' : 'transparent'}` }}>
                modo ativo
              </span>
            </label>
            <div className="o-field-hint">O agente pergunta proativamente quando este dado está em falta.</div>
            <textarea className="o-textarea" rows={2} value={local.question}
              placeholder="Ex: Qual o melhor horário para você?"
              style={{ opacity: responseStyle === 'passive' ? 0.45 : 1 }}
              onChange={e => setLocal(v => ({ ...v, question: e.target.value }))} />
          </div>

          {/* MODO PASSIVO: como capturar */}
          <div className="o-field">
            <label className="o-field-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              Como capturar passivamente
              <span style={{ fontSize: 9, letterSpacing: 1.5, padding: '1px 6px', borderRadius: 3, background: responseStyle === 'passive' ? 'color-mix(in srgb, #22c55e 10%, transparent)' : 'var(--o-b1)', color: responseStyle === 'passive' ? '#22c55e' : 'var(--o-dim)', textTransform: 'uppercase', border: `1px solid ${responseStyle === 'passive' ? '#22c55e' : 'transparent'}` }}>
                modo passivo
              </span>
            </label>
            <div className="o-field-hint">Agente não pergunta — mas detecta e registra se o lead mencionar este dado ao responder.</div>
            <textarea className="o-textarea" rows={2} value={local.passive_hint}
              placeholder='Ex: Capturar se lead mencionar "semana que vem", horário ou data'
              style={{ opacity: responseStyle === 'active' ? 0.45 : 1 }}
              onChange={e => setLocal(v => ({ ...v, passive_hint: e.target.value }))} />
          </div>

          {/* Pergunta estratégica de fechamento (F3 / allow_closing_question) */}
          {canHaveClosingQ && local.mode !== 'off' && (
            <div className="o-field" style={{ padding: '14px', background: 'color-mix(in srgb, #f59e0b 8%, transparent)', borderRadius: 8, border: '1px solid color-mix(in srgb, #f59e0b 30%, transparent)' }}>
              <label className="o-field-label" style={{ color: '#d97706', display: 'flex', alignItems: 'center', gap: 6 }}>
                ⚡ Pergunta estratégica de fechamento
                <span style={{ fontSize: 9, letterSpacing: 1.5, padding: '1px 6px', borderRadius: 3, background: 'color-mix(in srgb, #f59e0b 20%, transparent)', color: '#d97706', textTransform: 'uppercase', border: '1px solid color-mix(in srgb, #f59e0b 50%, transparent)' }}>
                  passivo · F3
                </span>
              </label>
              <div className="o-field-hint" style={{ color: 'var(--o-sub)' }}>
                Única pergunta permitida no modo passivo. Use alternativas binárias ou confirmações — nunca perguntas de descoberta.
              </div>
              <textarea className="o-textarea" rows={2} value={local.closing_question}
                placeholder='Ex: "Tenho disponibilidade na quinta às 14h ou na sexta às 10h — qual funciona melhor?"'
                onChange={e => setLocal(v => ({ ...v, closing_question: e.target.value }))} />
              <div className="o-field-hint" style={{ marginTop: 6, color: '#d97706', fontSize: 10.5 }}>
                Bons exemplos: horário A ou B · confirmar valor · confirmar próximo passo
              </div>
            </div>
          )}

          {/* Remover campo personalizado */}
          {local.is_custom && (
            <button onClick={onRemove} style={{
              background: 'transparent', border: '1px solid #ef4444', color: '#ef4444',
              borderRadius: 6, padding: '8px 0', cursor: 'pointer', fontSize: 12,
            }}>
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
  const hasClosingQ = field.allow_closing_question && field.closing_question;

  let hintText = '';
  let hintLabel = '';
  if (responseStyle === 'active') {
    hintText = field.question;
    hintLabel = 'pergunta:';
  } else if (hasClosingQ) {
    hintText = field.closing_question;
    hintLabel = '⚡ fechamento:';
  } else {
    hintText = field.passive_hint;
    hintLabel = 'capturar:';
  }

  return (
    <div onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '11px 14px', borderRadius: 8, cursor: 'pointer',
      background: field.mode === 'off' ? 'var(--o-b1)' : c.bg,
      border: `1px solid ${field.mode === 'off' ? 'var(--o-b1)' : c.border}`,
      opacity: field.mode === 'off' ? 0.55 : 1,
      transition: 'all .15s',
    }}>
      <div style={{ flexShrink: 0, width: 7, height: 7, borderRadius: '50%', background: field.mode === 'off' ? 'var(--o-dim)' : c.border }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, color: 'var(--o-text)', fontWeight: 500 }}>{field.label}</span>
          {field.is_custom && (
            <span style={{ fontSize: 8, letterSpacing: 1.5, padding: '1px 5px', borderRadius: 2, background: 'var(--o-b1)', color: 'var(--o-dim)', textTransform: 'uppercase' }}>custom</span>
          )}
          {responseStyle === 'passive' && hasClosingQ && field.mode !== 'off' && (
            <span style={{ fontSize: 8, letterSpacing: 1.5, padding: '1px 5px', borderRadius: 2, background: 'color-mix(in srgb, #f59e0b 15%, transparent)', color: '#d97706', border: '1px solid color-mix(in srgb, #f59e0b 40%, transparent)', textTransform: 'uppercase' }}>⚡ fechamento</span>
          )}
        </div>
        {hintText && field.mode !== 'off' && (
          <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 2, display: 'flex', gap: 4 }}>
            <span style={{ color: 'var(--o-dim)', flexShrink: 0 }}>{hintLabel}</span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{hintText}</span>
          </div>
        )}
      </div>
      <span style={{ fontSize: 9, letterSpacing: 1.5, padding: '2px 7px', borderRadius: 3, flexShrink: 0, textTransform: 'uppercase', fontWeight: 600, color: c.text, background: c.bg, border: `1px solid ${c.border}` }}>
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
  const { title, sub, passiveSub } = FILTER_LABELS[group];
  const required = fields.filter(f => f.mode === 'required').length;
  const optional  = fields.filter(f => f.mode === 'optional').length;
  const isF3 = group === 'f3';
  const closingQFields = fields.filter(f => f.allow_closing_question && f.closing_question);

  const displaySub = responseStyle === 'passive' ? passiveSub : sub;

  return (
    <div style={{ border: `1px solid ${isF3 && responseStyle === 'passive' ? 'color-mix(in srgb, #f59e0b 35%, transparent)' : 'var(--o-b1)'}`, borderRadius: 10, overflow: 'hidden', marginBottom: 10 }}>
      <div onClick={() => setExpanded(v => !v)} style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', cursor: 'pointer',
        background: isF3 && responseStyle === 'passive' ? 'color-mix(in srgb, #f59e0b 6%, transparent)' : 'var(--o-b1)',
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12.5, color: 'var(--o-text)', fontWeight: 500 }}>{title}</span>
            {isF3 && responseStyle === 'passive' && closingQFields.length > 0 && (
              <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 3, background: 'color-mix(in srgb, #f59e0b 15%, transparent)', border: '1px solid color-mix(in srgb, #f59e0b 40%, transparent)', color: '#d97706', letterSpacing: 1.5, textTransform: 'uppercase' }}>
                ⚡ {closingQFields.length} fechamento
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 2 }}>{displaySub}</div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {required > 0 && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 3, background: MODE_COLORS.required.bg, border: `1px solid ${MODE_COLORS.required.border}`, color: MODE_COLORS.required.text }}>{required} obrig.</span>}
          {optional > 0 && <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 3, background: MODE_COLORS.optional.bg, border: `1px solid ${MODE_COLORS.optional.border}`, color: MODE_COLORS.optional.text }}>{optional} opc.</span>}
          <span style={{ color: 'var(--o-dim)', fontSize: 14, transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform .2s' }}>›</span>
        </div>
      </div>

      {expanded && (
        <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Nota F3 passivo */}
          {isF3 && responseStyle === 'passive' && (
            <div style={{ fontSize: 11, color: '#d97706', padding: '8px 12px', background: 'color-mix(in srgb, #f59e0b 8%, transparent)', borderRadius: 6, border: '1px solid color-mix(in srgb, #f59e0b 25%, transparent)', marginBottom: 4 }}>
              ⚡ Modo passivo — o agente não faz perguntas de descoberta. Apenas as perguntas estratégicas de fechamento configuradas em cada campo são permitidas aqui.
            </div>
          )}
          {fields.length === 0
            ? <div style={{ fontSize: 12, color: 'var(--o-dim)', padding: '8px 0' }}>Nenhum campo neste filtro.</div>
            : fields.map(field => <FieldRow key={field.key} field={field} responseStyle={responseStyle} onClick={() => onFieldClick(field)} />)
          }
        </div>
      )}
    </div>
  );
}

// ─── Painel JSON derivado ─────────────────────────────────────

function JsonPanel({ fields }: { fields: QualificationField[] }) {
  const [open, setOpen] = useState(false);

  const qualification_required_fields = fields.filter(f => f.mode === 'required').map(f => f.key);

  const contract = {
    qualification_fields: fields.map(({ key, label, question, passive_hint, closing_question, allow_closing_question, mode, group }) => ({
      key, label,
      question:          question || null,
      passive_hint:      passive_hint || null,
      closing_question:  allow_closing_question && closing_question ? closing_question : null,
      mode,
      ...(group ? { group } : {}),
    })),
    qualification_required_fields,
    // Campos legados derivados para backward compat com executors
    f1_questions: fields.filter(f => f.group === 'f1').map(f => f.question).filter(Boolean),
    f2_questions: fields.filter(f => f.group === 'f2').map(f => f.question).filter(Boolean),
    f3_questions: fields.filter(f => f.group === 'f3').map(f => f.question).filter(Boolean),
  };

  return (
    <div style={{ marginTop: 32, border: '1px solid var(--o-b1)', borderRadius: 10, overflow: 'hidden' }}>
      <div onClick={() => setOpen(v => !v)} style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 16px', cursor: 'pointer', background: 'var(--o-b1)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-purple)', fontWeight: 600 }}>JSON derivado</span>
          <span style={{ fontSize: 11, color: 'var(--o-sub)' }}>— contrato que seria enviado para a API</span>
        </div>
        <span style={{ color: 'var(--o-dim)', fontSize: 14, transform: open ? 'rotate(90deg)' : 'none', transition: 'transform .2s' }}>›</span>
      </div>

      {open && (
        <div style={{ padding: 16 }}>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 10, letterSpacing: 1.5, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>
              qualification_required_fields → guardrails do Kanban
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {qualification_required_fields.length === 0
                ? <span style={{ fontSize: 11.5, color: 'var(--o-warn)' }}>[] — sem campos obrigatórios configurados</span>
                : qualification_required_fields.map(k => (
                  <span key={k} style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: MODE_COLORS.required.bg, border: `1px solid ${MODE_COLORS.required.border}`, color: MODE_COLORS.required.text, fontFamily: 'monospace' }}>
                    {k}
                  </span>
                ))
              }
            </div>
          </div>
          <pre style={{
            fontSize: 11, lineHeight: 1.6, color: 'var(--o-sub)',
            background: 'var(--o-bg)', padding: 14, borderRadius: 8,
            overflow: 'auto', maxHeight: 400, border: '1px solid var(--o-b1)',
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
  const [agentMode, setAgentMode]           = useState<AgentMode>('sdr_scheduler');
  const [responseStyle, setResponseStyle]   = useState<ResponseStyle>('active');
  const [fields, setFields]                 = useState<QualificationField[]>(buildInitialFields('sdr_scheduler'));
  const [editingField, setEditingField]     = useState<QualificationField | null>(null);
  const [suggestionPending, setSuggestionPending] = useState<AgentMode | null>(null);
  const [addingField, setAddingField]       = useState(false);

  const isSdr = agentMode === 'sdr_scheduler';

  const handleModeChange = useCallback((mode: AgentMode) => {
    if (mode === agentMode) return;
    setAgentMode(mode);
    setSuggestionPending(mode);
  }, [agentMode]);

  const handleApplySuggestion = () => {
    if (suggestionPending) { setFields(buildInitialFields(suggestionPending)); setSuggestionPending(null); }
  };

  const handleSaveField = (updated: QualificationField) => {
    if (addingField) setFields(prev => [...prev, updated]);
    else             setFields(prev => prev.map(f => f.key === updated.key ? updated : f));
    setEditingField(null);
    setAddingField(false);
  };

  const handleRemoveField = () => {
    if (editingField) { setFields(prev => prev.filter(f => f.key !== editingField.key)); setEditingField(null); }
  };

  const newCustomField = (): QualificationField => ({
    key: '', label: '', question: '', passive_hint: '', closing_question: '',
    allow_closing_question: false, mode: 'optional',
    group: isSdr ? 'f1' : undefined, is_custom: true,
  });

  const fieldsByGroup = (group: FilterGroup) => fields.filter(f => f.group === group);

  return (
    <OrionShell>
      {/* Topbar debug */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        background: 'var(--o-bg)', borderBottom: '1px solid var(--o-b1)',
        display: 'flex', alignItems: 'center', gap: 16, padding: '10px 24px',
      }}>
        <span style={{ fontSize: 9, letterSpacing: 2.5, textTransform: 'uppercase', color: '#f59e0b', fontWeight: 700 }}>⚡ Debug UI</span>
        <span style={{ fontSize: 12, color: 'var(--o-sub)' }}>Fase 4 — CamadaQualificacao dinâmica</span>
        <span style={{ fontSize: 10, color: 'var(--o-dim)', marginLeft: 'auto' }}>Sem API · Estado local · Apenas frontend</span>
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
            Campos unificados por tipo de agente. Distinção obrigatório/opcional. Modo ativo vs. passivo com persuasão.
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
                <button key={mode} onClick={() => handleModeChange(mode)} style={{
                  padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
                  background: active ? 'color-mix(in srgb, var(--o-purple) 15%, transparent)' : 'var(--o-b1)',
                  border: `1px solid ${active ? 'var(--o-purple)' : 'transparent'}`,
                  color: active ? 'var(--o-purple)' : 'var(--o-text)',
                  fontSize: 12.5, fontWeight: active ? 600 : 400, transition: 'all .15s',
                }}>
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
            display: 'flex', alignItems: 'center', gap: 14, padding: '12px 16px',
            borderRadius: 8, marginBottom: 20,
            background: 'color-mix(in srgb, #f59e0b 10%, transparent)',
            border: '1px solid color-mix(in srgb, #f59e0b 40%, transparent)',
          }}>
            <span style={{ fontSize: 16 }}>⚙</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12.5, color: 'var(--o-text)', fontWeight: 500, marginBottom: 2 }}>
                Sugestão para "{AGENT_MODE_LABELS[suggestionPending]}"
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--o-sub)' }}>
                Campos típicos para este pipeline foram pré-selecionados.
              </div>
            </div>
            <button onClick={handleApplySuggestion} style={{ padding: '6px 14px', borderRadius: 6, cursor: 'pointer', background: '#f59e0b', border: 'none', color: '#000', fontSize: 12, fontWeight: 600 }}>
              Aplicar sugestão
            </button>
            <button onClick={() => setSuggestionPending(null)} style={{ padding: '6px 14px', borderRadius: 6, cursor: 'pointer', background: 'transparent', border: '1px solid var(--o-b1)', color: 'var(--o-sub)', fontSize: 12 }}>
              Manter atual
            </button>
          </div>
        )}

        {/* Toggle response_style — Fase 4.1 */}
        <div style={{ border: '1px solid var(--o-b1)', borderRadius: 10, overflow: 'hidden', marginBottom: 28 }}>
          <div style={{ padding: '12px 18px', background: 'var(--o-b1)', borderBottom: '1px solid var(--o-b1)' }}>
            <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 2.5, textTransform: 'uppercase', color: 'var(--o-sub)' }}>
              Como o agente coleta informações
            </div>
            <div style={{ fontSize: 11, color: 'var(--o-dim)', marginTop: 3 }}>
              Ambos os modos respondem perguntas e capturam dados da conversa automaticamente.
            </div>
          </div>
          <div style={{ display: 'flex', padding: '10px 12px', gap: 10 }}>
            <button onClick={() => setResponseStyle('active')} style={{
              flex: 1, padding: '12px 16px', borderRadius: 8, cursor: 'pointer', textAlign: 'left',
              background: responseStyle === 'active' ? 'color-mix(in srgb, var(--o-purple) 12%, transparent)' : 'var(--o-b1)',
              border: `1px solid ${responseStyle === 'active' ? 'var(--o-purple)' : 'transparent'}`,
              transition: 'all .2s',
            }}>
              <div style={{ fontSize: 13, fontWeight: responseStyle === 'active' ? 600 : 400, color: responseStyle === 'active' ? 'var(--o-purple)' : 'var(--o-text)', marginBottom: 4 }}>
                Conduz a conversa
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--o-sub)' }}>Pergunta proativamente quando um campo está em falta</div>
              <div style={{ fontSize: 10.5, color: 'var(--o-dim)', marginTop: 6 }}>
                Todos os campos · Sem restrição de perguntas
              </div>
            </button>
            <button onClick={() => setResponseStyle('passive')} style={{
              flex: 1, padding: '12px 16px', borderRadius: 8, cursor: 'pointer', textAlign: 'left',
              background: responseStyle === 'passive' ? 'color-mix(in srgb, #22c55e 10%, transparent)' : 'var(--o-b1)',
              border: `1px solid ${responseStyle === 'passive' ? '#22c55e' : 'transparent'}`,
              transition: 'all .2s',
            }}>
              <div style={{ fontSize: 13, fontWeight: responseStyle === 'passive' ? 600 : 400, color: responseStyle === 'passive' ? '#22c55e' : 'var(--o-text)', marginBottom: 4 }}>
                Responde com persuasão
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--o-sub)' }}>Guia para o próximo passo sem perguntar para qualificar</div>
              <div style={{ fontSize: 10.5, color: 'var(--o-dim)', marginTop: 6 }}>
                Sem perguntas de qualificação · ⚡ Fechamento permitido em F3
              </div>
            </button>
          </div>
        </div>

        {/* Seção: campos */}
        <div className="o-section-hdr" style={{ marginBottom: 14 }}>
          <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
            {responseStyle === 'active'
              ? (isSdr ? 'Filtros de qualificação' : 'O que o agente descobre')
              : (isSdr ? 'O que o agente capta + perguntas de fechamento' : 'Captura passiva + perguntas de fechamento')}
          </span>
          <span className="font-mono-orion" style={{ fontSize: 8, color: 'var(--o-dim)', border: '1px solid var(--o-b1)', padding: '1px 6px', borderRadius: 2 }}>
            {fields.filter(f => f.mode === 'required').length} obrig. · {fields.filter(f => f.mode === 'optional').length} opc.
          </span>
        </div>

        {/* Hint contextual */}
        <div style={{ fontSize: 12, color: 'var(--o-sub)', marginBottom: 16, padding: '8px 12px', background: 'var(--o-b1)', borderRadius: 6 }}>
          {responseStyle === 'active'
            ? isSdr
              ? 'Agente segue a sequência F1→F2→F3. Cada filtro tem sua etapa na conversa. Captura respostas que surgem naturalmente a qualquer momento.'
              : 'Agente pergunta diretamente quando o campo está em falta. Captura respostas que surgem naturalmente a qualquer momento.'
            : isSdr
              ? 'Agente responde de forma persuasiva guiando para o próximo passo. Não faz perguntas de qualificação em F1 e F2. Em F3, perguntas estratégicas de fechamento configuradas são permitidas. Captura dados da conversa automaticamente.'
              : 'Agente responde de forma persuasiva guiando para o próximo passo. Não faz perguntas de qualificação. Perguntas estratégicas de fechamento (⚡) são a única exceção. Captura dados da conversa automaticamente.'}
        </div>

        {/* SDR: F1/F2/F3 */}
        {isSdr && (
          <div style={{ marginBottom: 16 }}>
            {(['f1', 'f2', 'f3'] as FilterGroup[]).map(group => (
              <SdrFilterCard key={group} group={group} fields={fieldsByGroup(group)} responseStyle={responseStyle} onFieldClick={setEditingField} />
            ))}
          </div>
        )}

        {/* Outros: lista plana */}
        {!isSdr && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
            {fields.length === 0 && (
              <div style={{ fontSize: 12.5, color: 'var(--o-dim)', padding: '16px 0', textAlign: 'center' }}>
                Nenhum campo. Adicione abaixo ou aplique a sugestão do modo.
              </div>
            )}
            {fields.map(field => (
              <FieldRow key={field.key} field={field} responseStyle={responseStyle} onClick={() => setEditingField(field)} />
            ))}
          </div>
        )}

        {/* Botão adicionar */}
        <button
          onClick={() => { setEditingField(newCustomField()); setAddingField(true); }}
          style={{
            width: '100%', padding: '10px 0', borderRadius: 8, cursor: 'pointer',
            background: 'transparent', border: '1px dashed var(--o-b1)',
            color: 'var(--o-sub)', fontSize: 13,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            transition: 'all .15s',
          }}
          onMouseEnter={e => { (e.target as HTMLElement).closest('button')!.style.borderColor = 'var(--o-purple)'; (e.target as HTMLElement).closest('button')!.style.color = 'var(--o-purple)'; }}
          onMouseLeave={e => { (e.target as HTMLElement).closest('button')!.style.borderColor = 'var(--o-b1)'; (e.target as HTMLElement).closest('button')!.style.color = 'var(--o-sub)'; }}
        >
          <span style={{ fontSize: 16 }}>＋</span> Adicionar campo personalizado
        </button>

        {/* Legenda */}
        <div style={{ marginTop: 28, padding: '14px 16px', borderRadius: 8, background: 'var(--o-b1)' }}>
          <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 2.5, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 12 }}>
            Legenda
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginBottom: 12 }}>
            {(['required', 'optional', 'off'] as FieldMode[]).map(m => {
              const c = MODE_COLORS[m];
              return (
                <div key={m} style={{ padding: '8px 12px', borderRadius: 6, background: c.bg, border: `1px solid ${c.border}` }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: c.text, marginBottom: 4 }}>{c.label}</div>
                  <div style={{ fontSize: 10.5, color: 'var(--o-sub)' }}>
                    {m === 'required' ? 'Bloqueia avanço no Kanban. Agente prioriza.' :
                     m === 'optional' ? 'Não bloqueia. Capturado se surgir na conversa.' :
                     'Ignorado pelo agente e pelos guardrails.'}
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div style={{ padding: '8px 12px', borderRadius: 6, background: 'color-mix(in srgb, var(--o-purple) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--o-purple) 25%, transparent)' }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--o-purple)', marginBottom: 4 }}>Modo ativo</div>
              <div style={{ fontSize: 10.5, color: 'var(--o-sub)' }}>Agente pergunta proativamente. Usa o campo "Pergunta direta" de cada campo.</div>
            </div>
            <div style={{ padding: '8px 12px', borderRadius: 6, background: 'color-mix(in srgb, #f59e0b 8%, transparent)', border: '1px solid color-mix(in srgb, #f59e0b 25%, transparent)' }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#d97706', marginBottom: 4 }}>⚡ Modo passivo · Fechamento</div>
              <div style={{ fontSize: 10.5, color: 'var(--o-sub)' }}>Única pergunta permitida no passivo. Confirma ou propõe alternativa binária. Nunca descobre.</div>
            </div>
          </div>
        </div>

        {/* JSON */}
        <JsonPanel fields={fields} />

      </div>

      {/* Drawer */}
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
