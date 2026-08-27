import { useEffect, useRef, useState } from 'react';
import { api } from '@/services/api';
import type { WhatsappConnectResponse, WhatsappStatusResponse } from '@/services/api';

interface SessionHistoryEntry {
  date: string;
  text: string;
  color: string;
}

function getQrSrc(qr: WhatsappConnectResponse['qr']): string | null {
  if (!qr?.value) return null;
  if (qr.kind === 'url') return qr.value;
  if (qr.kind === 'base64') return `data:image/png;base64,${qr.value}`;
  if (qr.value.startsWith('data:image')) return qr.value;
  if (qr.value.length > 80) return `data:image/png;base64,${qr.value}`;
  return null;
}

export function ConexaoNumero() {
  const [status, setStatus] = useState<WhatsappStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [reconnecting, setReconnecting] = useState(false);
  const [qrPayload, setQrPayload] = useState<WhatsappConnectResponse | null>(null);
  const [qrExpired, setQrExpired] = useState(false);
  const [modo, setModo] = useState<'qr' | 'pareamento'>('qr');
  const [phoneInput, setPhoneInput] = useState('');

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const qrTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api.crm.whatsappStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));

    return () => {
      stopPolling();
    };
  }, []);

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (qrTimeoutRef.current) { clearTimeout(qrTimeoutRef.current); qrTimeoutRef.current = null; }
  };

  const startPolling = (timeoutMs = 90_000) => {
    stopPolling();
    qrTimeoutRef.current = setTimeout(() => {
      setQrExpired(true);
      stopPolling();
    }, timeoutMs);

    pollRef.current = setInterval(async () => {
      try {
        const updated = await api.crm.whatsappStatus();
        if (updated.status === 'connected' || updated.status === 'open') {
          stopPolling();
          setQrPayload(null);
          setQrExpired(false);
          setStatus(updated);
        }
      } catch {
        // ignora erros pontuais no polling
      }
    }, 3_000);
  };

  async function handleReconnect() {
    setReconnecting(true);
    setQrExpired(false);
    try {
      const phone = modo === 'pareamento' ? phoneInput.trim() : undefined;
      const resp = await api.crm.whatsappConnect(phone);
      if (resp.pair_code || resp.qr?.value) {
        setQrPayload(resp);
        startPolling(resp.pair_code ? 280_000 : 90_000);
      } else {
        const updated = await api.crm.whatsappStatus();
        setStatus(updated);
      }
    } catch {
      // silencioso — o toast de erro é gerenciado pelo hook global
    } finally {
      setReconnecting(false);
    }
  }

  async function handleRefreshQr() {
    setQrExpired(false);
    setReconnecting(true);
    try {
      const phone = modo === 'pareamento' ? phoneInput.trim() : undefined;
      const resp = await api.crm.whatsappRefreshQr(phone);
      setQrPayload(resp);
      startPolling(resp.pair_code ? 280_000 : 90_000);
    } catch {
      // silencioso
    } finally {
      setReconnecting(false);
    }
  }

  function handleCancelQr() {
    stopPolling();
    setQrPayload(null);
    setQrExpired(false);
  }

  function toggleModo() {
    setModo((prev) => (prev === 'qr' ? 'pareamento' : 'qr'));
    setQrPayload(null);
    setQrExpired(false);
  }

  const isConnected = status?.status === 'connected' || status?.status === 'open';
  const phone = status?.phone_e164 ?? '—';

  const history: SessionHistoryEntry[] = [
    { date: 'hoje', text: isConnected ? 'Sessão ativa' : 'Sessão desconectada', color: isConnected ? 'var(--o-active)' : 'var(--o-hot)' },
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

  const qrSrc = qrPayload ? getQrSrc(qrPayload.qr) : null;

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
          {!qrPayload && modo === 'qr' && (
            <button
              className="o-btn"
              onClick={handleReconnect}
              disabled={reconnecting}
            >
              {reconnecting ? 'Conectando…' : 'Reconectar QR'}
            </button>
          )}
          {!qrPayload && modo === 'pareamento' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
              <input
                type="tel"
                value={phoneInput}
                onChange={(e) => setPhoneInput(e.target.value)}
                placeholder="Ex: 5511999999999"
                className="o-input"
                style={{ fontSize: 12, padding: '6px 10px', width: 180, textAlign: 'right' }}
              />
              <button
                className="o-btn"
                onClick={handleReconnect}
                disabled={reconnecting || !phoneInput.trim()}
              >
                {reconnecting ? 'Gerando…' : 'Gerar código'}
              </button>
            </div>
          )}
          {qrPayload && (
            <button
              className="o-btn o-btn-ghost"
              onClick={handleCancelQr}
              style={{ fontSize: 11 }}
            >
              Cancelar
            </button>
          )}
          {!qrPayload && (
            <button
              className="o-btn o-btn-ghost"
              onClick={toggleModo}
              style={{ fontSize: 10.5, color: 'var(--o-dim)', textDecoration: 'underline' }}
            >
              {modo === 'qr' ? 'Não tem outro aparelho? Conectar com código' : 'Voltar para QR code'}
            </button>
          )}
        </div>
      </div>

      {/* Bloco QR Code / Código de pareamento */}
      {qrPayload && (
        <div
          style={{
            background: 'var(--o-s1)',
            border: '1px solid var(--o-b1)',
            borderRadius: 8,
            padding: '24px',
            marginBottom: 20,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 16,
          }}
        >
          <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-sub)' }}>
            {qrPayload.pair_code ? 'Código de pareamento' : 'Escaneie com o WhatsApp'}
          </div>

          {qrExpired ? (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 13, color: 'var(--o-hot)', marginBottom: 12 }}>
                {qrPayload.pair_code ? 'Código expirado' : 'QR code expirado'}
              </div>
              <button
                className="o-btn"
                onClick={handleRefreshQr}
                disabled={reconnecting}
              >
                {reconnecting ? 'Gerando…' : qrPayload.pair_code ? 'Novo código' : 'Novo QR code'}
              </button>
            </div>
          ) : qrPayload.pair_code ? (
            <>
              <div
                className="font-mono-orion"
                style={{ fontSize: 28, letterSpacing: 4, color: '#111', background: '#fff', padding: '12px 20px', borderRadius: 8 }}
              >
                {qrPayload.pair_code}
              </div>
              <div style={{ fontSize: 11, color: 'var(--o-dim)', textAlign: 'center' }}>
                No WhatsApp do celular → Aparelhos conectados → Conectar um aparelho → Conectar com número de telefone
                <br />
                <span style={{ color: 'var(--o-warn)' }}>Expira em 5 minutos</span>
              </div>
            </>
          ) : qrSrc ? (
            <>
              <img
                src={qrSrc}
                alt="QR code WhatsApp"
                style={{ width: 200, height: 200, borderRadius: 8, background: '#fff', padding: 8 }}
              />
              <div style={{ fontSize: 11, color: 'var(--o-dim)', textAlign: 'center' }}>
                Abra o WhatsApp → Dispositivos vinculados → Vincular dispositivo
                <br />
                <span style={{ color: 'var(--o-warn)' }}>Expira em 90 segundos</span>
              </div>
            </>
          ) : (
            <div style={{ fontSize: 12, color: 'var(--o-dim)' }}>Formato de QR não suportado</div>
          )}
        </div>
      )}

      {/* Métricas de saúde */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
        <StatCard label="Sessão" value={isConnected ? 'Ativa' : 'Inativa'} delta="API WhatsApp Web" color={isConnected ? 'var(--o-active)' : 'var(--o-hot)'} />
        <StatCard label="Taxa de bloqueio" value="0%" delta="sem bloqueios recentes" color="var(--o-active)" />
        <StatCard label="Opt-outs" value="—" delta="dados não disponíveis" color="var(--o-warn)" />
        <StatCard label="Uptime" value="—" delta="últimos 30 dias" color="var(--o-text)" />
      </div>

      {/* Alerta de ritmo */}
      <div style={{ marginBottom: 12 }}>
        <div className="o-alert o-alert-warn">
          <span style={{ flexShrink: 0 }}>⚠</span>
          <span>
            <strong>Atenção ao ritmo de disparo.</strong> A sessão não tem limites impostos pela Meta,
            mas envios muito acelerados aumentam o risco de detecção e ban do número.
            O sistema aplica intervalos automáticos entre mensagens.
          </span>
        </div>
      </div>

      {/* Alerta de sessão dupla */}
      <div style={{ marginBottom: 20 }}>
        <div className="o-alert o-alert-warn">
          <span style={{ flexShrink: 0 }}>⚠</span>
          <span>
            <strong>Não use o WhatsApp Web ou o WhatsApp Desktop neste número.</strong> A ligação do
            agente já conta como um aparelho vinculado — usar o WhatsApp Web/Desktop ao mesmo tempo,
            no mesmo número, pode fazer o WhatsApp derrubar a sessão do agente por conflito entre
            aparelhos conectados. Se precisar de acompanhar as conversas pelo computador, use apenas o
            próprio telemóvel com esse número.
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
