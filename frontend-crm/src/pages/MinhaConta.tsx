import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useUsage } from "@/hooks/useUsage";
import { api } from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { AlertCircle, CalendarDays, CheckCircle2, Gauge, RefreshCw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

function formatLimitLabel(key: string) {
  return key
    .replace(/_/g, " ")
    .replace(/\b(\w)/g, (match) => match.toUpperCase())
    .trim();
}

function formatLimitValue(value: number | null | undefined) {
  if (value === null || value === undefined) return "Ilimitado";
  if (value === 0) return "Bloqueado";
  return value.toLocaleString("pt-BR");
}

export default function MinhaConta() {
  const { data, loading, error, refetch } = useUsage();
  const { toast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const [gcalStatus, setGcalStatus] = useState<{ connected: boolean; email: string | null } | null>(null);
  const [gcalLoading, setGcalLoading] = useState(false);
  const [gcalConnecting, setGcalConnecting] = useState(false);

  const fetchGcalStatus = useCallback(async () => {
    try {
      const status = await api.googleCalendar.getStatus();
      setGcalStatus(status);
    } catch {
      // endpoint pode retornar 503 se não configurado — silencioso
    }
  }, []);

  useEffect(() => {
    fetchGcalStatus();
  }, [fetchGcalStatus]);

  useEffect(() => {
    const connected = searchParams.get("google_connected");
    const errParam = searchParams.get("google_error");
    if (connected === "1") {
      toast({ title: "Google Calendar conectado com sucesso!" });
      fetchGcalStatus();
      setSearchParams({}, { replace: true });
    } else if (errParam === "1") {
      toast({ title: "Erro ao conectar Google Calendar", variant: "destructive" });
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams, toast, fetchGcalStatus]);

  async function handleGcalConnect() {
    setGcalConnecting(true);
    try {
      const url = await api.googleCalendar.connectUrl();
      window.location.href = url;
    } catch {
      toast({ title: "Não foi possível iniciar a conexão com o Google", variant: "destructive" });
      setGcalConnecting(false);
    }
  }

  async function handleGcalDisconnect() {
    setGcalLoading(true);
    try {
      await api.googleCalendar.disconnect();
      setGcalStatus({ connected: false, email: null });
      toast({ title: "Google Calendar desconectado" });
    } catch {
      toast({ title: "Erro ao desconectar", variant: "destructive" });
    } finally {
      setGcalLoading(false);
    }
  }
  const entitlements = data?.entitlements;
  const crmProduct = entitlements?.products?.find(
    (product) => product?.product_code === "crm"
  );
  const limits = entitlements?.limits ?? {};

  return (
    <div className="p-6 space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Minha conta</h1>
        <p className="text-muted-foreground">
          Consulte rapidamente seu plano atual e os limites disponíveis.
        </p>
      </div>

      {error && (
        <Alert variant="destructive" className="max-w-2xl">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Não foi possível carregar</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button size="sm" variant="outline" onClick={refetch}>
              <RefreshCw className="mr-2 h-4 w-4" /> Tentar novamente
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-xl">
                <Sparkles className="h-5 w-5 text-primary" /> Plano atual
              </CardTitle>
              <CardDescription>Detalhes do produto CRM</CardDescription>
            </div>
            <Button size="icon" variant="ghost" onClick={refetch} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <div className="space-y-2">
                <Skeleton className="h-6 w-40" />
                <Skeleton className="h-4 w-24" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-semibold capitalize">
                  {crmProduct?.plan_code || "Sem plano"}
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Badge variant={crmProduct?.status === "active" ? "default" : "secondary"}>
                    {crmProduct?.status ?? "indefinido"}
                  </Badge>
                  <span>Produto: CRM</span>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-xl">
                <Gauge className="h-5 w-5 text-primary" /> Limites do meu plano
              </CardTitle>
              <CardDescription>Valores diretamente do backend</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            ) : Object.keys(limits).length ? (
              <div className="space-y-2">
                {Object.entries(limits).map(([key, value]) => (
                  <div
                    key={key}
                    className="flex items-center justify-between rounded-md border bg-muted/40 px-3 py-2"
                  >
                    <div className="text-sm font-medium text-muted-foreground">
                      {formatLimitLabel(key)}
                    </div>
                    <div className="text-sm font-semibold">
                      {formatLimitValue(value)}
                      {value === 0 ? (
                        <span className="ml-2 text-xs text-muted-foreground">(bloqueado)</span>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Nenhum limite informado para este plano.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Google Calendar */}
      <Card className="max-w-2xl">
        <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-xl">
              <CalendarDays className="h-5 w-5 text-primary" /> Google Calendar
            </CardTitle>
            <CardDescription>
              Sincronize os seus compromissos automaticamente com o Google Agenda.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          {gcalStatus === null ? (
            <Skeleton className="h-10 w-48" />
          ) : gcalStatus.connected ? (
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
                <div>
                  <p className="text-sm font-medium">Conectado</p>
                  {gcalStatus.email && (
                    <p className="text-xs text-muted-foreground">{gcalStatus.email}</p>
                  )}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleGcalDisconnect}
                disabled={gcalLoading}
              >
                {gcalLoading ? "Desconectando…" : "Desconectar"}
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <p className="text-sm text-muted-foreground">
                Não conectado. Ao conectar, cada novo compromisso criado no CRM será
                adicionado automaticamente ao seu Google Calendar.
              </p>
              <Button
                size="sm"
                className="w-fit"
                onClick={handleGcalConnect}
                disabled={gcalConnecting}
              >
                {gcalConnecting ? "Redirecionando…" : "Conectar Google Calendar"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
