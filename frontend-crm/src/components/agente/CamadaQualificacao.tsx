import { useState } from 'react';
import type { AgentConfig } from '@/types/agente';

interface CamadaQualificacaoProps {
  config: AgentConfig;
  onUpdate: (partial: Partial<AgentConfig>) => void;
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
        <textarea className="o-textarea" value={local} maxLength={max} placeholder={placeholder} onChange={e => setLocal(e.target.value)} />
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

// ─── Modal: lista de perguntas ────────────────────────────────

function ModalFiltro({ title, sub, questions, onSave, onClose }: {
  title: string; sub: string; questions: string[];
  onSave: (qs: string[]) => void; onClose: () => void;
}) {
  const [local, setLocal] = useState<string[]>([...questions]);

  function updateQ(i: number, val: string) {
    setLocal(prev => prev.map((q, idx) => idx === i ? val : q));
  }
  function removeQ(i: number) {
    setLocal(prev => prev.filter((_, idx) => idx !== i));
  }
  function addQ() {
    setLocal(prev => [...prev, '']);
  }

  return (
    <ModalBase title={title} sub={sub} onClose={onClose} onSave={() => onSave(local.filter(q => q.trim()))}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {local.map((q, i) => (
          <div key={i} className="o-q-item">
            <span className="font-mono-orion" style={{ fontSize: 10, color: 'var(--o-dim)', flexShrink: 0, paddingTop: 3, minWidth: 20 }}>
              {String(i + 1).padStart(2, '0')}
            </span>
            <textarea
              className="o-q-text"
              rows={2}
              value={q}
              placeholder="Digite a pergunta…"
              onChange={e => updateQ(i, e.target.value)}
            />
            <button className="o-q-del" onClick={() => removeQ(i)} title="Remover">✕</button>
          </div>
        ))}
        <button className="o-q-add" onClick={addQ}>＋ Adicionar pergunta</button>
      </div>
    </ModalBase>
  );
}

// ─────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────

// ─── Drawer: Score threshold ──────────────────────────────────
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

// ─── Modal: Sinais de compra ──────────────────────────────────
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

// ─── Modal: campos de qualificação obrigatórios ───────────────
const ALL_QUAL_FIELDS: { key: string; label: string; desc: string }[] = [
  { key: 'service_interest',    label: 'Serviço de interesse',   desc: 'O que o lead quer contratar' },
  { key: 'availability_window', label: 'Disponibilidade',        desc: 'Horário ou data disponível' },
  { key: 'price_acceptance',    label: 'Aceitação de preço',     desc: 'Lead aceitou o valor informado' },
  { key: 'location_preference', label: 'Preferência de local',   desc: 'Presencial, online ou domicílio' },
  { key: 'urgency',             label: 'Urgência',               desc: 'Quão urgente é a necessidade' },
  { key: 'decision_role',       label: 'Decisor',                desc: 'Quem decide a compra' },
  { key: 'budget_or_price_acceptance', label: 'Orçamento',       desc: 'Faixa de orçamento disponível' },
  { key: 'constraints',         label: 'Restrições',             desc: 'Limitações de horário ou acesso' },
];

function ModalQualFields({ current, onSave, onClose }: {
  current: string[] | null;
  onSave: (v: string[] | null) => void;
  onClose: () => void;
}) {
  // null = usar defaults do modo; array = override (pode ser vazio)
  const [useOverride, setUseOverride] = useState(current !== null);
  const [selected, setSelected] = useState<string[]>(current ?? []);

  function toggle(key: string) {
    setSelected(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]);
  }

  function handleSave() {
    onSave(useOverride ? selected : null);
  }

