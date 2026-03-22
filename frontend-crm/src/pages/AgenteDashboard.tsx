import { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { OrionShell } from '@/components/agente/OrionShell';
import { FunilAgente } from '@/components/agente/FunilAgente';
import { LeadsQuentes } from '@/components/agente/LeadsQuentes';
import { ConexaoNumero } from '@/components/agente/ConexaoNumero';
import { api } from '@/services/api';
import type { AiProfile } from '@/services/api';
import type { FunilItem, LeadQuente, ActivityEntry } from '@/types/agente';

type Tab = 'overview' | 'conversations' | 'pipeline' | 'conexao';

// ─── Helpers ──────────────────────────────────────────────────

function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map(s => s[0]?.toUpperCase() ?? '')
    .join('');
}

function computeFunil(leads: any[]): FunilItem[] {
  const active = leads.filter(l => l.category !== 'archived');
  const total  = active.length || 1;

  const f1 = active.filter(l => ['to-prospect', 'prospecting'].includes(l.category)).length;
  const f2 = active.filter(l => ['qualified'].includes(l.category)).length;
  const f3 = active.filter(l => ['closing'].includes(l.category)).length;
  const ag = active.filter(l => ['scheduled', 'meeting'].includes(l.category)).length;

  const pct = (n: number) => Math.round((n / total) * 100);

  return [
    { stage: 'entrada', label: 'ent', count: active.length, pct: 100,       color: 'var(--o-sub)' },
    { stage: 'f1',      label: 'F1',  count: f1 + f2 + f3 + ag, pct: pct(f1 + f2 + f3 + ag), color: 'var(--o-cold)' },
    { stage: 'f2',      label: 'F2',  count: f2 + f3 + ag, pct: pct(f2 + f3 + ag), color: 'var(--o-warn)' },
    { stage: 'f3',      label: 'F3',  count: f3 + ag, pct: pct(f3 + ag), color: 'var(--o-purple)' },
    { stage: 'ag',      label: 'ag',  count: ag,      pct: pct(ag),    color: 'var(--o-active)' },
  ];
}

function computeLeadsQuentes(leads: any[]): LeadQuente[] {
  const active = leads
    .filter(l => l.category !== 'archived')
    .slice(0, 5);

  return active.map(l => {
    const name = l.contactName || l.companyName || 'Lead';
    const cat  = l.category ?? '';
    const stageMap: Record<string, string> = {
      'to-prospect': 'F1 · Entrada',
      'prospecting':  'F1 · Perfil',
      'qualified':    'F2 · Dor',
      'closing':      'F3 · 4Ps',
      'scheduled':    'Agendamento',
    };
    const stage = stageMap[cat] ?? cat;

    // score simulado por categoria
    const scoreMap: Record<string, number> = {
      'scheduled': 90, 'closing': 75, 'qualified': 55, 'prospecting': 35, 'to-prospect': 20,
    };
    const score = scoreMap[cat] ?? 30;
    const temp: 'hot' | 'warm' | 'cold' = score >= 70 ? 'hot' : score >= 45 ? 'warm' : 'cold';

    return { id: l.id, name, initials: initials(name), stage, score, temp };
  });
}

// ─── Painéis internos ─────────────────────────────────────────

