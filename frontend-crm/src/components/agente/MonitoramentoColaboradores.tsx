import { useEffect, useRef, useState } from 'react';
import { api } from '@/services/api';
import type { CollabMonitorConnectResponse, CollabMonitorInstance, WhatsappQrPayload } from '@/services/api';
import { ApiError } from '@/lib/api-client';
import { useToast } from '@/hooks/use-toast';

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.status === 429) {
    return 'Muitas tentativas de conexão — aguarde alguns minutos e tente novamente.';
  }
  return fallback;
}

function getQrSrc(qr: WhatsappQrPayload | undefined): string | null {
  if (!qr?.value) return null;
  if (qr.kind === 'url') return qr.value;
  if (qr.kind === 'base64') return `data:image/png;base64,${qr.value}`;
  if (qr.value.startsWith('data:image')) return qr.value;
  if (qr.value.length > 80) return `data:image/png;base64,${qr.value}`;
  return null;
}

function isConnected(instance: CollabMonitorInstance): boolean {
  const s = (instance.connection_status || instance.status || '').toLowerCase();
  return s === 'connected' || s === 'active' || s === 'open';
}

export function MonitoramentoColaboradores() {
  const { toast } = useToast();
  const [instances, setInstances] = useState<CollabMonitorInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [qrTarget, setQrTarget] = useState<CollabMonitorConnectResponse | null>(null);
  const [qrExpired, setQrExpired] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const qrTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadInstances = async () => {
    const list = await api.crm.collabMonitorList();
    setInstances(list);
  };

  useEffect(() => {
    loadInstances()
      .catch(() => {
        toast({
          title: 'Erro ao carregar colaboradores',
          description: 'Não foi possível carregar a lista de colaboradores monitorados.',
          variant: 'destructive',
        });
      })
      .finally(() => setLoading(false));
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (qrTimeoutRef.current) { clearTimeout(qrTimeoutRef.current); qrTimeoutRef.current = null; }
  };

  const startPolling = (instanceRowId: number) => {
    stopPolling();
    qrTimeoutRef.current = setTimeout(() => {
      setQrExpired(true);
      stopPolling();
    }, 90_000);

    pollRef.current = setInterval(async () => {
      try {
        const list = await api.crm.collabMonitorList();
        setInstances(list);
        const updated = list.find((i) => i.id === instanceRowId);
        if (updated && isConnected(updated)) {
          stopPolling();
          setQrTarget(null);
          setQrExpired(false);
        }
      } catch {
        // ignora erros pontuais no polling
      }
    }, 3_000);
  };

  async function handleCreate() {
    const collaborator_name = newName.trim();
    if (!collaborator_name) return;
    setCreating(true);
    try {
      const resp = await api.crm.collabMonitorCreate(collaborator_name);
      setNewName('');
      await loadInstances();
      if (resp.qr?.value) {
        setQrTarget(resp);
        setQrExpired(false);
        startPolling(resp.id);
      }
    } catch (err) {
      toast({
        title: 'Erro ao cadastrar colaborador',
        description: describeError(err, 'Não foi possível cadastrar o colaborador. Tente novamente.'),
        variant: 'destructive',
      });
    } finally {
      setCreating(false);
    }
  }

  async function handleReconnect(id: number) {
    setQrExpired(false);
    try {
      const resp = await api.crm.collabMonitorReconnect(id);
      await loadInstances();
      if (resp.qr?.value) {
        setQrTarget(resp);
        startPolling(id);
      }
    } catch (err) {
      toast({
        title: 'Erro ao reconectar',
        description: describeError(err, 'Não foi possível reconectar o colaborador. Tente novamente.'),
        variant: 'destructive',
      });
    }
  }

  async function handleDelete(id: number) {
    try {
      await api.crm.collabMonitorDelete(id);
      if (qrTarget?.id === id) {
        stopPolling();
        setQrTarget(null);
      }
      await loadInstances();
    } catch (err) {
      toast({
        title: 'Erro ao remover colaborador',
        description: describeError(err, 'Não foi possível remover o colaborador. Tente novamente.'),
        variant: 'destructive',
      });
    }
  }

  function handleCancelQr() {
    stopPolling();
    setQrTarget(null);
    setQrExpired(false);
  }

  const qrSrc = qrTarget ? getQrSrc(qrTarget.qr) : null;

  if (loading) {
    return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <span style={{ fontFamily: '"DM Mono", monospace', fontSize: 10, color: 'var(--o-dim)' }}>
          Carregando instâncias monitoradas…
        </span>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 6 }}>
        <div className="font-display" style={{ fontSize: 26, fontWeight: 400, marginBottom: 6, color: 'var(--o-text)' }}>
          Monitoramento de colaboradores
        </div>
        <div style={{ fontSize: 13, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 24 }}>
          Conecte o WhatsApp comercial de um colaborador só para observação — o agente de IA nunca
          responde por essa instância. As conversas alimentam a coluna "Monitorado" do Kanban.
        </div>
      </div>

      {/* Formulário de cadastro */}
      <div
        style={{
          background: 'var(--o-s1)',
          border: '1px solid var(--o-b1)',
          borderRadius: 8,
          padding: '16px 20px',
          marginBottom: 20,
          display: 'flex',
          gap: 12,
          alignItems: 'center',
        }}
      >
        <input
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Nome do colaborador"
          className="o-input"
          style={{ fontSize: 12.5, padding: '8px 12px', flex: 1 }}
        />
        <button className="o-btn" onClick={handleCreate} disabled={creating || !newName.trim()}>
          {creating ? 'Conectando…' : 'Cadastrar e conectar'}
        </button>
      </div>

      {/* QR code em foco */}
      {qrTarget && (
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
            Conectar WhatsApp de {qrTarget.collaborator_name}
          </div>
          {qrExpired ? (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 13, color: 'var(--o-hot)', marginBottom: 12 }}>QR code expirado</div>
              <button className="o-btn" onClick={() => handleReconnect(qrTarget.id)}>Novo QR code</button>
            </div>
          ) : qrSrc ? (
            <>
              <img
                src={qrSrc}
                alt="QR code WhatsApp"
                style={{ width: 200, height: 200, borderRadius: 8, background: '#fff', padding: 8 }}
              />
              <div style={{ fontSize: 11, color: 'var(--o-dim)', textAlign: 'center' }}>
                Abra o WhatsApp do colaborador → Dispositivos vinculados → Vincular dispositivo
                <br />
                <span style={{ color: 'var(--o-warn)' }}>Expira em 90 segundos</span>
              </div>
            </>
          ) : (
            <div style={{ fontSize: 12, color: 'var(--o-dim)' }}>Formato de QR não suportado</div>
          )}
          <button className="o-btn o-btn-ghost" onClick={handleCancelQr} style={{ fontSize: 11 }}>
            Fechar
          </button>
        </div>
      )}

      {/* Lista de instâncias */}
      <div className="o-card">
        <div className="o-card-header">
          <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
            Colaboradores monitorados
          </span>
        </div>
        <div className="o-card-body">
          {instances.length === 0 && (
            <div style={{ fontSize: 12.5, color: 'var(--o-dim)', padding: '8px 0' }}>
              Nenhum colaborador cadastrado ainda.
            </div>
          )}
          {instances.map((instance) => {
            const connected = isConnected(instance);
            return (
              <div key={instance.id} className="o-log-row" style={{ alignItems: 'center' }}>
                <div
                  style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: connected ? 'var(--o-active)' : 'var(--o-hot)',
                    flexShrink: 0,
                  }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, color: 'var(--o-text)' }}>{instance.collaborator_name}</div>
                  <div className="font-mono-orion" style={{ fontSize: 9, color: 'var(--o-dim)' }}>
                    {instance.phone_e164 || '—'} · {connected ? 'Conectado' : 'Desconectado'}
                  </div>
                </div>
                <button
                  className="o-btn o-btn-ghost"
                  style={{ fontSize: 10.5 }}
                  onClick={() => handleReconnect(instance.id)}
                >
                  Reconectar
                </button>
                <button
                  className="o-btn o-btn-ghost"
                  style={{ fontSize: 10.5, color: 'var(--o-hot)' }}
                  onClick={() => handleDelete(instance.id)}
                >
                  Remover
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
