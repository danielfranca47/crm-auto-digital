import { useState, useRef, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  ArrowLeft, Sparkles, Eye, Loader2, CheckCircle2,
  RefreshCw, QrCode, WifiOff, Undo2, ArrowRight, X,
} from "lucide-react";
import { api, SpyAgentModule, WhatsappConnectResponse } from "@/services/api";
import { SpyAgentSetup } from "@/components/agente/SpyAgentSetup";
import { SpyAgentModuleCard, type Decision } from "@/components/agente/SpyAgentModuleCard";
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

const MODULE_LABELS: Record<string, string> = {
  facts: "Complementação de Fatos",
  identity: "Identidade e Tom",
  strategy: "Estratégia de Vendas",
};

// ─── Types ────────────────────────────────────────────────────────────────────

interface SuggestionState {
  status: Decision;
  module: string;
  value: unknown;
}

interface HistoryEntry {
  field: string;
  module: string;
  value: unknown;
  from: Decision;
  to: Decision;
  batch?: boolean; // true = this entry represents many fields
  batchFields?: string[]; // fields included in the batch
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function SpyAgent() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // 3-state decisions: pending | accepted | rejected
  const [decisions, setDecisions] = useState<Record<string, SuggestionState>>({});
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  // Permite fechar a análise concluída e voltar ao ecrã de setup
  const [dismissed, setDismissed] = useState(false);

