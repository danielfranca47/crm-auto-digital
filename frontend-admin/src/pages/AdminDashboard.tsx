import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import { Users, Wifi, WifiOff, CreditCard, AlertTriangle, RefreshCw } from "lucide-react";

function KpiCard({
  title,
  value,
  icon: Icon,
  accent = "text-slate-200",
}: {
  title: string;
  value: number | string;
  icon: React.ElementType;
  accent?: string;
}) {
  return (
    <Card className="bg-slate-800/60 border-slate-700">
      <CardContent className="p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs text-slate-400 uppercase tracking-wide">{title}</p>
          <Icon size={16} className="text-slate-500" />
        </div>
        <p className={`text-3xl font-bold ${accent}`}>{value}</p>
      </CardContent>
    </Card>
  );
}

function statusIsOnline(status: string) {
  return status === "active" || status === "connected";
}

export default function AdminDashboard() {
  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats,
  } = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: () => api.getStats(),
    staleTime: 30_000,
  });

  const { data: instances, isLoading: instancesLoading } = useQuery({
    queryKey: ["admin", "instances"],
    queryFn: () => api.listInstances(),
    staleTime: 30_000,
  });

  const offlineInstances = instances?.filter((i) => !statusIsOnline(i.status)) ?? [];
  const isLoading = statsLoading || instancesLoading;

  return (
    <div className="p-6 max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-200">Dashboard</h1>
          <p className="text-slate-500 text-sm">Visão geral do sistema.</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetchStats()}
          disabled={isLoading}
          className="border-slate-700 text-slate-400 hover:bg-slate-800 gap-1.5"
        >
          <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
          Atualizar
        </Button>
      </div>

      {statsError && (
        <div className="rounded-lg bg-red-950/40 border border-red-800/50 px-4 py-3 text-sm text-red-400">
          Erro ao carregar estatísticas. Verifique o token admin.
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          title="Usuários"
          value={statsLoading ? "—" : (stats?.total_users ?? 0)}
          icon={Users}
        />
        <KpiCard
          title="Assinaturas ativas"
          value={statsLoading ? "—" : (stats?.active_subscriptions ?? 0)}
          icon={CreditCard}
          accent="text-indigo-400"
        />
        <KpiCard
          title="Instâncias online"
          value={statsLoading ? "—" : (stats?.instances_online ?? 0)}
          icon={Wifi}
          accent="text-emerald-400"
        />
        <KpiCard
          title="Instâncias offline"
          value={statsLoading ? "—" : (stats?.instances_offline ?? 0)}
          icon={WifiOff}
          accent={stats && stats.instances_offline > 0 ? "text-amber-400" : "text-slate-200"}
        />
      </div>

      {stats && stats.subscriptions_by_plan.length > 0 && (
        <Card className="bg-slate-800/60 border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">Assinaturas por plano</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2 pb-4">
            {stats.subscriptions_by_plan.map((row) => (
              <Badge
                key={row.plan}
                variant="secondary"
                className="bg-indigo-900/40 text-indigo-300 border-indigo-700/40 text-xs"
              >
                {row.plan}: {row.count}
              </Badge>
            ))}
          </CardContent>
        </Card>
      )}

      {offlineInstances.length > 0 && (
        <Card className="bg-amber-950/30 border-amber-800/40">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-amber-400 flex items-center gap-2">
              <AlertTriangle size={14} />
              {offlineInstances.length} instância{offlineInstances.length > 1 ? "s" : ""} offline
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-amber-900/30">
              {offlineInstances.map((inst) => (
                <div key={inst.id} className="flex items-center justify-between px-5 py-2.5">
                  <div>
                    <p className="text-sm text-slate-300 font-mono">{inst.instance_id}</p>
                    <p className="text-xs text-slate-500">{inst.user_email}</p>
                  </div>
                  <Badge className="bg-amber-900/50 text-amber-300 border-amber-700/50 text-xs">
                    {inst.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {offlineInstances.length === 0 && !isLoading && (
        <div className="rounded-lg bg-emerald-950/30 border border-emerald-800/30 px-4 py-3 text-sm text-emerald-400">
          Todas as instâncias estão online.
        </div>
      )}
    </div>
  );
}
