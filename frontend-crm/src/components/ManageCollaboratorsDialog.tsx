import { useEffect, useRef, useState } from 'react';
import { Loader2, QrCode, RefreshCw, Trash2, UserPlus } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useToast } from '@/hooks/use-toast';
import { ApiError } from '@/lib/api-client';
import { api } from '@/services/api';
import type { CollabMonitorConnectResponse, CollabMonitorInstance, WhatsappQrPayload } from '@/services/api';

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

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.status === 429) {
    return 'Muitas tentativas de conexão — aguarde alguns minutos e tente novamente.';
  }
  return fallback;
}

interface ManageCollaboratorsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Chamado sempre que uma instância é criada/reconectada/removida, para o chamador atualizar listas dependentes. */
  onChanged?: () => void;
}

export function ManageCollaboratorsDialog({ open, onOpenChange, onChanged }: ManageCollaboratorsDialogProps) {
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
    if (!open) return;
    setLoading(true);
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
  }, [open]);

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
          onChanged?.();
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
      onChanged?.();
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
      onChanged?.();
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Gerenciar colaboradores</DialogTitle>
          <DialogDescription>
            Conecte o WhatsApp comercial de um colaborador só para observação — o agente de IA
            nunca responde por essa instância. As conversas alimentam esta tela.
          </DialogDescription>
        </DialogHeader>

        {/* Formulário de cadastro */}
        <div className="flex items-center gap-2">
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Nome do colaborador"
            className="flex-1"
          />
          <Button onClick={handleCreate} disabled={creating || !newName.trim()}>
            {creating ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                Conectando…
              </>
            ) : (
              <>
                <UserPlus className="h-4 w-4 mr-1.5" />
                Cadastrar
              </>
            )}
          </Button>
        </div>

        {/* QR code em foco */}
        {qrTarget && (
          <div className="rounded-lg border bg-muted/40 p-4 flex flex-col items-center gap-3">
            <p className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
              <QrCode className="h-3.5 w-3.5" />
              Conectar WhatsApp de {qrTarget.collaborator_name}
            </p>
            {qrExpired ? (
              <div className="text-center">
                <p className="text-sm text-destructive mb-2">QR code expirado</p>
                <Button size="sm" variant="secondary" onClick={() => handleReconnect(qrTarget.id)}>
                  Novo QR code
                </Button>
              </div>
            ) : qrSrc ? (
              <>
                <img
                  src={qrSrc}
                  alt="QR code WhatsApp"
                  className="w-[200px] h-[200px] rounded-lg bg-white p-2"
                />
                <p className="text-xs text-muted-foreground text-center">
                  Abra o WhatsApp do colaborador → Dispositivos vinculados → Vincular dispositivo
                  <br />
                  <span className="text-amber-600 dark:text-amber-400">Expira em 90 segundos</span>
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Formato de QR não suportado</p>
            )}
            <Button size="sm" variant="ghost" onClick={handleCancelQr}>
              Fechar
            </Button>
          </div>
        )}

        <Separator />

        {/* Lista de instâncias */}
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Colaboradores monitorados
          </p>
          {loading ? (
            <p className="text-sm text-muted-foreground py-2">Carregando…</p>
          ) : instances.length === 0 ? (
            <p className="text-sm text-muted-foreground py-2">Nenhum colaborador cadastrado ainda.</p>
          ) : (
            <ScrollArea className="max-h-64">
              <div className="space-y-1 pr-3">
                {instances.map((instance) => {
                  const connected = isConnected(instance);
                  return (
                    <div key={instance.id} className="flex items-center gap-2.5 py-1.5">
                      <span
                        className={`h-1.5 w-1.5 rounded-full shrink-0 ${
                          connected ? 'bg-emerald-500' : 'bg-destructive'
                        }`}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm truncate">{instance.collaborator_name}</p>
                        <p className="text-xs text-muted-foreground truncate">
                          {instance.phone_e164 || '—'} ·{' '}
                          <Badge variant={connected ? 'default' : 'secondary'} className="text-[10px] px-1.5 h-4">
                            {connected ? 'Conectado' : 'Desconectado'}
                          </Badge>
                        </p>
                      </div>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 shrink-0"
                        title="Reconectar"
                        onClick={() => handleReconnect(instance.id)}
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 shrink-0 text-destructive hover:text-destructive"
                        title="Remover"
                        onClick={() => handleDelete(instance.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
