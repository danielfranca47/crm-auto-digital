import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useToast } from "@/hooks/use-toast";
import { api, CorePlan, EntitlementsResponse } from "@/services/api";
import {
  AlertCircle,
  ArrowRight,
  Calendar,
  Check,
  CheckCircle,
  CreditCard,
  ExternalLink,
  Info,
  Rocket,
} from "lucide-react";

const env = import.meta.env;

// Mapa de plan_code → URL de checkout Kiwify
// Pode ser sobreposto por variáveis de ambiente por plano
const PLAN_CHECKOUT_URLS: Record<string, string> = {
  crm_start:  env?.VITE_CHECKOUT_URL_CRM_START  || "https://pay.kiwify.com.br/gOjcexD",
  crm_growth: env?.VITE_CHECKOUT_URL_CRM_GROWTH || "https://pay.kiwify.com.br/To8qV99",
  crm_scale:  env?.VITE_CHECKOUT_URL_CRM_SCALE  || "https://pay.kiwify.com.br/2mtd25x",
};

function buildCheckoutUrl(planCode: string, email?: string | null) {
  const base = PLAN_CHECKOUT_URLS[planCode] || env?.VITE_UPGRADE_CHECKOUT_URL?.trim();
  if (!base) return null;
  if (!email) return base;
  try {
    const url = new URL(base);
    url.searchParams.set("email", email);
    return url.toString();
  } catch {
    return base;
  }
}

function buildWhatsAppUrl(planCode: string, planName?: string, email?: string | null) {
  const rawNumber = env?.VITE_WHATSAPP_UPGRADE_NUMBER?.trim();
  if (!rawNumber) return null;

  const sanitized = rawNumber.replace(/[^0-9+]/g, "");
  if (!sanitized) return null;

  const template = env?.VITE_WHATSAPP_UPGRADE_MESSAGE_TEMPLATE;
  const baseMessage = template?.trim().length
    ? template
    : "Quero fazer upgrade do CRM";

  const message = baseMessage
    .replace("{plan_code}", planCode)
    .replace("{plan}", planName ?? planCode)
    .replace("{email}", email ?? "");

  const fallbackMessage = baseMessage.includes("{plan_code}") || baseMessage.includes("{plan}")
    ? message
    : `${baseMessage} para ${planName ?? planCode}`;

  const withEmail = email && !fallbackMessage.includes(email)
    ? `${fallbackMessage} (email: ${email})`
    : fallbackMessage;

  return `https://wa.me/${sanitized}?text=${encodeURIComponent(withEmail)}`;
}

