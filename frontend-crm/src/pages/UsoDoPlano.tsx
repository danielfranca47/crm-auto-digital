import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useUsage } from "@/hooks/useUsage";
import { PlanLimitsCard, UsageData } from "@/components/PlanLimitsCard";
import { AlertCircle, Gauge, RefreshCw, Sparkles } from "lucide-react";

function formatLimitValue(limit: number | null | undefined) {
  if (limit === null) return "Ilimitado";
  if (limit === 0) return "Bloqueado";
  if (typeof limit === "number") return limit.toLocaleString("pt-BR");
  return "—";
}

function formatUsageValue(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("pt-BR");
}

function UsageCard({
  title,
  used,
  limit,
  remaining,
}: {
  title: string;
  used?: number | null;
  limit?: number | null;
  remaining?: number | null;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        <div className="flex items-center justify-between text-muted-foreground">
          <span>Usado</span>
          <span className="text-foreground font-semibold">{formatUsageValue(used)}</span>
        </div>
        <div className="flex items-center justify-between text-muted-foreground">
          <span>Limite</span>
          <span className="text-foreground font-semibold">{formatLimitValue(limit)}</span>
        </div>
        <div className="flex items-center justify-between text-muted-foreground">
          <span>Restante</span>
          <span className="text-foreground font-semibold">{formatUsageValue(remaining)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

export default function UsoDoPlano() {
  const { data, loading, error, refetch } = useUsage();
  const entitlements = data?.entitlements;
  const limits = (entitlements?.limits ?? {}) as Record<string, number | boolean | null | undefined>;
  const usage = data?.usage as UsageData | undefined;
  const crmProduct = entitlements?.products?.find((product) => product?.product_code === "crm");

  const dailyUsage = usage?.daily;

  return (
    <div className="p-6 space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Uso do plano</h1>
        <p className="text-muted-foreground">Acompanhe quanto ainda resta no seu plano.</p>
      </div>

      {error && (
        <Alert variant="destructive" className="max-w-2xl">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Não foi possível carregar</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button size="sm" variant="outline" onClick={refetch} disabled={loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Tentar novamente
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
                <Gauge className="h-5 w-5 text-primary" /> Resumo rápido
              </CardTitle>
              <CardDescription>Dados diretamente do backend</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {loading ? (
              <>
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-20 w-full" />
              </>
            ) : (
              <>
                <div className="rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">
                  <div className="flex items-center justify-between">
                    <span>Leads</span>
                    <span className="font-semibold text-foreground">
                      {formatUsageValue(usage?.leads?.total)} / {formatLimitValue(usage?.leads?.limit)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Restante: {formatUsageValue(usage?.leads?.remaining)}
                  </div>
                </div>
                <div className="rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">
                  <div className="flex items-center justify-between">
                    <span>Agentes locais</span>
                    <span className="font-semibold text-foreground">
                      {formatUsageValue(usage?.agents?.active)} / {formatLimitValue(usage?.agents?.limit)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Restante: {formatUsageValue(usage?.agents?.remaining)}
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-semibold">Resumo de uso</h2>
            <p className="text-sm text-muted-foreground">Valores retornados pelo backend, sem cálculos extras.</p>
          </div>
          <Button variant="outline" size="sm" onClick={refetch} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Atualizar
          </Button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, idx) => (
              <Skeleton key={idx} className="h-28 w-full" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            <UsageCard
              title="Leads"
              used={usage?.leads?.total}
              limit={usage?.leads?.limit}
              remaining={usage?.leads?.remaining}
            />
            <UsageCard
              title="Agentes locais"
              used={usage?.agents?.active}
              limit={usage?.agents?.limit}
              remaining={usage?.agents?.remaining}
            />
            {dailyUsage?.max_prospects_daily ? (
              <UsageCard
                title="Prospects do dia"
                used={dailyUsage.max_prospects_daily.used}
                limit={dailyUsage.max_prospects_daily.limit}
                remaining={dailyUsage.max_prospects_daily.remaining}
              />
            ) : null}
            {dailyUsage?.max_whatsapp_send_daily ? (
              <UsageCard
                title="WhatsApp do dia"
                used={dailyUsage.max_whatsapp_send_daily.used}
                limit={dailyUsage.max_whatsapp_send_daily.limit}
                remaining={dailyUsage.max_whatsapp_send_daily.remaining}
              />
            ) : null}
            <UsageCard
              title="Copys do mês"
              used={usage?.copy_monthly?.used}
              limit={usage?.copy_monthly?.limit}
              remaining={usage?.copy_monthly?.remaining}
            />
            {dailyUsage?.max_maps_search_daily ? (
              <UsageCard
                title="Pesquisas no Maps (dia)"
                used={dailyUsage.max_maps_search_daily.used}
                limit={dailyUsage.max_maps_search_daily.limit}
                remaining={dailyUsage.max_maps_search_daily.remaining}
              />
            ) : null}
            {dailyUsage?.max_maps_enrich_daily ? (
              <UsageCard
                title="Enriquecimentos no Maps (dia)"
                used={dailyUsage.max_maps_enrich_daily.used}
                limit={dailyUsage.max_maps_enrich_daily.limit}
                remaining={dailyUsage.max_maps_enrich_daily.remaining}
              />
            ) : null}
          </div>
        )}
      </div>

      <div className="space-y-3">
        <div>
          <h2 className="text-2xl font-semibold">Limites do plano</h2>
          <p className="text-sm text-muted-foreground">Agrupados por categoria e com uso atual quando disponível.</p>
        </div>
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : Object.keys(limits).length ? (
          <PlanLimitsCard limits={limits} usage={usage} />
        ) : (
          <p className="text-sm text-muted-foreground">Nenhum limite informado para este plano.</p>
        )}
      </div>
    </div>
  );
}