  return (
    <ModalBase
      title="Campos de qualificação"
      sub="Define quais informações o agente deve obter antes de avançar o lead no pipeline"
      onClose={onClose}
      onSave={handleSave}
    >
      <div className="o-field" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: 'var(--o-b1)', borderRadius: 6, cursor: 'pointer' }}
          onClick={() => setUseOverride(v => !v)}>
          <div style={{
            width: 36, height: 20, borderRadius: 10, background: useOverride ? 'var(--o-purple)' : 'var(--o-dim)',
            position: 'relative', flexShrink: 0, transition: 'background .2s',
          }}>
            <div style={{
              position: 'absolute', top: 3, left: useOverride ? 18 : 3,
              width: 14, height: 14, borderRadius: '50%', background: '#fff', transition: 'left .2s',
            }} />
          </div>
          <div>
            <div style={{ fontSize: 12.5, color: 'var(--o-text)', fontWeight: 500 }}>
              {useOverride ? 'Campos personalizados' : 'Usar padrão do modo de agente'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 2 }}>
              {useOverride
                ? 'Marque os campos que o agente deve exigir. Lista vazia = agente passivo, sem qualificação obrigatória.'
                : 'O sistema usa automaticamente os campos adequados ao modo configurado (agenda, consultivo, etc.)'}
            </div>
          </div>
        </div>
      </div>

      {useOverride && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {ALL_QUAL_FIELDS.map(f => {
            const active = selected.includes(f.key);
            return (
              <div key={f.key}
                onClick={() => toggle(f.key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px',
                  background: active ? 'color-mix(in srgb, var(--o-purple) 12%, transparent)' : 'var(--o-b1)',
                  border: `1px solid ${active ? 'var(--o-purple)' : 'transparent'}`,
                  borderRadius: 6, cursor: 'pointer',
                }}
              >
                <div style={{
                  width: 16, height: 16, borderRadius: 3, border: `2px solid ${active ? 'var(--o-purple)' : 'var(--o-dim)'}`,
                  background: active ? 'var(--o-purple)' : 'transparent', flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {active && <span style={{ color: '#fff', fontSize: 10, lineHeight: 1 }}>✓</span>}
                </div>
                <div>
                  <div style={{ fontSize: 12.5, color: 'var(--o-text)', fontWeight: 500 }}>{f.label}</div>
                  <div style={{ fontSize: 11, color: 'var(--o-sub)' }}>{f.desc}</div>
                </div>
              </div>
            );
          })}
          {selected.length === 0 && (
            <div style={{ fontSize: 11.5, color: 'var(--o-warn)', padding: '8px 0' }}>
              Nenhum campo selecionado — o agente não fará qualificação obrigatória (modo passivo).
            </div>
          )}
        </div>
      )}
    </ModalBase>
  );
}

type DrawerKey = 'produto' | 'ticket' | 'publico' | 'dor' | 'objecao' | 'score' | null;
type ModalKey  = 'f1' | 'f2' | 'f3' | 'buying_signals' | 'qual_fields' | null;

