import { useState } from 'react';
import type { AgentConfig } from '@/types/agente';
import {
  AGENT_MODE_LABELS,
  IDENTITY_MODE_LABELS,
  TEMPLATE_KEY_LABELS,
} from '@/types/agente';

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
        <label className="o-field-label">Nome</label>
        <div className="o-field-hint">Este nome aparecerá em todas as mensagens enviadas.</div>
        <input className="o-input" value={local} maxLength={40} onChange={e => setLocal(e.target.value)} placeholder="Ex: Sofia, Max, Atendente…" />
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

// ─── Drawer: Tom ─────────────────────────────────────────────
function DrawerTom({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  return (
    <DrawerBase title="Tom de comunicação" sub="Estilo de linguagem em todas as mensagens" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Tom</label>
        <input className="o-input" value={local} onChange={e => setLocal(e.target.value)} placeholder="Ex: equilibrado, formal, descontraído…" />
        <div className="o-field-hint">Texto livre — descreva o tom que o agente deve usar.</div>
      </div>
    </DrawerBase>
  );
}

// ─── Modal: Tipo de agente (template_key) ────────────────────
function ModalTipoAgente({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const options = [
    { v: 'sdr_padrao',             label: 'SDR Padrão',                desc: 'Pipeline completo com qualificação e handoff. Ideal para alto ticket.', sub: 'Imóveis · Advocacia · Consultoria' },
    { v: 'consultor_especialista', label: 'Consultor Especialista',     desc: 'Processos longos, diagnóstico e educação antes da venda.', sub: 'Saúde · Educação · B2B complexo' },
    { v: 'closer_agressivo',       label: 'Closer Agressivo',           desc: 'Foco em fechamento direto. Pipeline curto, alta conversão.', sub: 'Infoprodutos · Cursos · E-commerce' },
    { v: 'hybrid_scheduler',       label: 'Híbrido Agendador',          desc: 'Qualifica e agenda. Entrega o lead preparado para o profissional.', sub: 'Coaches · Terapeutas · Consultores' },
  ];
  return (
    <ModalBase title="Tipo de agente" sub="Define a complexidade do pipeline e o nível de autonomia" onClose={onClose} onSave={() => onSave(local)}>
      {options.map(o => (
        <OptCard key={o.v} selected={local === o.v} onClick={() => setLocal(o.v)} label={o.label} desc={o.desc} sub={o.sub} />
      ))}
    </ModalBase>
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

// ─── Modal: Forma de vender (agent_mode) ─────────────────────
function ModalVenda({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const options = [
    { v: 'sdr_scheduler', label: 'SDR · Agendamento',   desc: 'Qualifica e foca em agendar reunião ou sessão.' },
    { v: 'consultivo',    label: 'Consultivo',           desc: 'Usa perguntas estratégicas para diagnosticar e apresentar a solução.' },
    { v: 'closer',        label: 'Closer · Direto',      desc: 'Aborda proativamente e fecha de forma mais direta.' },
    { v: 'agenda',        label: 'Foco em Agenda',       desc: '4 campos de qualificação obrigatórios, objetivo é o agendamento.' },
    { v: 'direto',        label: 'Vendedor Direto',      desc: '3 campos de qualificação, fechamento rápido.' },
  ];
  return (
    <ModalBase title="Forma de vender" sub="Define a abordagem comercial e estilo de argumentação" onClose={onClose} onSave={() => onSave(local)}>
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

type DrawerKey = 'nome' | 'empresa' | 'tom' | null;
type ModalKey  = 'tipo' | 'identidade' | 'venda' | 'perfil' | null;

export function CamadaIdentidade({ config, onUpdate, resumo }: CamadaIdentidadeProps) {
  const [drawer, setDrawer] = useState<DrawerKey>(null);
  const [modal, setModal]   = useState<ModalKey>(null);

  const profilePreview = config.custom_instructions
    ? config.custom_instructions.slice(0, 60) + '…'
    : 'Ainda não configurado';

  const cards = [
    {
      key: 'nome',
      label: 'Nome do agente',
      value: config.name || '—',
      sub: 'Como se apresenta ao lead',
      onClick: () => setDrawer('nome'),
    },
    {
      key: 'empresa',
      label: 'Empresa',
      value: config.brand_name || '—',
      sub: `Nicho: ${config.niche || 'não definido'}`,
      onClick: () => setDrawer('empresa'),
    },
    {
      key: 'tipo',
      label: 'Tipo de agente',
      value: TEMPLATE_KEY_LABELS[config.template_key] || config.template_key || '—',
      sub: 'Define complexidade do pipeline',
      onClick: () => setModal('tipo'),
    },
    {
      key: 'identidade',
      label: 'Modo de identidade',
      value: IDENTITY_MODE_LABELS[config.identity_mode] || config.identity_mode || '—',
      sub: 'Como se apresenta ao lead',
      onClick: () => setModal('identidade'),
    },
    {
      key: 'venda',
      label: 'Forma de vender',
      value: AGENT_MODE_LABELS[config.agent_mode] || config.agent_mode || '—',
      sub: 'Estilo de abordagem comercial',
      onClick: () => setModal('venda'),
    },
    {
      key: 'perfil',
      label: 'Perfil gerado',
      value: profilePreview,
      sub: 'Texto de instruções personalizadas',
      onClick: () => setModal('perfil'),
      italic: true,
    },
  ];

  const displayCards = resumo ? cards : cards;

  return (
    <>
      {/* Tom de comunicação card extra (só no modo full) */}
      {!resumo && (
        <div style={{ marginBottom: 14 }}>
          <div className="o-section-hdr">
            <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
              Comunicação
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 14 }}>
            <EditCard
              label="Tom de comunicação"
              value={config.tone_of_voice || '—'}
              sub="Estilo de linguagem"
              onClick={() => setDrawer('tom')}
            />
          </div>
        </div>
      )}

      {/* Cards principais */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14 }}>
        {displayCards.map(card => (
          <EditCard
            key={card.key}
            label={card.label}
            value={card.value}
            sub={card.sub}
            onClick={card.onClick}
            italic={card.italic}
          />
        ))}
      </div>

      {/* Drawers */}
      {drawer === 'nome' && (
        <DrawerNome value={config.name} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ name: v }); setDrawer(null); }} />
      )}
      {drawer === 'empresa' && (
        <DrawerEmpresa value={config.brand_name} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ brand_name: v }); setDrawer(null); }} />
      )}
      {drawer === 'tom' && (
        <DrawerTom value={config.tone_of_voice} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ tone_of_voice: v }); setDrawer(null); }} />
      )}

      {/* Modais */}
      {modal === 'tipo' && (
        <ModalTipoAgente value={config.template_key} onClose={() => setModal(null)} onSave={v => { onUpdate({ template_key: v }); setModal(null); }} />
      )}
      {modal === 'identidade' && (
        <ModalIdentidade value={config.identity_mode} onClose={() => setModal(null)} onSave={v => { onUpdate({ identity_mode: v as AgentConfig['identity_mode'] }); setModal(null); }} />
      )}
      {modal === 'venda' && (
        <ModalVenda value={config.agent_mode} onClose={() => setModal(null)} onSave={v => { onUpdate({ agent_mode: v as AgentConfig['agent_mode'] }); setModal(null); }} />
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

function EditCard({ label, value, sub, onClick, italic }: {
  label: string; value: string; sub: string; onClick: () => void; italic?: boolean;
}) {
  return (
    <div className="o-edit-card" onClick={onClick}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>
        {label}
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
