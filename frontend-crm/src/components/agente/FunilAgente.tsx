import type { FunilItem } from '@/types/agente';

interface FunilAgenteProps {
  items: FunilItem[];
  onVerTudo?: () => void;
}

/**
 * Card de funil do agente com barras de progresso por estágio.
 * Recebe FunilItem[] e renderiza uma barra horizontal por item.
 */
export function FunilAgente({ items, onVerTudo }: FunilAgenteProps) {
  return (
    <div className="o-card">
      <div className="o-card-header">
        <span
          className="font-mono-orion"
          style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}
        >
          Funil do agente
        </span>
        {onVerTudo && (
          <button
            onClick={onVerTudo}
            className="font-mono-orion"
            style={{ fontSize: 8, letterSpacing: 1, color: 'var(--o-dim)', cursor: 'pointer', textTransform: 'uppercase', background: 'none', border: 'none' }}
            onMouseOver={e => (e.currentTarget.style.color = 'var(--o-active)')}
            onMouseOut={e => (e.currentTarget.style.color = 'var(--o-dim)')}
          >
            ver tudo →
          </button>
        )}
      </div>
      <div className="o-card-body">
        {items.map((item) => (
          <div key={item.stage} className="o-funnel-row">
            <span
              className="font-mono-orion"
              style={{ fontSize: 8, letterSpacing: '1.5px', textTransform: 'uppercase', width: 28, flexShrink: 0, color: item.color }}
            >
              {item.label}
            </span>
            <div style={{ flex: 1, height: 3, background: 'var(--o-s3)', borderRadius: 1 }}>
              <div
                style={{
                  width: `${item.pct}%`,
                  height: '100%',
                  borderRadius: 1,
                  background: item.color,
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
            <span className="font-mono-orion" style={{ fontSize: 10, color: 'var(--o-sub)', minWidth: 28, textAlign: 'right' }}>
              {item.count}
            </span>
            <span className="font-mono-orion" style={{ fontSize: 9, color: 'var(--o-dim)', minWidth: 32, textAlign: 'right' }}>
              {item.pct}%
            </span>
          </div>
        ))}
        {items.length === 0 && (
          <p style={{ fontSize: 12, color: 'var(--o-dim)', textAlign: 'center', padding: '12px 0' }}>
            Nenhum dado disponível
          </p>
        )}
      </div>
    </div>
  );
}
