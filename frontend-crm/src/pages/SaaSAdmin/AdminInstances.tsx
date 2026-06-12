import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { RefreshCw, RotateCcw, Wifi, WifiOff } from "lucide-react";

type Instance = {
  id: number;
  instance_id: string;
  user_id: number;
  user_email: string;
  phone_e164: string | null;
  provider: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
};

function statusIsOnline(status: string) {
  return status === "active" || status === "connected";
}

function StatusBadge({ status }: { status: string }) {
  const online = statusIsOnline(status);
  return (
    <Badge
      className={
        online
          ? "bg-emerald-900/50 text-emerald-300 border-emerald-700/50 text-xs"
          : "bg-amber-900/50 text-amber-300 border-amber-700/50 text-xs"
      }
    >
      {online ? <Wifi size={10} className="mr-1" /> : <WifiOff size={10} className="mr-1" />}
      {status}
    </Badge>
  );
}

function formatDate(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function AdminInstances() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [reconnecting, setReconnecting] = useState<Set<string>>(new Set());

  const { data: instances = [], isLoading, refetch } = useQuery({
    queryKey: ["admin", "instances"],
    queryFn: () => api.admin.listInstances(),
    staleTime: 30_000,
  });

  const handleReconnect = async (inst: Instance) => {
    setReconnecting((prev) => new Set(prev).add(inst.instance_id));
    try {
      const res = await api.admin.reconnectInstance(inst.instance_id);
      if (res.ok) {
        toast({
          title: "Reconexão iniciada",
          description: `Instância ${inst.instance_id} está reconectando.`,
        });
        queryClient.invalidateQueries({ queryKey: ["admin", "instances"] });
      } else {
        toast({
          title: "Falha na reconexão",
          description: res.error ?? "Erro desconhecido.",
          variant: "destructive",
        });
      }
    } catch (err: any) {
      toast({
        title: "Erro",
        description: err?.message ?? "Erro ao reconectar.",
        variant: "destructive",
      });
    } finally {
      setReconnecting((prev) => {
        const next = new Set(prev);
        next.delete(inst.instance_id);
        return next;
      });
    }
  };

  const online = instances.filter((i) => statusIsOnline(i.status));
  const offline = instances.filter((i) => !statusIsOnline(i.status));
  const sorted = [...offline, ...online];

  return (
    <div className="p-6 max-w-5xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-200">Instâncias WhatsApp</h1>
          <p className="text-slate-500 text-sm">
            {isLoading
              ? "Carregando…"
              : `${instances.length} instância${instances.length !== 1 ? "s" : ""} — ${online.length} online, ${offline.length} offline`}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isLoading}
          className="border-slate-700 text-slate-400 hover:bg-slate-800 gap-1.5"
        >
          <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
          Atualizar
        </Button>
      </div>

      <Card className="bg-slate-800/60 border-slate-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-slate-400">
            Conexões ({sorted.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {/* header row */}
          <div className="grid grid-cols-[1fr_1.2fr_0.8fr_0.8fr_0.9fr_auto] gap-3 px-5 py-2 border-b border-slate-700/60">
            {["Instância", "Usuário", "Telefone", "Status", "Atualizado", ""].map((h) => (
              <span key={h} className="text-xs uppercase tracking-wide text-slate-500">
                {h}
              </span>
            ))}
          </div>

          <div className="divide-y divide-slate-700/40">
            {sorted.map((inst) => (
              <div
                key={inst.id}
                className="grid grid-cols-[1fr_1.2fr_0.8fr_0.8fr_0.9fr_auto] gap-3 items-center px-5 py-3"
              >
                <span className="text-xs font-mono text-slate-300 truncate" title={inst.instance_id}>
                  {inst.instance_id}
                </span>
                <span className="text-xs text-slate-400 truncate" title={inst.user_email}>
                  {inst.user_email}
                </span>
                <span className="text-xs text-slate-500">{inst.phone_e164 ?? "—"}</span>
                <div>
                  <StatusBadge status={inst.status} />
                </div>
                <span className="text-xs text-slate-600">{formatDate(inst.updated_at)}</span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleReconnect(inst)}
                  disabled={reconnecting.has(inst.instance_id)}
                  className="border-slate-600 text-slate-300 hover:bg-slate-700 gap-1.5 text-xs h-7 px-2.5"
                >
                  <RotateCcw size={11} className={reconnecting.has(inst.instance_id) ? "animate-spin" : ""} />
                  {reconnecting.has(inst.instance_id) ? "…" : "Reconectar"}
                </Button>
              </div>
            ))}

            {sorted.length === 0 && !isLoading && (
              <p className="px-5 py-10 text-center text-sm text-slate-500">
                Nenhuma instância encontrada.
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
