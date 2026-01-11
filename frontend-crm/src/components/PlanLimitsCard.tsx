import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type UsageDailyEntry = {
  used?: number | null;
  limit?: number | null;
  remaining?: number | null;
};

export type UsageData = {
  leads?: { total?: number | null; limit?: number | null; remaining?: number | null };
  agents?: { active?: number | null; limit?: number | null; remaining?: number | null };
  copy_monthly?: { used?: number | null; limit?: number | null; remaining?: number | null };
  daily?: Record<string, UsageDailyEntry>;
  [key: string]: unknown;
};

type LimitValue = number | boolean | null | undefined;

type PlanLimitsCardProps = {
  limits: Record<string, LimitValue>;
  usage?: UsageData;
};

const LABELS: Record<string, string> = {
  max_leads: "Leads",
  max_agents_local: "Agentes locais",
  max_prospects_daily: "Prospects do dia",
  max_whatsapp_send_daily: "Envios WhatsApp do dia",
  max_maps_search_daily: "Pesquisas no Maps (dia)",
  max_maps_enrich_daily: "Enriquecimentos no Maps (dia)",
  max_copy_generation_monthly: "Copys do mês",
  max_prospec_monthly: "Prospecções do mês",
  max_pesquisa_turbo_monthly: "Pesquisas turbo do mês",
  max_ia_conversas_monthly: "Conversas Conversational AI do mês",
  require_agent_local_activation_fee: "Taxa de ativação de agente local",
  ia_memory_advanced: "Memória avançada de IA",
};

const FIXED_KEYS = ["max_leads", "max_agents_local"] as const;
const DAILY_KEYS = [
  "max_prospects_daily",
  "max_whatsapp_send_daily",
  "max_maps_search_daily",
  "max_maps_enrich_daily",
] as const;
const MONTHLY_KEYS = [
  "max_copy_generation_monthly",
  "max_prospec_monthly",
  "max_pesquisa_turbo_monthly",
  "max_ia_conversas_monthly",
] as const;
const FEATURE_KEYS = [
  "require_agent_local_activation_fee",
  "ia_memory_advanced",
] as const;

function formatLimitValue(limit: LimitValue) {
  if (limit === null) return "Ilimitado";
  if (limit === 0) return "Bloqueado";
  if (typeof limit === "number") return limit.toLocaleString("pt-BR");
  return "—";
}

function formatUsageValue(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("pt-BR");
}

function getUsageInfo(key: string, usage?: UsageData) {
  if (!usage) return {};

  if (key === "max_leads") {
    return { used: usage.leads?.total ?? undefined, remaining: usage.leads?.remaining };
  }

  if (key === "max_agents_local") {
    return { used: usage.agents?.active ?? undefined, remaining: usage.agents?.remaining };
  }

  if (key === "max_copy_generation_monthly") {
    return {
      used: usage.copy_monthly?.used ?? undefined,
      remaining: usage.copy_monthly?.remaining,
    };
  }

  const dailyUsage = usage.daily?.[key];
  if (dailyUsage) {
    return { used: dailyUsage.used ?? undefined, remaining: dailyUsage.remaining };
  }

  return {};
}

function shouldRenderKey(key: string, limits: Record<string, LimitValue>, usage?: UsageData) {
  const limitValue = limits?.[key];
  const usageInfo = getUsageInfo(key, usage);
  const hasUsage = usageInfo.used !== undefined || usageInfo.remaining !== undefined;
  return limitValue !== undefined || hasUsage;
}

function LimitItem({
  label,
  limitValue,
  usageInfo,
  showUsage,
}: {
  label: string;
  limitValue: LimitValue;
  usageInfo: ReturnType<typeof getUsageInfo>;
  showUsage: boolean;
}) {
  return (
    <div className="flex items-start justify-between rounded-lg border bg-muted/40 p-3">
      <div className="text-sm font-medium text-muted-foreground">{label}</div>
      <div className="space-y-1 text-right">
        <div className="text-sm font-semibold">{formatLimitValue(limitValue)}</div>
        {showUsage ? (
          <div className="text-xs text-muted-foreground flex gap-3 justify-end">
            <span>Usado: {formatUsageValue(usageInfo.used as number | null | undefined)}</span>
            <span>Restante: {formatUsageValue(usageInfo.remaining as number | null | undefined)}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function FeatureItem({ label, value }: { label: string; value: LimitValue }) {
  return (
    <div className="flex items-center justify-between rounded-lg border bg-muted/40 p-3">
      <div className="text-sm font-medium text-muted-foreground">{label}</div>
      <div className="text-sm font-semibold">
        {typeof value === "boolean" ? (value ? "Sim" : "Não") : "—"}
      </div>
    </div>
  );
}

export function PlanLimitsCard({ limits, usage }: PlanLimitsCardProps) {
  const showUsage = Boolean(usage);

  const renderGroup = (title: string, keys: readonly string[]) => {
    const items = keys.filter((key) => shouldRenderKey(key, limits, usage));
    if (!items.length) return null;

    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">{title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {items.map((key) => (
            <LimitItem
              key={key}
              label={LABELS[key] ?? key}
              limitValue={limits?.[key]}
              usageInfo={getUsageInfo(key, usage)}
              showUsage={showUsage}
            />
          ))}
        </CardContent>
      </Card>
    );
  };

  const featureItems = FEATURE_KEYS.filter((key) => limits?.[key] !== undefined);

  return (
    <div className="space-y-4">
      {renderGroup("Limites fixos", FIXED_KEYS)}
      {renderGroup("Limites diários", DAILY_KEYS)}
      {renderGroup("Limites mensais", MONTHLY_KEYS)}

      {featureItems.length ? (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Recursos</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {featureItems.map((key) => (
              <FeatureItem key={key} label={LABELS[key] ?? key} value={limits?.[key]} />
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