function PainelOverview({
  profile, leads, agentId, onTabChange,
}: {
  profile: AiProfile | null; leads: any[]; agentId: string; onTabChange: (t: Tab) => void;
}) {
  const funil         = useMemo(() => computeFunil(leads), [leads]);
  const leadsQuentes  = useMemo(() => computeLeadsQuentes(leads), [leads]);
  const active        = leads.filter(l => l.category !== 'archived');
  const qualificados  = leads.filter(l => ['closing', 'qualified', 'scheduled'].includes(l.category)).length;
  const pctQual       = active.length ? Math.round((qualificados / active.length) * 100) : 0;

  const criticalCount = 0; // placeholder — seria de um endpoint de validação

  const activity: ActivityEntry[] = [
    { time: '—', text: 'Dados de atividade disponíveis em breve', color: 'var(--o-dim)' },
  ];

  return (
    <div className="o-panel o-fade-in">
      {criticalCount > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div className="o-alert o-alert-danger">
            <span style={{ flexShrink: 0 }}>⚠</span>
            <span>
              <strong>{criticalCount} itens críticos</strong> na Camada 3 sem configuração.
            </span>
            <Link to={`/agentes/${agentId}/configuracao`} className="o-btn o-btn-danger" style={{ marginLeft: 'auto', fontSize: 8 }}>
              Resolver →
            </Link>
          </div>
        </div>
      )}

      {/* Hero */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 24, alignItems: 'start', paddingBottom: 28, marginBottom: 28, borderBottom: '1px solid var(--o-b0)' }}>
        <div>
          <div className="font-display" style={{ fontSize: 38, fontWeight: 400, lineHeight: 1.1, color: 'var(--o-text)', marginBottom: 6 }}>
            {profile?.name ?? '—'} <em style={{ fontStyle: 'italic', color: 'var(--o-sub)' }}>·</em>
          </div>
          <div style={{ fontSize: 13, color: 'var(--o-sub)', fontWeight: 300, marginTop: 4 }}>
            {profile?.brand_name ?? '—'}
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginTop: 10 }}>
            <span className="o-chip o-chip-active">✓ Ativo</span>
            {profile?.tone_of_voice && <span className="o-chip">Tom: {profile.tone_of_voice}</span>}
            {profile?.agent_mode    && <span className="o-chip">{profile.agent_mode}</span>}
            {profile?.timezone      && <span className="o-chip">{profile.timezone}</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <Link to={`/agentes/${agentId}/configuracao`} className="o-btn">Editar agente</Link>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 28 }}>
        <StatCard label="Leads ativos"    value={String(active.length)}  delta="total do pipeline" color="var(--o-text)" />
        <StatCard label="Qualificados"    value={String(qualificados)}   delta={`${pctQual}% do total`} color="var(--o-active)" />
        <StatCard label="Agendamentos"    value="—"                       delta="dados em breve"     color="var(--o-warn)" />
        <StatCard label="Taxa de resposta" value="—"                      delta="dados em breve"     color="var(--o-text)" />
      </div>

      {/* Funil + Leads quentes */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        <FunilAgente items={funil} onVerTudo={() => onTabChange('pipeline')} />
        <LeadsQuentes leads={leadsQuentes} onVerTodos={() => onTabChange('conversations')} />
      </div>

      {/* Estado da configuração por camada */}
      <div style={{ marginBottom: 8 }}>
        <div className="o-section-hdr">
          <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
            Estado da configuração por camada
          </span>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 20 }}>
        <LayerCard
          num="Camada 1" title="Identidade e estratégia"
          desc="Quem é o agente, como fala e como vende."
          progress={profile?.name && profile?.brand_name ? 100 : 50}
          statusText={profile?.name ? 'Completa' : 'Incompleta'}
          colorClass="o-layer-l1"
          link={`/agentes/${agentId}/configuracao`}
        />
        <LayerCard
          num="Camada 2" title="Qualificação"
          desc="Filtros F1, F2, F3 e perguntas do agente."
          progress={70}
          statusText="Verificar perguntas"
          colorClass="o-layer-l2"
          link={`/agentes/${agentId}/configuracao`}
        />
        <LayerCard
          num="Camada 3" title="Pipeline e comportamento"
          desc="Follow-up, score, reativação e proteção do número."
          progress={30}
          statusText="Incompleta"
          colorClass="o-layer-l3"
          link={`/agentes/${agentId}/configuracao`}
        />
      </div>

      {/* Log de atividade */}
      <div className="o-card">
        <div className="o-card-header">
          <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
            Atividade recente
          </span>
        </div>
        <div className="o-card-body">
          {activity.map((entry, i) => (
            <div key={i} className="o-log-row">
              <span className="font-mono-orion" style={{ fontSize: 9, color: 'var(--o-dim)', flexShrink: 0, minWidth: 40, paddingTop: 2 }}>
                {entry.time}
              </span>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: entry.color, flexShrink: 0, marginTop: 4 }} />
              <span style={{ color: 'var(--o-sub)', lineHeight: 1.5, flex: 1 }}>
                {entry.boldText && <strong style={{ color: 'var(--o-text)', fontWeight: 400 }}>{entry.boldText}</strong>}
                {entry.text}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PainelConversas({ leads }: { leads: any[] }) {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'hot' | 'waiting'>('all');

  const active = leads.filter(l => l.category !== 'archived');
  const filtered = active.filter(l => {
    const name = (l.contactName || l.companyName || '').toLowerCase();
    if (search && !name.includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="o-panel o-fade-in">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
        <input
          className="o-input"
          style={{ flex: 1, minWidth: 180 }}
          placeholder="Buscar conversa, nome ou número…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        {(['all', 'hot', 'waiting'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              fontFamily: '"DM Mono", monospace',
              fontSize: 8,
              letterSpacing: '1.5px',
              textTransform: 'uppercase',
              padding: '6px 12px',
              borderRadius: 2,
              border: '1px solid',
              cursor: 'pointer',
              transition: 'all 0.15s',
              borderColor: filter === f ? 'var(--o-act-b)' : 'var(--o-b1)',
              background:   filter === f ? 'var(--o-act-dim)' : 'transparent',
              color:        filter === f ? 'var(--o-active)' : 'var(--o-dim)',
            }}
          >
            {f === 'all' ? 'Todas' : f === 'hot' ? '🔥 Quentes' : 'Aguardando'}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {filtered.length === 0 && (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--o-dim)', fontSize: 13 }}>
            Nenhuma conversa encontrada
          </div>
        )}
        {filtered.slice(0, 20).map(lead => {
          const name    = lead.contactName || lead.companyName || 'Lead';
          const ini     = initials(name);
          const cat     = lead.category ?? '';
          const isHot   = ['closing', 'scheduled'].includes(cat);
          const preview = lead.customMessage || lead.observations || 'Sem mensagem recente';
          return (
            <div key={lead.id} className={`o-conv-item ${isHot ? 'o-conv-unread' : ''}`}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%', background: 'var(--o-s3)',
                border: '1px solid var(--o-b1)', display: 'flex', alignItems: 'center',
                justifyContent: 'center', fontFamily: '"DM Mono"', fontSize: 10, color: 'var(--o-sub)',
              }}>
                {ini}
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, color: 'var(--o-text)', marginBottom: 3 }}>{name}</div>
                <div style={{ fontSize: 11.5, color: 'var(--o-sub)', fontWeight: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {preview}
                </div>
              </div>
              <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-end' }}>
                <span className="font-mono-orion" style={{ fontSize: 8, color: 'var(--o-dim)' }}>—</span>
                {isHot && <span className="o-badge o-badge-hot">🔥</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PainelPipeline({ leads }: { leads: any[] }) {
  const active  = leads.filter(l => l.category !== 'archived');
  const f1count = active.filter(l => ['to-prospect', 'prospecting'].includes(l.category)).length;
  const f2count = active.filter(l => ['qualified'].includes(l.category)).length;
  const f3count = active.filter(l => ['closing'].includes(l.category)).length;
  const agcount = active.filter(l => ['scheduled'].includes(l.category)).length;

  const conv = (a: number, b: number) => b > 0 ? Math.round((a / b) * 100) : 0;

  return (
    <div className="o-panel o-fade-in">
      <div className="font-display" style={{ fontSize: 26, fontWeight: 400, marginBottom: 20, color: 'var(--o-text)' }}>
        Pipeline · <em style={{ color: 'var(--o-sub)' }}>Dados reais</em>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
        <StatCard label="F1 → F2" value={`${conv(f2count, f1count)}%`} delta={`${f2count} de ${f1count} leads`} color="var(--o-cold)" />
        <StatCard label="F2 → F3" value={`${conv(f3count, f2count)}%`} delta={`${f3count} de ${f2count} leads`} color="var(--o-warn)" />
        <StatCard label="F3 → Ag." value={`${conv(agcount, f3count)}%`} delta={`${agcount} de ${f3count} leads`} color="var(--o-active)" />
        <StatCard label="Total ativo" value={String(active.length)} delta="leads no pipeline" color="var(--o-text)" />
      </div>
      <div className="o-alert o-alert-info">
        <span>ℹ</span>
        <span>Score de temperatura não implementado — valores calculados por categoria de lead.</span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Página principal
// ─────────────────────────────────────────────────────────────

export default function AgenteDashboard() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate    = useNavigate();

  const [tab, setTab]       = useState<Tab>('overview');
  const [profile, setProfile] = useState<AiProfile | null>(null);
  const [leads, setLeads]   = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [profileData, leadsData] = await Promise.all([
          api.core.getAiProfileMe(),
          api.getLeads(),
        ]);
        if (alive) {
          setProfile(profileData);
          setLeads(Array.isArray(leadsData) ? leadsData : []);
        }
      } catch {
        // silencioso
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const tabs: { id: Tab; label: string }[] = [
    { id: 'overview',       label: 'Visão geral' },
    { id: 'conversations',  label: 'Conversas' },
    { id: 'pipeline',       label: 'Pipeline' },
    { id: 'conexao',        label: 'Conexão do número' },
  ];

  if (loading) {
    return (
      <OrionShell>
        <div style={{ padding: 48, textAlign: 'center' }}>
          <span className="font-mono-orion" style={{ fontSize: 10, color: 'var(--o-dim)' }}>Carregando agente…</span>
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
          <span style={{ color: 'var(--o-text)' }}>{profile?.name ?? '—'}</span>
          <span>›</span>
          <span style={{ color: 'var(--o-active)' }}>Dashboard</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="o-status-pill">
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--o-active)', animation: 'o-pulse 2s ease-in-out infinite' }} />
            Agente ativo
          </div>
          <Link to={`/agentes/${agentId}/configuracao`} className="o-btn">← Configurar agente</Link>
          <Link to="/" className="o-btn" style={{ fontSize: 8 }}>← CRM</Link>
        </div>
      </header>

      {/* Subnav */}
      <nav className="o-subnav">
        {tabs.map(t => (
          <div
            key={t.id}
            className={`o-subnav-item ${tab === t.id ? 'o-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </div>
        ))}
      </nav>

      {/* Conteúdo */}
      <div className="o-content">
        {tab === 'overview'      && <PainelOverview profile={profile} leads={leads} agentId={agentId!} onTabChange={setTab} />}
        {tab === 'conversations' && <PainelConversas leads={leads} />}
        {tab === 'pipeline'      && <PainelPipeline leads={leads} />}
        {tab === 'conexao'       && (
          <div className="o-panel o-fade-in">
            <ConexaoNumero />
          </div>
        )}
      </div>
    </OrionShell>
  );
}

// ─── Componentes utilitários locais ──────────────────────────

function StatCard({ label, value, delta, color }: { label: string; value: string; delta: string; color: string }) {
  return (
    <div className="o-stat-card">
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 10 }}>
        {label}
      </div>
      <div className="font-display" style={{ fontSize: 28, fontWeight: 400, lineHeight: 1, marginBottom: 4, color }}>
        {value}
      </div>
      <div className="font-mono-orion" style={{ fontSize: 9, color: 'var(--o-active)' }}>{delta}</div>
    </div>
  );
}

function LayerCard({ num, title, desc, progress, statusText, colorClass, link }: {
  num: string; title: string; desc: string; progress: number;
  statusText: string; colorClass: string; link: string;
}) {
  const isWarning = progress < 50;
  return (
    <Link to={link} className={`o-layer-card ${colorClass}`}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 3, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 8 }}>
        {num}
      </div>
      <div className="font-display" style={{ fontSize: 17, fontWeight: 400, color: 'var(--o-text)', marginBottom: 6 }}>
        {title}
      </div>
      <div style={{ fontSize: 12, color: 'var(--o-sub)', lineHeight: 1.6, marginBottom: 14, fontWeight: 300 }}>
        {desc}
      </div>
      <div style={{ height: 2, background: 'var(--o-s3)', borderRadius: 1, marginBottom: 8 }}>
        <div style={{ width: `${progress}%`, height: '100%', borderRadius: 1, background: isWarning ? 'var(--o-hot)' : 'var(--o-active)', transition: 'width 0.4s ease' }} />
      </div>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: '1.5px', textTransform: 'uppercase', color: isWarning ? 'var(--o-hot)' : 'var(--o-dim)', display: 'flex', justifyContent: 'space-between' }}>
        <span>{statusText}</span>
        <span>{progress}%</span>
      </div>
    </Link>
  );
}