function formatBillingPeriod(billingPeriod?: string | null) {
  if (!billingPeriod) return "—";
  return billingPeriod.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

export default function Assinatura() {
  const { handleError } = useApiErrorHandler();
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  const upgraded = searchParams.get("upgraded") === "1";

  const [plans, setPlans] = useState<CorePlan[]>([]);
  const [entitlements, setEntitlements] = useState<EntitlementsResponse | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const crmProduct = useMemo(
    () => entitlements?.products?.find((product) => product?.product_code === "crm"),
    [entitlements]
  );

  const renewalDate = useMemo(() => {
    const end = (crmProduct as any)?.current_period_end;
    if (!end) return null;
    return new Date(end).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
  }, [crmProduct]);

  // Botões activos se existe pelo menos um URL de checkout ou número WhatsApp configurado
  const contactAvailable = Boolean(
    Object.values(PLAN_CHECKOUT_URLS).some(Boolean)
    || env?.VITE_UPGRADE_CHECKOUT_URL?.trim()
    || env?.VITE_WHATSAPP_UPGRADE_NUMBER?.trim()
  );

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [plansResponse, entitlementsResponse, meResponse] = await Promise.all([
        api.core.getPlans("crm"),
        api.core.getEntitlements(),
        api.auth.me(),
      ]);

      setPlans(Array.isArray(plansResponse) ? plansResponse : []);
      setEntitlements(entitlementsResponse ?? null);
      setUserEmail(meResponse?.email ?? null);
    } catch (err) {
      const { message } = handleError(err, {
        fallbackMessage: "Erro ao carregar informações da assinatura.",
      });
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [handleError]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSelectPlan = useCallback(
    (plan: CorePlan) => {
      const checkoutUrl = buildCheckoutUrl(plan.code, userEmail);
      const whatsappUrl = buildWhatsAppUrl(plan.code, plan.name ?? plan.code, userEmail);

      if (checkoutUrl) {
        window.open(checkoutUrl, "_blank", "noopener");
        return;
      }

      if (whatsappUrl) {
        window.open(whatsappUrl, "_blank", "noopener");
        return;
      }

      toast({
        title: "Contato de upgrade não configurado",
        description: "Defina VITE_UPGRADE_CHECKOUT_URL ou VITE_WHATSAPP_UPGRADE_NUMBER",
        variant: "destructive",
      });
    },
    [toast, userEmail]
  );

  const isLoadingList = loading && !plans.length;

  return (
    <div className="p-6 space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Assinatura</h1>
        <p className="text-muted-foreground">
          Visualize seu plano atual e compare opções disponíveis do CRM.
        </p>
      </div>

      {upgraded && (
        <Alert className="max-w-3xl border-green-500/50 bg-green-500/10">
          <CheckCircle className="h-4 w-4 text-green-500" />
          <AlertTitle className="text-green-600">Plano activado com sucesso!</AlertTitle>
          <AlertDescription>
            O teu novo plano já está activo. As funcionalidades foram desbloqueadas — podes fechar esta mensagem e começar a usar.
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive" className="max-w-3xl">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Não foi possível carregar</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button size="sm" variant="outline" onClick={fetchData}>
              Tentar novamente
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl">
              <CreditCard className="h-5 w-5 text-primary" /> Plano atual
            </CardTitle>
            <CardDescription>Produto CRM</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <div className="space-y-2">
                <Skeleton className="h-6 w-40" />
                <Skeleton className="h-4 w-28" />
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
                {renewalDate && (
                  <div className="flex items-center gap-1.5 text-sm text-muted-foreground mt-1">
                    <Calendar className="h-3.5 w-3.5 shrink-0" />
                    <span>Activo até <strong>{renewalDate}</strong></span>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl">
              <Rocket className="h-5 w-5 text-primary" /> Gerenciar assinatura
            </CardTitle>
            <CardDescription>Compare planos e acompanhe limites</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Escolha um plano para upgrade/downgrade. A ação abrirá o checkout ou
              um canal de contato configurado.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="default"
                onClick={() =>
                  document.getElementById("planos")?.scrollIntoView({
                    behavior: "smooth",
                  })
                }
              >
                Ver planos
              </Button>
              <Button asChild variant="outline">
                <Link to="/minha-conta">Ver limites</Link>
              </Button>
              <Button asChild variant="outline">
                <Link to="/uso-do-plano">Ver uso</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {crmProduct?.status === "active" && (
        <Alert className="max-w-3xl border-blue-500/40 bg-blue-500/5">
          <Info className="h-4 w-4 text-blue-500" />
          <AlertTitle className="text-blue-700 dark:text-blue-400">Como trocar de plano</AlertTitle>
          <AlertDescription className="space-y-2 text-sm">
            <p>
              A Kiwify não tem troca automática de plano — ao subscrever um plano superior é criada uma
              nova assinatura independente. Para evitar pagar dois planos em simultâneo:
            </p>
            <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
              <li>
                Subscreve o novo plano <strong>próximo da data de renovação</strong>
                {renewalDate ? <> (<strong>{renewalDate}</strong>)</> : ""}.
              </li>
              <li>
                Após a confirmação de pagamento, cancela a assinatura actual pelo link que a Kiwify
                enviou no teu email de confirmação de compra.
              </li>
              <li>
                O nosso sistema activa o novo plano automaticamente assim que recebe a confirmação.
              </li>
            </ol>
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-4" id="planos">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Planos disponíveis</h2>
            <p className="text-sm text-muted-foreground">Catálogo do produto CRM</p>
          </div>
          {!contactAvailable && (
            <Badge variant="secondary" className="text-xs">
              Contato de upgrade não configurado
            </Badge>
          )}
        </div>

        {isLoadingList && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {[1, 2, 3].map((key) => (
              <Card key={key} className="space-y-4 p-4">
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
              </Card>
            ))}
          </div>
        )}

        {!isLoadingList && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {plans.map((plan) => {
              const isCurrent = plan.code === crmProduct?.plan_code;
              const billing = formatBillingPeriod(plan.billing_period);
              const disabled = isCurrent || !contactAvailable;
              const disabledReason = isCurrent
                ? "Este é o seu plano atual"
                : "Contato de upgrade não configurado";

              return (
                <Card
                  key={plan.code}
                  className={`h-full transition ${isCurrent ? "border-primary/60 shadow-sm" : ""}`}
                >
                  <CardHeader className="space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <CardTitle className="text-xl">{plan.name ?? plan.code}</CardTitle>
                      {isCurrent && (
                        <Badge className="gap-1" variant="default">
                          <Check className="h-3.5 w-3.5" /> Plano atual
                        </Badge>
                      )}
                    </div>
                    <CardDescription className="flex items-center gap-2 text-sm">
                      <span className="capitalize">{plan.code}</span>
                      <span className="text-muted-foreground">•</span>
                      <span>Faturamento: {billing}</span>
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="text-sm text-muted-foreground">
                      Preço: — (definir no checkout)
                    </div>
                    <Button
                      className="w-full"
                      variant={isCurrent ? "secondary" : "default"}
                      disabled={disabled}
                      title={disabled ? disabledReason : undefined}
                      onClick={() => !disabled && handleSelectPlan(plan)}
                    >
                      {isCurrent ? (
                        "Seu plano atual"
                      ) : (
                        <span className="flex items-center justify-center gap-2">
                          Selecionar plano
                          <ArrowRight className="h-4 w-4" />
                        </span>
                      )}
                    </Button>
                    {!contactAvailable && !isCurrent && (
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <AlertCircle className="h-3.5 w-3.5" />
                        Contato de upgrade não configurado
                      </p>
                    )}
                    {contactAvailable && (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <ExternalLink className="h-3.5 w-3.5" />
                        Ação abre checkout ou WhatsApp em nova aba
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}

            {!plans.length && !loading && (
              <Card className="col-span-full">
                <CardContent className="py-6 text-sm text-muted-foreground">
                  Nenhum plano do produto CRM foi retornado.
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
