import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api, SpyAgentRun } from "@/services/api";
import { History } from "lucide-react";

const STATUS_LABELS: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  observing:  { label: "Observando", variant: "secondary" },
  analyzing:  { label: "Analisando", variant: "default" },
  completed:  { label: "Concluído", variant: "default" },
  failed:     { label: "Falhou", variant: "destructive" },
};

const MODULE_ABBR: Record<string, string> = {
  facts: "Fatos",
  identity: "Identidade",
  strategy: "Estratégia",
};

export function SpyAgentHistory() {
  const { data: runs, isLoading } = useQuery({
    queryKey: ["spy-agent-runs"],
    queryFn: () => api.spyAgent.getRuns(),
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Histórico de execuções</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {[1, 2].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </CardContent>
      </Card>
    );
  }

  if (!runs || runs.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-sm">Histórico de execuções</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {runs.map((run: SpyAgentRun) => {
          const st = STATUS_LABELS[run.status] ?? { label: run.status, variant: "outline" };
          const modules = run.modules_requested.map((m) => MODULE_ABBR[m] ?? m).join(", ");
          const dateStr = (run.completed_at || run.observation_start_at || "").slice(0, 10);

          return (
            <div key={run.run_id} className="flex items-center justify-between gap-2 py-1.5 border-b last:border-0">
              <div className="min-w-0">
                <p className="text-xs font-medium truncate">{modules || "—"}</p>
                <p className="text-xs text-muted-foreground">{dateStr}</p>
              </div>
              <Badge variant={st.variant} className="text-xs shrink-0">{st.label}</Badge>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
