import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, Sparkles, Eye, Loader2, CheckCircle2 } from "lucide-react";
import { api, SpyAgentModule } from "@/services/api";
import { SpyAgentSetup } from "@/components/agente/SpyAgentSetup";
import { SpyAgentModuleCard } from "@/components/agente/SpyAgentModuleCard";
import { CompatibilityReportPanel } from "@/components/agente/CompatibilityReportPanel";
import { SpyAgentHistory } from "@/components/agente/SpyAgentHistory";
import { useToast } from "@/hooks/use-toast";

const STATUS_LABELS: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  not_started: { label: "Não iniciado", icon: null, color: "text-muted-foreground" },
  observing:   { label: "Observando", icon: <Eye className="h-4 w-4" />, color: "text-blue-500" },
  analyzing:   { label: "Analisando", icon: <Loader2 className="h-4 w-4 animate-spin" />, color: "text-primary" },
  completed:   { label: "Análise concluída", icon: <CheckCircle2 className="h-4 w-4" />, color: "text-green-500" },
  failed:      { label: "Falhou", icon: null, color: "text-destructive" },
};

export default function SpyAgent() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // accepted: { [field]: { module, value } }
  const [accepted, setAccepted] = useState<Record<string, { module: string; value: unknown }>>({});
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  const { data: session, isLoading: sessionLoading } = useQuery({
    queryKey: ["spy-agent-session"],
    queryFn: () => api.spyAgent.getSession(),
    refetchInterval: (query) => {
      const status = (query.state.data as any)?.status;
      return status === "observing" || status === "analyzing" ? 15000 : false;
    },
  });

  const { data: sample } = useQuery({
    queryKey: ["spy-agent-sample"],
    queryFn: () => api.spyAgent.getConversationSample(),
    enabled: !session || (session as any).status === "not_started",
  });

  const status = (session as any)?.status ?? "not_started";
  const st = STATUS_LABELS[status] ?? STATUS_LABELS.not_started;

  const toggleSuggestion = (module: string, field: string, value: unknown) => {
    setAccepted((prev) => {
      const next = { ...prev };
      if (next[field]) {
        delete next[field];
      } else {
        next[field] = { module, value };
      }
      return next;
    });
  };

  const handleApply = async () => {
    if (!session || (session as any).status !== "completed") return;
    const run_id = (session as any).run_id;

    const accepted_suggestions = Object.entries(accepted).map(([field, { module, value }]) => ({
      module: module as SpyAgentModule,
      field,
      value,
    }));

    if (accepted_suggestions.length === 0) {
      toast({ title: "Selecione pelo menos uma sugestão para aplicar", variant: "destructive" });
      return;
    }

    setApplying(true);
    try {
      const res = await api.spyAgent.apply({ run_id, accepted_suggestions });
      setApplied(true);
      setAccepted({});
      toast({
        title: "Sugestões aplicadas!",
        description: `${res.fields_updated.length} campo(s) atualizados no AI Profile.`,
      });
      queryClient.invalidateQueries({ queryKey: ["spy-agent-session"] });
    } catch {
      toast({ title: "Erro ao aplicar sugestões", variant: "destructive" });
    } finally {
      setApplying(false);
    }
  };

  const handleStarted = () => {
    queryClient.invalidateQueries({ queryKey: ["spy-agent-session"] });
    queryClient.invalidateQueries({ queryKey: ["spy-agent-runs"] });
    queryClient.invalidateQueries({ queryKey: ["spy-agent-sample"] });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b bg-background sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center gap-3">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Sparkles className="h-5 w-5 text-primary shrink-0" />
            <h1 className="font-semibold truncate">Agente Espião</h1>
            <Badge variant="secondary" className="text-xs shrink-0">Premium</Badge>
          </div>
          {session && status !== "not_started" && (
            <div className={`flex items-center gap-1.5 text-xs font-medium ${st.color}`}>
              {st.icon}
              <span>{st.label}</span>
            </div>
          )}
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">

        {sessionLoading && (
          <div className="space-y-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        )}

        {/* === NÃO INICIADO — mostrar setup === */}
        {!sessionLoading && status === "not_started" && (
          <>
            <div className="space-y-1">
              <h2 className="text-lg font-semibold">Configure o Agente Espião</h2>
              <p className="text-sm text-muted-foreground">
                O agente observa suas conversas reais de WhatsApp durante o período escolhido
                e, ao término, aprende automaticamente a configurar seu AI Profile.
              </p>
            </div>
            <SpyAgentSetup sample={sample ?? null} onStarted={handleStarted} />
            <SpyAgentHistory />
          </>
        )}

        {/* === OBSERVANDO — countdown === */}
        {!sessionLoading && status === "observing" && session && (
          <>
            <div className="rounded-xl border bg-muted/30 p-5 space-y-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-blue-500/10 flex items-center justify-center shrink-0">
                  <Eye className="h-5 w-5 text-blue-500" />
                </div>
                <div>
                  <p className="font-semibold">Observação em andamento</p>
                  <p className="text-sm text-muted-foreground">
                    O sistema está coletando dados das suas conversas silenciosamente.
                  </p>
                </div>
              </div>

              {/* Barra de progresso */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Progresso</span>
                  <span>{(session as any).progress_pct ?? 0}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full transition-all"
                    style={{ width: `${(session as any).progress_pct ?? 0}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg bg-background border p-3">
                  <p className="text-xl font-bold">{(session as any).days_elapsed ?? 0}</p>
                  <p className="text-xs text-muted-foreground">dias passados</p>
                </div>
                <div className="rounded-lg bg-background border p-3">
                  <p className="text-xl font-bold text-blue-500">{(session as any).days_remaining ?? 0}</p>
                  <p className="text-xs text-muted-foreground">dias restantes</p>
                </div>
                <div className="rounded-lg bg-background border p-3">
                  <p className="text-xl font-bold">{(session as any).leads_collected_so_far ?? 0}</p>
                  <p className="text-xs text-muted-foreground">leads coletados</p>
                </div>
              </div>

              <p className="text-xs text-muted-foreground text-center">
                Previsão de conclusão:{" "}
                <span className="font-medium">
                  {new Date((session as any).observation_end_at).toLocaleString("pt-BR", {
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </p>
            </div>
            <SpyAgentHistory />
          </>
        )}

        {/* === ANALISANDO === */}
        {!sessionLoading && status === "analyzing" && (
          <div className="rounded-xl border bg-muted/30 p-8 text-center space-y-4">
            <Loader2 className="h-10 w-10 text-primary mx-auto animate-spin" />
            <div>
              <p className="font-semibold">Analisando suas conversas...</p>
              <p className="text-sm text-muted-foreground mt-1">
                O Agente Espião está processando os dados coletados. Isso pode levar alguns minutos.
              </p>
            </div>
          </div>
        )}

        {/* === CONCLUÍDO — mostrar sugestões === */}
        {!sessionLoading && status === "completed" && session && (
          <>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Sugestões do Agente Espião</h2>
                <p className="text-sm text-muted-foreground">
                  Selecione as sugestões que deseja aplicar no AI Profile.
                </p>
              </div>
              {Object.keys(accepted).length > 0 && !applied && (
                <Button onClick={handleApply} disabled={applying} size="sm">
                  {applying ? (
                    <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> Aplicando...</>
                  ) : (
                    <>Aplicar {Object.keys(accepted).length} selecionada(s)</>
                  )}
                </Button>
              )}
              {applied && (
                <Badge variant="default" className="gap-1">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Aplicado
                </Badge>
              )}
            </div>

            {/* Cards de módulos */}
            {((session as any).module_results ?? []).map((result: any) => (
              <SpyAgentModuleCard
                key={result.module}
                result={result}
                acceptedFields={new Set(Object.keys(accepted))}
                onToggle={(field, value) => toggleSuggestion(result.module, field, value)}
              />
            ))}

            {/* Relatório de compatibilidade */}
            {(session as any).compatibility_report && (
              <CompatibilityReportPanel
                report={(session as any).compatibility_report}
                runId={(session as any).run_id}
              />
            )}

            {/* Botão aplicar no final (repetido para conveniência) */}
            {Object.keys(accepted).length > 0 && !applied && (
              <Button className="w-full" onClick={handleApply} disabled={applying} size="lg">
                {applying ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Aplicando...</>
                ) : (
                  <>Aplicar {Object.keys(accepted).length} sugestão(ões) selecionada(s)</>
                )}
              </Button>
            )}

            <SpyAgentHistory />
          </>
        )}

        {/* === FALHOU === */}
        {!sessionLoading && status === "failed" && (
          <>
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center space-y-3">
              <p className="font-semibold text-destructive">A análise falhou</p>
              <p className="text-sm text-muted-foreground">
                Não foi possível concluir a análise. Verifique se há conversas suficientes e tente novamente.
              </p>
              <Button variant="outline" onClick={() => handleStarted()}>
                Tentar novamente
              </Button>
            </div>
            <SpyAgentSetup sample={sample ?? null} onStarted={handleStarted} />
          </>
        )}
      </div>
    </div>
  );
}
