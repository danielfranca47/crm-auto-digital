import type { LeadQuente } from '@/types/agente';

interface LeadsQuentesProps {
  leads: LeadQuente[];
  onVerTodos?: () => void;
}

const TEMP_CONFIG = {
  hot:  { emoji: '🔥', color: 'var(--o-hot)',  bgClass: 'o-badge-hot' },
  warm: { emoji: '🌡', color: 'var(--o-warn)', bgClass: 'o-badge-warn' },
  cold: { emoji: '❄',  color: 'var(--o-cold)', bgClass: 'o-badge-cold' },
} as const;

/**
 * Card com a lista de leads ordenados por temperatura/score.
 */
export function LeadsQuentes({ leads, onVerTodos }: LeadsQuentesProps) {
  return (
    <div className="o-card">
      <div className="o-card-header">
        <span
          className="font-mono-orion"
          style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}
        >
          Leads quentes
        </span>
        {onVerTodos && (
          <button
            onClick={onVerTodos}
            className="font-mono-orion"
            style={{ fontSize: 8, letterSpacing: 1, color: 'var(--o-dim)', cursor: 'pointer', textTransform: 'uppercase', background: 'none', border: 'none' }}
            onMouseOver={e => (e.currentTarget.style.color = 'var(--o-active)')}
            onMouseOut={e => (e.currentTarget.style.color = 'var(--o-dim)')}
          >
            ver todos →
          </button>
        )}
      </div>
      <div className="o-card-body">
        {leads.map((lead) => {
          const temp = TEMP_CONFIG[lead.temp];
          return (
            <div key={lead.id} className="o-lead-row">
              {/* Avatar */}
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  background: 'var(--o-s3)',
                  border: '1px solid var(--o-b1)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  fontFamily: '"DM Mono", monospace',
                  fontSize: 9,
                  color: 'var(--o-sub)',
                }}
              >
                {lead.initials}
              </div>
              {/* Nome + estágio */}
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12.5, color: 'var(--o-text)' }}>{lead.name}</div>
                <div
                  className="font-mono-orion"
                  style={{ fontSize: 8, letterSpacing: 1, textTransform: 'uppercase', color: 'var(--o-dim)' }}
                >
                  {lead.stage}
                </div>
              </div>
              {/* Badge de temperatura */}
              <span className={`o-badge ${temp.bgClass}`}>
                {temp.emoji} {lead.score} pts
              </span>
            </div>
          );
        })}
        {leads.length === 0 && (
          <p style={{ fontSize: 12, color: 'var(--o-dim)', textAlign: 'center', padding: '12px 0' }}>
            Nenhum lead ativo ainda
          </p>
        )}
      </div>
    </div>
  );
}
