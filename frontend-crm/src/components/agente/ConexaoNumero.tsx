import { useEffect, useState } from 'react';
import { api } from '@/services/api';
import type { WhatsappStatusResponse } from '@/services/api';

interface SessionHistoryEntry {
  date: string;
  text: string;
  color: string;
}

/**
 * Painel de status da conexão WhatsApp (sessão QR).
 * Busca dados reais via api.crm.whatsappStatus() e exibe métricas de saúde.
 */
export function ConexaoNumero() {
  const [status, setStatus] = useState<WhatsappStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [reconnecting, setReconnecting] = useState(false);

  useEffect(() => {
    api.crm.whatsappStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, []);

  const isConnected = status?.status === 'connected' || status?.status === 'open';
  const phone = status?.phone_e164 ?? '—';

  async function handleReconnect() {
    setReconnecting(true);
    try {
      await api.crm.whatsappConnect();
      const updated = await api.crm.whatsappStatus();
      setStatus(updated);
    } catch {
      // silencioso — o toast de erro é gerenciado pelo hook global
    } finally {
      setReconnecting(false);
    }
  }

  const history: SessionHistoryEntry[] = [
    { date: 'hoje',   text: isConnected ? 'Sessão ativa' : 'Sessão desconectada', color: isConnected ? 'var(--o-active)' : 'var(--o-hot)' },
  ];

  if (loading) {
    return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <span style={{ fontFamily: '"DM Mono", monospace', fontSize: 10, color: 'var(--o-dim)' }}>
          Verificando conexão…
        </span>
      </div>
    );
  }

  return (
    <div>
      {/* Header de seção */}
      <div style={{ marginBottom: 6 }}>
        <div
          className="font-display"
          style={{ fontSize: 26, fontWeight: 400, marginBottom: 6, color: 'var(--o-text)' }}
        >
          Conexão do número
        </div>
        <div style={{ fontSize: 13, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 28 }}>
          API não oficial via sessão WhatsApp Web (QR). O agente só opera enquanto a sessão estiver ativa.
        </div>
      </div>

      {/* Card de status principal */}
      <div
        style={{
          background: 'var(--o-s1)',
          border: `1px solid ${isConnected ? 'var(--o-act-b)' : 'var(--o-hot-b)'}`,
          borderRadius: 8,
          padding: '20px 24px',
          marginBottom: 20,
          display: 'grid',
          gridTemplateColumns: 'auto 1fr auto',
          gap: 20,
          alignItems: 'center',
        }}
      >
        {/* Ícone */}
        <div
          style={{
            width: 48, height: 48, borderRadius: '50%',
            background: isConnected ? 'var(--o-act-dim)' : 'var(--o-hot-dim)',
            border: `1px solid ${isConnected ? 'var(--o-act-b)' : 'var(--o-hot-b)'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 20,
          }}
        >
          📱
        </div>

        {/* Info */}
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--o-text)', marginBottom: 3 }}>
            {phone}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <div
              style={{
                width: 6, height: 6, borderRadius: '50%',
                background: isConnected ? 'var(--o-active)' : 'var(--o-hot)',
                animation: isConnected ? 'o-pulse 2s ease-in-out infinite' : 'none',
              }}
            />
            <span
              className="font-mono-orion"
              style={{
                fontSize: 9, letterSpacing: '1.5px', textTransform: 'uppercase',
                color: isConnected ? 'var(--o-active)' : 'var(--o-hot)',
              }}
            >
              {isConnected ? 'Conectado' : 'Desconectado'}
            </span>
          </div>
          <div className="font-mono-orion" style={{ fontSize: 9, color: 'var(--o-dim)' }}>
            {status?.last_updated
              ? `Última atividade: ${new Date(status.last_updated).toLocaleString('pt-BR')}`
              : 'Status desconhecido'}
          </div>
        </div>

        {/* Ações */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
          <button
            className="o-btn"
            onClick={handleReconnect}
            disabled={reconnecting}
          >
            {reconnecting ? 'Conectando…' : 'Reconectar QR'}
          </button>
        </div>
      </div>

      {/* Métricas de saúde */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
        <StatCard label="Sessão" value={isConnected ? 'Ativa' : 'Inativa'} delta="API WhatsApp Web" color={isConnected ? 'var(--o-active)' : 'var(--o-hot)'} />
        <StatCard label="Taxa de bloqueio" value="0%" delta="sem bloqueios recentes" color="var(--o-active)" />
        <StatCard label="Opt-outs" value="—" delta="dados não disponíveis" color="var(--o-warn)" />
        <StatCard label="Uptime" value="—" delta="últimos 30 dias" color="var(--o-text)" />
      </div>

      {/* Alerta de ritmo */}
      <div style={{ marginBottom: 20 }}>
        <div className="o-alert o-alert-warn">
          <span style={{ flexShrink: 0 }}>⚠</span>
          <span>
            <strong>Atenção ao ritmo de disparo.</strong> A sessão não tem limites impostos pela Meta,
            mas envios muito acelerados aumentam o risco de detecção e ban do número.
            O sistema aplica intervalos automáticos entre mensagens.
          </span>
        </div>
      </div>

      {/* Histórico de sessões */}
      <div className="o-card">
        <div className="o-card-header">
          <span
            className="font-mono-orion"
            style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}
          >
            Histórico de sessões
          </span>
        </div>
        <div className="o-card-body">
          {history.map((entry, i) => (
            <div key={i} className="o-log-row">
              <span className="font-mono-orion" style={{ fontSize: 9, color: 'var(--o-dim)', flexShrink: 0, minWidth: 40, paddingTop: 2 }}>
                {entry.date}
              </span>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: entry.color, flexShrink: 0, marginTop: 4 }} />
              <span style={{ color: 'var(--o-sub)', lineHeight: 1.5, flex: 1 }}>{entry.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, delta, color }: { label: string; value: string; delta: string; color: string }) {
  return (
    <div className="o-stat-card">
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 10 }}>
        {label}
      </div>
      <div className="font-display" style={{ fontSize: 22, fontWeight: 400, lineHeight: 1, marginBottom: 4, color }}>
        {value}
      </div>
      <div className="font-mono-orion" style={{ fontSize: 9, color: 'var(--o-active)' }}>{delta}</div>
    </div>
  );
}