export function CamadaQualificacao({ config, onUpdate }: CamadaQualificacaoProps) {
  const [drawer, setDrawer] = useState<DrawerKey>(null);
  const [modal, setModal]   = useState<ModalKey>(null);

  const totalPerguntas = config.f1_questions.length + config.f2_questions.length + config.f3_questions.length;
  const showBuyingSignals = config.agent_mode === 'sdr_scheduler' || config.agent_mode === 'agenda' || config.template_key === 'sdr_padrao' || config.template_key === 'hybrid_scheduler';

  return (
    <>
      {/* Contexto do negócio */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Contexto do negócio
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard label="Produto ou serviço" value={config.offer_description || '—'} sub="O que você vende em uma frase" onClick={() => setDrawer('produto')} />
        <EditCard label="Ticket médio"       value={config.ticket_range || '—'}      sub="Valor por venda ou contrato"     onClick={() => setDrawer('ticket')} />
        <EditCard label="Cliente ideal"      value={config.target_audience || '—'}   sub="Perfil e situação de vida"        onClick={() => setDrawer('publico')} />
        <EditCard label="Principal dor"      value={config.main_pain || '—'}          sub="Problema antes de te contratar"  onClick={() => setDrawer('dor')} />
        <EditCard label="Objeção mais comum" value={config.main_objection || '—'}     sub="O que o lead fala ao não comprar" onClick={() => setDrawer('objecao')} />
      </div>

      {/* Filtros */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Filtros de qualificação
        </span>
        <span className="font-mono-orion" style={{ fontSize: 8, color: 'var(--o-dim)', border: '1px solid var(--o-b1)', padding: '1px 6px', borderRadius: 2 }}>
          {totalPerguntas} perguntas ativas
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <FiltroCard
          label="Filtro 1 · Perfil e fit"
          count={config.f1_questions.length}
          sub="Localização · uso pessoal · decisor"
          onClick={() => setModal('f1')}
        />
        <FiltroCard
          label="Filtro 2 · Intenção e dor"
          count={config.f2_questions.length}
          sub="Abertas · exploratórias · contexto"
          onClick={() => setModal('f2')}
        />
        <FiltroCard
          label="Filtro 3 · 4Ps"
          count={config.f3_questions.length}
          sub="Poder · prioridade · preço · timing"
          onClick={() => setModal('f3')}
        />
      </div>

      {/* Qualificação avançada */}
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
        />
        <div className="o-edit-card" onClick={() => onUpdate({ nurture_vs_discard_rule: !config.nurture_vs_discard_rule })}>
          <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>Nurture vs Descarte</div>
          <div style={{ fontSize: 13, color: 'var(--o-text)', marginBottom: 4 }}>{config.nurture_vs_discard_rule ? 'Nurture passivo' : 'Descarte imediato'}</div>
          <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 8 }}>Lead abaixo do score</div>
          <span className={`o-badge ${config.nurture_vs_discard_rule ? 'o-badge-ok' : 'o-badge-warn'}`}>
            {config.nurture_vs_discard_rule ? 'Nurture ativo' : 'Descarte'}
          </span>
          <span className="o-edit-arrow">›</span>
        </div>
        <EditCard
          label="Campos de qualificação"
          value={
            config.qualification_required_fields === null
              ? 'Padrão do modo'
              : config.qualification_required_fields.length === 0
                ? 'Nenhum (modo passivo)'
                : `${config.qualification_required_fields.length} campo(s) ativo(s)`
          }
          sub="Informações obrigatórias antes de avançar o lead"
          onClick={() => setModal('qual_fields')}
        />
        {showBuyingSignals && (
          <EditCard
            label="Sinais de compra"
            value={config.buying_signal_keywords.length > 0 ? `${config.buying_signal_keywords.length} sinal(is)` : 'Não configurado'}
            sub="Palavras que indicam intenção de compra"
            onClick={() => setModal('buying_signals')}
          />
        )}
      </div>

      {/* Drawers */}
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

      {/* Modais de perguntas */}
      {modal === 'f1' && (
        <ModalFiltro
          title="Filtro 1 · Perfil e fit"
          sub="Perguntas binárias que validam se o lead está dentro do seu público-alvo"
          questions={config.f1_questions}
          onClose={() => setModal(null)}
          onSave={qs => { onUpdate({ f1_questions: qs }); setModal(null); }}
        />
      )}
      {modal === 'f2' && (
        <ModalFiltro
          title="Filtro 2 · Intenção e dor"
          sub="Perguntas abertas que revelam contexto, urgência e a dor do lead"
          questions={config.f2_questions}
          onClose={() => setModal(null)}
          onSave={qs => { onUpdate({ f2_questions: qs }); setModal(null); }}
        />
      )}
      {modal === 'f3' && (
        <ModalFiltro
          title="Filtro 3 · Poder, Prioridade, Preço e Timing"
          sub="Qualificação profunda via conversa consultiva — os 4Ps"
          questions={config.f3_questions}
          onClose={() => setModal(null)}
          onSave={qs => { onUpdate({ f3_questions: qs }); setModal(null); }}
        />
      )}
      {modal === 'buying_signals' && (
        <ModalBuyingSignals
          keywords={config.buying_signal_keywords}
          onClose={() => setModal(null)}
          onSave={v => { onUpdate({ buying_signal_keywords: v }); setModal(null); }}
        />
      )}
      {modal === 'qual_fields' && (
        <ModalQualFields
          current={config.qualification_required_fields}
          onClose={() => setModal(null)}
          onSave={v => { onUpdate({ qualification_required_fields: v }); setModal(null); }}
        />
      )}
    </>
  );
}

// ─── Componentes internos ─────────────────────────────────────

function EditCard({ label, value, sub, onClick }: { label: string; value: string; sub: string; onClick: () => void }) {
  return (
    <div className="o-edit-card" onClick={onClick}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 13, color: 'var(--o-text)', marginBottom: 4 }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300 }}>{sub}</div>
      <span className="o-edit-arrow">›</span>
    </div>
  );
}

function FiltroCard({ label, count, sub, onClick }: { label: string; count: number; sub: string; onClick: () => void }) {
  const hasQuestions = count > 0;
  return (
    <div className="o-edit-card" onClick={onClick}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 13, color: 'var(--o-text)', marginBottom: 4 }}>
        {count === 0 ? 'Sem perguntas' : `${count} pergunta${count !== 1 ? 's' : ''} ativa${count !== 1 ? 's' : ''}`}
      </div>
      <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 8 }}>{sub}</div>
      <span className={`o-badge ${hasQuestions ? 'o-badge-ok' : 'o-badge-warn'}`}>
        {hasQuestions ? 'Editar perguntas' : 'Adicionar perguntas'}
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
