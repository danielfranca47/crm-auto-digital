import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { OrionShell } from '@/components/agente/OrionShell';
import { CamadaIdentidade } from '@/components/agente/CamadaIdentidade';
import { CamadaQualificacao } from '@/components/agente/CamadaQualificacao';
import { CamadaPipeline } from '@/components/agente/CamadaPipeline';
import { api } from '@/services/api';
import { DEFAULT_AGENT_CONFIG } from '@/types/agente';
import type { AgentConfig, AgenteRunner } from '@/types/agente';
import { AGENT_MODE_LABELS, IDENTITY_MODE_LABELS, LGPD_LABELS, REATIVACAO_LABELS, MEDIA_FALLBACK_LABELS } from '@/types/agente';

// ─── Tipos de painel ─────────────────────────────────────────
type PanelId = 'overview' | 'c1' | 'c2' | 'c3';

// ─── Painel: Resumo ──────────────────────────────────────────
function PainelResumo({
  config, agentId, runner, onNavigate, onSave, onDiscard, saving, dirty,
}: {
  config: AgentConfig; agentId: string; runner: AgenteRunner | null;
  onNavigate: (p: PanelId) => void; onUpdate: (partial: Partial<AgentConfig>) => void;
  onSave: () => void; onDiscard: () => void; saving: boolean; dirty: boolean;
}) {
  const optoutOk = config.opt_out_keywords.length > 0;
  const lgpdOk   = !!config.lgpd_mode;
  const reatOk   = !!config.reactivation_mode;
  const criticals = [!optoutOk, !lgpdOk, !reatOk].filter(Boolean).length;

  const layer1Complete = !!(config.name && config.brand_name && config.agent_mode && config.identity_mode);
  const layer2Questions = config.f1_questions.length + config.f2_questions.length + config.f3_questions.length;
  const layer2Progress  = Math.min(100, Math.round((layer2Questions / 10) * 100));
  const layer3Items     = [optoutOk, lgpdOk, reatOk, config.media_fallback, config.followup_h1 > 0].filter(Boolean).length;

  return (
    <div className="o-panel o-fade-in">
      {dirty && (
        <div className="o-draft-banner">
          <span>●</span>
          <span><strong>Modo de edição.</strong> Alterações salvas como rascunho — aplicadas apenas em novas conversas.</span>
          <button className="o-btn o-btn-primary" style={{ marginLeft: 'auto' }} onClick={onSave} disabled={saving}>
            {saving ? 'Salvando…' : 'Publicar alterações'}
          </button>
          <button className="o-btn" onClick={onDiscard}>Descartar</button>
        </div>
      )}

      {criticals > 0 && (
        <div className="o-alert o-alert-danger" style={{ marginBottom: 20 }}>
          <span style={{ flexShrink: 0 }}>⚠</span>
          <span>
            <strong>{criticals} itens críticos</strong> na Camada 3 sem configuração.
            Opt-out não configurado — leads que pedem para parar continuam sendo contactados.
          </span>
        </div>
      )}

      <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 8, color: 'var(--o-purple)' }}>
        Configuração · {config.name || '—'}
      </div>
      <div className="font-display" style={{ fontSize: 28, fontWeight: 400, marginBottom: 6, color: 'var(--o-text)' }}>Resumo do agente</div>
      <div style={{ fontSize: 12.5, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 24 }}>
        Visão consolidada de todas as camadas. Clique em qualquer seção para editar.
      </div>

      {/* Camada 1 */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Camada 1 — Identidade e estratégia
        </span>
        <span className="font-mono-orion" style={{ fontSize: 8, color: 'var(--o-dim)', border: '1px solid var(--o-b1)', padding: '1px 6px', borderRadius: 2 }}>
          {layer1Complete ? 'Completa' : 'Incompleta'}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <SummaryCard label="Nome do agente"  value={config.name || '—'}                               onClick={() => onNavigate('c1')} />
        <SummaryCard label="Empresa"         value={config.brand_name || '—'}                         onClick={() => onNavigate('c1')} />
        <SummaryCard label="Tipo de agente"  value={config.template_key || '—'}                       onClick={() => onNavigate('c1')} />
        <SummaryCard label="Modo de identidade" value={IDENTITY_MODE_LABELS[config.identity_mode] || '—'} onClick={() => onNavigate('c1')} />
        <SummaryCard label="Forma de vender" value={AGENT_MODE_LABELS[config.agent_mode] || '—'}     onClick={() => onNavigate('c1')} />
        <SummaryCard label="Perfil gerado"   value={config.custom_instructions ? config.custom_instructions.slice(0, 50) + '…' : 'Não configurado'}
          onClick={() => onNavigate('c1')} italic />
      </div>

      {/* Camada 2 */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Camada 2 — Qualificação
        </span>
        <span className="font-mono-orion" style={{ fontSize: 8, color: 'var(--o-dim)', border: '1px solid var(--o-b1)', padding: '1px 6px', borderRadius: 2 }}>
          {layer2Progress}%
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <SummaryCard label="Produto / Serviço"  value={config.offer_description || '—'} onClick={() => onNavigate('c2')} />
        <SummaryCard label="Principal dor"       value={config.main_pain || '—'}          onClick={() => onNavigate('c2')} />
        <SummaryCard label="Filtro 1 · F1"       value={`${config.f1_questions.length} pergunta(s)`} onClick={() => onNavigate('c2')} />
        <SummaryCard label="Filtro 2 · F2"       value={`${config.f2_questions.length} pergunta(s)`} onClick={() => onNavigate('c2')} />
        <SummaryCard label="Filtro 3 · F3"       value={`${config.f3_questions.length} pergunta(s)`} onClick={() => onNavigate('c2')} />
      </div>

      {/* Camada 3 */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Camada 3 — Pipeline e comportamento
        </span>
        <span className="font-mono-orion" style={{ fontSize: 8, color: criticals > 0 ? 'var(--o-hot)' : 'var(--o-dim)', border: `1px solid ${criticals > 0 ? 'var(--o-hot-b)' : 'var(--o-b1)'}`, padding: '1px 6px', borderRadius: 2 }}>
          {layer3Items} / 5 · {criticals > 0 ? `${criticals} críticos` : 'OK'}
        </span>
      </div>
      {criticals > 0 && (
        <div className="o-alert o-alert-danger" style={{ marginBottom: 8 }}>
          <span style={{ flexShrink: 0 }}>⚠</span>
          <span>Opt-out não configurado — risco de ban do número. LGPD é lei brasileira, obrigatório.</span>
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14 }}>
        <SummaryCard label="Opt-out"         value={optoutOk ? `${config.opt_out_keywords.length} palavras` : 'Não configurado'} status={optoutOk ? 'ok' : 'miss'} onClick={() => onNavigate('c3')} />
        <SummaryCard label="LGPD"            value={LGPD_LABELS[config.lgpd_mode] || 'Não configurado'}                         status={lgpdOk ? 'ok' : 'miss'}   onClick={() => onNavigate('c3')} />
        <SummaryCard label="Reativação"      value={REATIVACAO_LABELS[config.reactivation_mode] || 'Não configurado'}           status={reatOk ? 'ok' : 'miss'}   onClick={() => onNavigate('c3')} />
        <SummaryCard label="Cadência follow-up" value={`${config.followup_h1}h · ${Math.round(config.followup_h2/24)}d · ${Math.round(config.followup_h3/24)}d`} status="ok" onClick={() => onNavigate('c3')} />
        <SummaryCard label="Mídia inválida"  value={MEDIA_FALLBACK_LABELS[config.media_fallback] || '—'}                         status="ok"                       onClick={() => onNavigate('c3')} />
      </div>

      <div style={{ marginTop: 24, display: 'flex', gap: 10 }}>
        {dirty && (
          <>
            <button className="o-btn o-btn-primary" onClick={onSave} disabled={saving}>
              {saving ? 'Salvando…' : 'Publicar alterações'}
            </button>
            <button className="o-btn" onClick={onDiscard}>Descartar rascunho</button>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Painel: Camada 1 ─────────────────────────────────────────
function PainelCamada1({ config, onUpdate, onBack, onSave, saving, dirty }: {
  config: AgentConfig; onUpdate: (p: Partial<AgentConfig>) => void;
  onBack: () => void; onSave: () => void; saving: boolean; dirty: boolean;
}) {
  return (
    <div className="o-panel o-fade-in">
      {dirty && (
        <div className="o-draft-banner">
          <span>●</span>
          <span><strong>Editando Camada 1.</strong> Alterações aplicadas apenas em novas conversas.</span>
          <button className="o-btn o-btn-primary" style={{ marginLeft: 'auto' }} onClick={onSave} disabled={saving}>
            {saving ? 'Salvando…' : 'Salvar camada'}
          </button>
          <button className="o-btn" onClick={onBack}>Cancelar</button>
        </div>
      )}
      <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 8, color: 'var(--o-active)' }}>
        Camada 1 · Identidade e estratégia
      </div>
      <div className="font-display" style={{ fontSize: 28, fontWeight: 400, marginBottom: 6, color: 'var(--o-text)' }}>Identidade e estratégia</div>
      <div style={{ fontSize: 12.5, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 24 }}>
        Define quem é o agente, como ele se apresenta, com qual tom fala e como aborda vendas.
      </div>

      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Dados básicos e identidade
        </span>
      </div>
      <CamadaIdentidade config={config} onUpdate={onUpdate} />

      <div style={{ display: 'flex', gap: 10, marginTop: 24 }}>
        {dirty && (
          <button className="o-btn o-btn-primary" onClick={onSave} disabled={saving}>
            {saving ? 'Salvando…' : 'Salvar Camada 1'}
          </button>
        )}
        <button className="o-btn" onClick={onBack}>← Voltar</button>
      </div>
    </div>
  );
}

// ─── Painel: Camada 2 ─────────────────────────────────────────
function PainelCamada2({ config, onUpdate, onBack, onSave, saving, dirty }: {
  config: AgentConfig; onUpdate: (p: Partial<AgentConfig>) => void;
  onBack: () => void; onSave: () => void; saving: boolean; dirty: boolean;
}) {
  return (
    <div className="o-panel o-fade-in">
      {dirty && (
        <div className="o-draft-banner">
          <span>●</span>
          <span><strong>Editando Camada 2.</strong> Alterações aplicadas apenas em novas conversas.</span>
          <button className="o-btn o-btn-primary" style={{ marginLeft: 'auto' }} onClick={onSave} disabled={saving}>
            {saving ? 'Salvando…' : 'Salvar camada'}
          </button>
          <button className="o-btn" onClick={onBack}>Cancelar</button>
        </div>
      )}
      <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 8, color: 'var(--o-warn)' }}>
        Camada 2 · Qualificação
      </div>
      <div className="font-display" style={{ fontSize: 28, fontWeight: 400, marginBottom: 6, color: 'var(--o-text)' }}>Qualificação</div>
      <div style={{ fontSize: 12.5, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 24 }}>
        Define o contexto do negócio e as perguntas dos três filtros de qualificação.
      </div>
      <CamadaQualificacao config={config} onUpdate={onUpdate} />
      <div style={{ display: 'flex', gap: 10, marginTop: 24 }}>
        {dirty && (
          <button className="o-btn o-btn-primary" onClick={onSave} disabled={saving}>
            {saving ? 'Salvando…' : 'Salvar Camada 2'}
          </button>
        )}
        <button className="o-btn" onClick={onBack}>← Voltar</button>
      </div>
    </div>
  );
}

// ─── Painel: Camada 3 ─────────────────────────────────────────
function PainelCamada3({ config, onUpdate, onBack, onSave, saving, dirty, phoneNumber }: {
  config: AgentConfig; onUpdate: (p: Partial<AgentConfig>) => void;
  onBack: () => void; onSave: () => void; saving: boolean; dirty: boolean;
  phoneNumber?: string | null;
}) {
  const criticals = [!config.opt_out_keywords.length, !config.lgpd_mode, !config.reactivation_mode].filter(Boolean).length;

  return (
    <div className="o-panel o-fade-in">
      {criticals > 0 && (
        <div className="o-alert o-alert-danger" style={{ marginBottom: 12 }}>
          <span style={{ flexShrink: 0 }}>⚠</span>
          <span>{criticals} configurações críticas ausentes. Opt-out: risco de ban do número. LGPD: exigência legal.</span>
        </div>
      )}
      {dirty && (
        <div className="o-draft-banner">
          <span>●</span>
          <span><strong>Editando Camada 3.</strong> Alterações aplicadas apenas em novas conversas.</span>
          <button className="o-btn o-btn-primary" style={{ marginLeft: 'auto' }} onClick={onSave} disabled={saving}>
            {saving ? 'Salvando…' : 'Salvar camada'}
          </button>
          <button className="o-btn" onClick={onBack}>Cancelar</button>
        </div>
      )}
      <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 3, textTransform: 'uppercase', marginBottom: 8, color: 'var(--o-purple)' }}>
        Camada 3 · Pipeline e comportamento
      </div>
      <div className="font-display" style={{ fontSize: 28, fontWeight: 400, marginBottom: 6, color: 'var(--o-text)' }}>Pipeline e comportamento</div>
      <div style={{ fontSize: 12.5, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 24 }}>
        Configura como o agente reage a eventos, gerencia a cadência e protege o número.
      </div>
      <CamadaPipeline config={config} onUpdate={onUpdate} phoneNumber={phoneNumber} />
      <div style={{ display: 'flex', gap: 10, marginTop: 24 }}>
        {dirty && (
          <button className="o-btn o-btn-primary" onClick={onSave} disabled={saving}>
            {saving ? 'Salvando…' : 'Salvar Camada 3'}
          </button>
        )}
        <button className="o-btn" onClick={onBack}>← Voltar</button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Página principal
// ─────────────────────────────────────────────────────────────

export default function AgenteConfiguracao() {
  const { agentId } = useParams<{ agentId: string }>();

  const [activePanel, setActivePanel] = useState<PanelId>('overview');
  const [config, setConfig]           = useState<AgentConfig>(DEFAULT_AGENT_CONFIG);
  const [savedConfig, setSavedConfig] = useState<AgentConfig>(DEFAULT_AGENT_CONFIG);
  const [runner, setRunner]           = useState<AgenteRunner | null>(null);
  const [loading, setLoading]         = useState(true);
  const [saving, setSaving]           = useState(false);
  const [error, setError]             = useState<string | null>(null);

  // Subnav config
  const navItems: { id: PanelId; label: string; badge?: number }[] = [
    { id: 'overview', label: 'Resumo' },
    { id: 'c1',       label: '① Identidade' },
    { id: 'c2',       label: '② Qualificação' },
    {
      id: 'c3', label: '③ Pipeline',
      badge: [!config.opt_out_keywords.length, !config.lgpd_mode, !config.reactivation_mode].filter(Boolean).length || undefined,
    },
  ];

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [loaded, runners] = await Promise.all([
          api.agente.getConfig(),
          api.agents.list(),
        ]);
        if (alive) {
          setConfig(loaded);
          setSavedConfig(loaded);
          setRunner(runners[0] ?? null);
        }
      } catch {
        if (alive) setError('Não foi possível carregar a configuração do agente.');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const updateConfig = useCallback((partial: Partial<AgentConfig>) => {
    setConfig(prev => ({ ...prev, ...partial }));
  }, []);

  const isDirty = JSON.stringify(config) !== JSON.stringify(savedConfig);

  async function handleSave() {
    setSaving(true);
    try {
      await api.agente.saveConfig(config);
      setSavedConfig(config);
    } catch {
      setError('Erro ao salvar. Tente novamente.');
    } finally {
      setSaving(false);
    }
  }

  function handleDiscard() {
    setConfig(savedConfig);
  }

  function navigate(panel: PanelId) {
    setActivePanel(panel);
    window.scrollTo(0, 0);
  }

  const phoneNumber = runner?.status === 'online' ? '(número conectado)' : null;

  if (loading) {
    return (
      <OrionShell>
        <div style={{ padding: 48, textAlign: 'center' }}>
          <span className="font-mono-orion" style={{ fontSize: 10, color: 'var(--o-dim)' }}>Carregando configuração…</span>
        </div>
      </OrionShell>
    );
  }

  if (error) {
    return (
      <OrionShell>
        <div style={{ padding: 48, textAlign: 'center' }}>
          <div className="o-alert o-alert-danger" style={{ maxWidth: 500, margin: '0 auto' }}>
            <span>⚠</span>
            <span>{error}</span>
          </div>
        </div>
      </OrionShell>
    );
  }

  return (
    <OrionShell>
      {/* Topbar */}
      <header className="o-topbar">
        <div className="font-mono-orion" style={{ fontSize: 11, letterSpacing: 3, textTransform: 'uppercase', color: 'var(--o-sub)', paddingRight: 24, borderRight: '1px solid var(--o-b1)', marginRight: 20, whiteSpace: 'nowrap' }}>
          Orion CRM
        </div>
        <div className="font-mono-orion" style={{ fontSize: 10, letterSpacing: '1.5px', color: 'var(--o-dim)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>Agentes</span>
          <span>›</span>
          <span style={{ color: 'var(--o-text)' }}>{config.name || '—'}</span>
          <span>›</span>
          <span style={{ color: 'var(--o-purple)' }}>Configuração</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <Link to={`/agentes/${agentId}/dashboard`} className="o-btn">← Ver dashboard</Link>
          <Link to="/" className="o-btn" style={{ fontSize: 8 }}>← CRM</Link>
        </div>
      </header>

      {/* Subnav */}
      <nav className="o-subnav">
        {navItems.map(item => (
          <div
            key={item.id}
            className={`o-subnav-item ${activePanel === item.id ? 'o-active' : ''}`}
            onClick={() => navigate(item.id)}
          >
            {item.label}
            {item.badge != null && item.badge > 0 && (
              <span className="o-num-badge">{item.badge}</span>
            )}
          </div>
        ))}
      </nav>

      {/* Conteúdo por painel */}
      <div className="o-content">
        {activePanel === 'overview' && (
          <PainelResumo
            config={config}
            agentId={agentId!}
            runner={runner}
            onNavigate={navigate}
            onUpdate={updateConfig}
            onSave={handleSave}
            onDiscard={handleDiscard}
            saving={saving}
            dirty={isDirty}
          />
        )}
        {activePanel === 'c1' && (
          <PainelCamada1
            config={config}
            onUpdate={updateConfig}
            onBack={() => navigate('overview')}
            onSave={handleSave}
            saving={saving}
            dirty={isDirty}
          />
        )}
        {activePanel === 'c2' && (
          <PainelCamada2
            config={config}
            onUpdate={updateConfig}
            onBack={() => navigate('overview')}
            onSave={handleSave}
            saving={saving}
            dirty={isDirty}
          />
        )}
        {activePanel === 'c3' && (
          <PainelCamada3
            config={config}
            onUpdate={updateConfig}
            onBack={() => navigate('overview')}
            onSave={handleSave}
            saving={saving}
            dirty={isDirty}
            phoneNumber={phoneNumber}
          />
        )}
      </div>
    </OrionShell>
  );
}

// ─── Componentes internos do resumo ──────────────────────────

function SummaryCard({ label, value, sub, status, onClick, italic }: {
  label: string; value: string; sub?: string; status?: 'ok' | 'warn' | 'miss'; onClick: () => void; italic?: boolean;
}) {
  const valueColor = status === 'miss' ? 'var(--o-hot)' : status === 'warn' ? 'var(--o-warn)' : 'var(--o-text)';
  return (
    <div className="o-edit-card" onClick={onClick}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 13, color: valueColor, marginBottom: 4, fontStyle: italic ? 'italic' : 'normal' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300 }}>{sub}</div>}
      {status && (
        <span className={`o-badge ${status === 'ok' ? 'o-badge-ok' : status === 'miss' ? 'o-badge-miss' : 'o-badge-warn'}`} style={{ marginTop: 8 }}>
          {status === 'ok' ? 'Configurado' : status === 'miss' ? 'Crítico' : 'Parcial'}
        </span>
      )}
      <span className="o-edit-arrow">›</span>
    </div>
  );
}