  // Reconexão do fone espião
  const [reconnecting, setReconnecting] = useState(false);
  const [reconnectData, setReconnectData] = useState<WhatsappConnectResponse | null>(null);
  const [reconnectQrExpired, setReconnectQrExpired] = useState(false);
  const reconnectPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (reconnectPollRef.current) clearInterval(reconnectPollRef.current);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, []);

  const stopReconnectTimers = () => {
    if (reconnectPollRef.current) { clearInterval(reconnectPollRef.current); reconnectPollRef.current = null; }
    if (reconnectTimeoutRef.current) { clearTimeout(reconnectTimeoutRef.current); reconnectTimeoutRef.current = null; }
  };

  const startReconnectPolling = () => {
    stopReconnectTimers();
    reconnectTimeoutRef.current = setTimeout(() => {
      setReconnectQrExpired(true);
      stopReconnectTimers();
    }, 90_000);

    reconnectPollRef.current = setInterval(async () => {
      try {
        const s = await api.spyAgent.reconnectStatus();
        if (s.status === "connected") {
          stopReconnectTimers();
          setReconnectData(null);
          setReconnectQrExpired(false);
          toast({ title: "Fone espião reconectado!", description: "As mensagens voltarão a ser capturadas." });
          queryClient.invalidateQueries({ queryKey: ["spy-instance-config"] });
        }
      } catch {
        // ignora erros pontuais
      }
    }, 3_000);
  };

  const handleReconnect = async () => {
    setReconnecting(true);
    setReconnectQrExpired(false);
    try {
      const resp = await api.spyAgent.reconnect();
      if (resp.qr?.value) {
        setReconnectData(resp);
        startReconnectPolling();
      } else if (resp.status === "connected") {
        toast({ title: "Fone espião já conectado!", description: "Nenhuma ação necessária." });
      } else {
        toast({ title: "Erro ao gerar QR code", description: "Tente novamente.", variant: "destructive" });
      }
    } catch {
      toast({ title: "Erro ao reconectar fone espião", variant: "destructive" });
    } finally {
      setReconnecting(false);
    }
  };

  const handleRefreshReconnectQr = async () => {
    setReconnectQrExpired(false);
    setReconnecting(true);
    try {
      const resp = await api.spyAgent.reconnect();
      if (resp.qr?.value) {
        setReconnectData(resp);
        startReconnectPolling();
      }
    } catch {
      toast({ title: "Erro ao renovar QR code", variant: "destructive" });
    } finally {
      setReconnecting(false);
    }
  };

  const handleCancelReconnect = () => {
    stopReconnectTimers();
    setReconnectData(null);
    setReconnectQrExpired(false);
  };

  const getQrSrc = (qr: WhatsappConnectResponse["qr"]): string | null => {
    if (!qr?.value) return null;
    if (qr.kind === "url") return qr.value;
    if (qr.kind === "base64") return `data:image/png;base64,${qr.value}`;
    if (qr.value.startsWith("data:image")) return qr.value;
    if (qr.value.length > 80) return `data:image/png;base64,${qr.value}`;
    return null;
  };

  const { data: session, isLoading: sessionLoading } = useQuery({
    queryKey: ["spy-agent-session"],
    queryFn: () => api.spyAgent.getSession(),
    refetchInterval: (query) => {
      const status = (query.state.data as any)?.status;
      return status === "observing" || status === "analyzing" ? 15000 : false;
    },
  });

  const status = (session as any)?.status ?? "not_started";
  // Se o utilizador fechou a análise sem aplicar, mostrar o ecrã de setup
  const effectiveStatus = dismissed ? "not_started" : status;
  const st = STATUS_LABELS[effectiveStatus] ?? STATUS_LABELS.not_started;

  const { data: sample } = useQuery({
    queryKey: ["spy-agent-sample"],
    queryFn: () => api.spyAgent.getConversationSample(),
    enabled: !session || effectiveStatus === "not_started",
  });

  // Helper: all suggestions flat
  const allSuggestions: Array<{ module: string; field: string; value: unknown }> = (
    (session as any)?.module_results ?? []
  ).flatMap((r: any) =>
    r.suggestions.map((s: any) => ({ module: r.module, field: s.field, value: s.suggested_value }))
  );

  // Derived counts
  const acceptedEntries = Object.entries(decisions).filter(([, v]) => v.status === "accepted");
  const acceptedCount = acceptedEntries.length;
  const hasAnyDecision = Object.values(decisions).some((v) => v.status !== "pending");

  // ─── Decision actions ──────────────────────────────────────────────────────

  const decide = (field: string, newStatus: Decision, module: string, value: unknown) => {
    const from = decisions[field]?.status ?? "pending";
    if (from === newStatus) return; // no change
    setHistory((h) => [...h, { field, module, value, from, to: newStatus }]);
    setDecisions((prev) => ({
      ...prev,
      [field]: { status: newStatus, module, value },
    }));
  };

  const undoLast = () => {
    setHistory((h) => {
      if (h.length === 0) return h;
      const last = h[h.length - 1];
      const rest = h.slice(0, -1);

      if (last.batch && last.batchFields) {
        // Undo batch: revert all fields to their "from" state
        setDecisions((prev) => {
          const next = { ...prev };
          // We stored individual "from" states as consecutive history entries
          // For batch, we store batchFields — restore each to "pending" (they were all pending before batch)
          for (const f of last.batchFields!) {
            if (next[f]?.status === last.to) {
              if (last.from === "pending") {
                delete next[f];
              } else {
                next[f] = { ...next[f], status: last.from };
              }
            }
          }
          return next;
        });
      } else {
        setDecisions((prev) => {
          const next = { ...prev };
          if (last.from === "pending") {
            delete next[last.field];
          } else {
            next[last.field] = { status: last.from, module: last.module, value: last.value };
          }
          return next;
        });
      }

      return rest;
    });
  };

  const acceptAll = (moduleId?: string) => {
    const targets = moduleId
      ? allSuggestions.filter((s) => s.module === moduleId)
      : allSuggestions;
    if (targets.length === 0) return;

    const batchFields = targets.map((s) => s.field);
    // Record as a single batch undo entry
    const batchEntry: HistoryEntry = {
      field: "__batch__",
      module: moduleId ?? "__all__",
      value: null,
      from: "pending",
      to: "accepted",
      batch: true,
      batchFields,
    };
    setHistory((h) => [...h, batchEntry]);
    setDecisions((prev) => {
      const next = { ...prev };
      for (const s of targets) {
        next[s.field] = { status: "accepted", module: s.module, value: s.value };
      }
      return next;
    });
  };

  const rejectAll = (moduleId?: string) => {
    const targets = moduleId
      ? allSuggestions.filter((s) => s.module === moduleId)
      : allSuggestions;
    if (targets.length === 0) return;

    const batchFields = targets.map((s) => s.field);
    const batchEntry: HistoryEntry = {
      field: "__batch__",
      module: moduleId ?? "__all__",
      value: null,
      from: "pending",
      to: "rejected",
      batch: true,
      batchFields,
    };
    setHistory((h) => [...h, batchEntry]);
    setDecisions((prev) => {
      const next = { ...prev };
      for (const s of targets) {
        next[s.field] = { status: "rejected", module: s.module, value: s.value };
      }
      return next;
    });
  };

  // ─── Apply ────────────────────────────────────────────────────────────────

  const handleApply = async () => {
    if (!session || (session as any).status !== "completed") return;
    if (acceptedCount === 0) return;

    const run_id = (session as any).run_id;
    const accepted_suggestions = acceptedEntries.map(([field, { module, value }]) => ({
      module: module as SpyAgentModule,
      field,
      value,
    }));

    setApplying(true);
    try {
      const res = await api.spyAgent.apply({ run_id, accepted_suggestions });
      setApplied(true);
      setDecisions({});
      setHistory([]);
      setShowPreview(false);
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
    setDismissed(false);
    queryClient.invalidateQueries({ queryKey: ["spy-agent-session"] });
    queryClient.invalidateQueries({ queryKey: ["spy-agent-runs"] });
    queryClient.invalidateQueries({ queryKey: ["spy-agent-sample"] });
  };

  // ─── Preview data ─────────────────────────────────────────────────────────

  // Group accepted suggestions by module for the preview dialog
  const previewByModule: Array<{
    module: string;
    label: string;
    items: Array<{ field: string; current: unknown; suggested: unknown }>;
  }> = [];

  for (const result of (session as any)?.module_results ?? []) {
    const accepted = result.suggestions.filter(
      (s: any) => decisions[s.field]?.status === "accepted"
    );
    if (accepted.length === 0) continue;
    previewByModule.push({
      module: result.module,
      label: MODULE_LABELS[result.module] ?? result.module,
      items: accepted.map((s: any) => ({
        field: s.field,
        current: s.current_value,
        suggested: s.suggested_value,
      })),
    });
  }

  // ─── Render ───────────────────────────────────────────────────────────────

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
          {session && effectiveStatus !== "not_started" && (
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

        {/* === NÃO INICIADO === */}
        {!sessionLoading && effectiveStatus === "not_started" && (
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

        {/* === OBSERVANDO === */}
        {!sessionLoading && effectiveStatus === "observing" && session && (
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
                    day: "2-digit", month: "2-digit", year: "numeric",
                    hour: "2-digit", minute: "2-digit",
                  })}
                </span>
              </p>
            </div>

            {/* Painel de reconexão do fone espião */}
            {reconnectData ? (
              <div className="rounded-xl border border-border bg-muted/20 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium flex items-center gap-1.5">
                    <QrCode className="h-3.5 w-3.5 text-primary" />
                    Escaneie com o fone espião para reconectar:
                  </p>
                  <Button size="sm" variant="ghost" className="h-6 px-2 text-xs text-muted-foreground" onClick={handleCancelReconnect}>
                    Cancelar
                  </Button>
                </div>
                {reconnectQrExpired ? (
                  <div className="flex flex-col items-center gap-3 py-2">
                    <p className="text-xs text-muted-foreground text-center">QR code expirado. Gere um novo.</p>
                    <Button size="sm" variant="outline" className="gap-1.5" onClick={handleRefreshReconnectQr} disabled={reconnecting}>
                      {reconnecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                      Novo QR code
                    </Button>
                  </div>
                ) : (() => {
                  const src = getQrSrc(reconnectData.qr);
                  return src ? (
                    <div className="flex flex-col items-center gap-2">
                      <img
                        src={src}
                        alt="QR Code WhatsApp"
                        className="w-48 h-48 rounded border border-border bg-white object-contain"
                      />
                      <div className="text-[10px] text-muted-foreground text-center space-y-0.5">
                        <p>1. Abra o WhatsApp no fone de observação</p>
                        <p>2. Vá em Menu → Aparelhos conectados</p>
                        <p>3. Escaneie este código</p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                        <span className="text-[10px] text-muted-foreground">Aguardando leitura...</span>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-2 py-2">
                      <p className="text-xs text-muted-foreground">QR code em formato não suportado.</p>
                      <Button size="sm" variant="outline" className="gap-1.5" onClick={handleRefreshReconnectQr} disabled={reconnecting}>
                        <RefreshCw className="h-3.5 w-3.5" /> Tentar novamente
                      </Button>
                    </div>
                  );
                })()}
              </div>
            ) : (
              <div className="flex items-center justify-between rounded-lg border border-yellow-500/30 bg-yellow-500/5 px-4 py-3">
                <div className="flex items-center gap-2">
                  <WifiOff className="h-4 w-4 text-yellow-500 shrink-0" />
                  <p className="text-xs text-muted-foreground">
                    Fone desconectou? Reconecte sem perder os dados coletados.
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5 shrink-0 ml-3"
                  onClick={handleReconnect}
                  disabled={reconnecting}
                >
                  {reconnecting
                    ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Aguarde...</>
                    : <><QrCode className="h-3.5 w-3.5" /> Reconectar</>}
                </Button>
              </div>
            )}

            <SpyAgentHistory />
          </>
        )}

        {/* === ANALISANDO === */}
        {!sessionLoading && effectiveStatus === "analyzing" && (
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

        {/* === CONCLUÍDO — sugestões === */}
        {!sessionLoading && effectiveStatus === "completed" && session && (
          <>
            {/* Título + ações globais */}
            <div className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">Sugestões do Agente Espião</h2>
                  <p className="text-sm text-muted-foreground">
                    Selecione as sugestões que deseja aplicar no AI Profile.
                  </p>
                </div>
                {applied && (
                  <Badge variant="default" className="gap-1 shrink-0 mt-1">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Aplicado
                  </Badge>
                )}
              </div>

              {/* Barra de ações globais */}
              <div className="flex items-center justify-between gap-2 rounded-lg border bg-muted/20 px-3 py-2">
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-green-600 hover:text-green-700 hover:bg-green-50 gap-1"
                    onClick={() => acceptAll()}
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Aceitar todas
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-destructive/70 hover:text-destructive hover:bg-destructive/5 gap-1"
                    onClick={() => rejectAll()}
                  >
                    <X className="h-3.5 w-3.5" />
                    Recusar todas
                  </Button>
                </div>
                {history.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-muted-foreground hover:text-foreground gap-1"
                    onClick={undoLast}
                  >
                    <Undo2 className="h-3.5 w-3.5" />
                    Desfazer ({history.length})
                  </Button>
                )}
              </div>
            </div>

            {/* Cards de módulos */}
            {((session as any).module_results ?? []).map((result: any) => (
              <SpyAgentModuleCard
                key={result.module}
                result={result}
                decisions={Object.fromEntries(
                  Object.entries(decisions)
                    .filter(([, v]) => v.module === result.module)
                    .map(([k, v]) => [k, v.status])
                )}
                onDecide={(field, decision, value) =>
                  decide(field, decision, result.module, value)
                }
                onAcceptAll={(moduleId) => acceptAll(moduleId)}
                onRejectAll={(moduleId) => rejectAll(moduleId)}
              />
            ))}

            {/* Relatório de compatibilidade */}
            {(session as any).compatibility_report && (
              <CompatibilityReportPanel
                report={(session as any).compatibility_report}
                runId={(session as any).run_id}
              />
            )}

            {/* Botão de pré-visualização / aplicar */}
            {!applied && (
              <div className="space-y-2">
                <Button
                  className="w-full gap-2"
                  size="lg"
                  disabled={acceptedCount === 0}
                  onClick={() => setShowPreview(true)}
                >
                  <ArrowRight className="h-4 w-4" />
                  {acceptedCount === 0
                    ? "Selecione sugestões para continuar"
                    : `Pré-visualizar ${acceptedCount} aceite(s)`}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full text-muted-foreground hover:text-foreground text-xs"
                  onClick={() => {
                    setDismissed(true);
                    setDecisions({});
                    setHistory([]);
                  }}
                >
                  Finalizar sem aplicar
                </Button>
              </div>
            )}

            <SpyAgentHistory />
          </>
        )}

        {/* === FALHOU === */}
        {!sessionLoading && effectiveStatus === "failed" && (
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

      {/* ─── Dialog de Preview / Confirmação ─────────────────────────────────── */}
      <Dialog open={showPreview} onOpenChange={setShowPreview}>
        <DialogContent className="max-w-lg max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Confirmar alterações ao AI Profile</DialogTitle>
            <p className="text-sm text-muted-foreground">
              {acceptedCount} campo(s) serão actualizados:
            </p>
          </DialogHeader>

          {/* Lista de mudanças agrupada por módulo */}
          <div className="flex-1 overflow-y-auto space-y-4 py-2 pr-1">
            {previewByModule.map((group) => (
              <div key={group.module} className="space-y-2">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  {group.label}
                </p>
                {group.items.map((item) => (
                  <div key={item.field} className="rounded-lg border bg-muted/20 p-3 space-y-1">
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                      {item.field}
                    </code>
                    {item.current !== null && item.current !== undefined && (
                      <p className="text-xs text-muted-foreground line-through">
                        {JSON.stringify(item.current)}
                      </p>
                    )}
                    <p className="text-xs font-semibold text-foreground">
                      → {JSON.stringify(item.suggested)}
                    </p>
                  </div>
                ))}
              </div>
            ))}
          </div>

          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="outline"
              onClick={() => setShowPreview(false)}
              disabled={applying}
            >
              Voltar
            </Button>
            <Button onClick={handleApply} disabled={applying} className="gap-1.5">
              {applying ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Aplicando...</>
              ) : (
                <><CheckCircle2 className="h-4 w-4" /> Confirmar e aplicar</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

