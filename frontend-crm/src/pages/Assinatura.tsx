import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useSubscriptionStatus } from "@/hooks/useSubscriptionStatus";
import { useToast } from "@/hooks/use-toast";
import { SUBSCRIPTION_STATE_LABELS } from "@/lib/subscription";
import { api, CorePlan } from "@/services/api";
import {
  AlertCircle,
  ArrowRight,
  Calendar,
  Check,
  CheckCircle,
  CreditCard,
  ExternalLink,
  Info,
  Loader2,
  Lock,
  Rocket,
} from "lucide-react";

const env = import.meta.env;

const CRM_BASE = (env?.VITE_CRM_BASE_URL || env?.VITE_API_BASE_URL || env?.VITE_API_URL || "").replace(/\/+$/, "");

// Mapa de plan_code → URL de checkout Efí (endpoint que gera o link sob demanda, ver
// docs/architecture/billing-efi.md)
// Pode ser sobreposto por variáveis de ambiente por plano
const PLAN_CHECKOUT_URLS: Record<string, string> = {
  crm_start:  env?.VITE_CHECKOUT_URL_CRM_START  || (CRM_BASE ? `${CRM_BASE}/checkout/efi/start` : ""),
  crm_growth: env?.VITE_CHECKOUT_URL_CRM_GROWTH || (CRM_BASE ? `${CRM_BASE}/checkout/efi/growth` : ""),
};

// Planos à venda, na ordem em que aparecem no catálogo. `GET /plans` devolve também os
// legados e o interno (o painel admin precisa deles) — esses não se oferecem ao cliente.
const SELLABLE_PLAN_CODES = Object.keys(PLAN_CHECKOUT_URLS);

const BILLING_PERIOD_LABELS: Record<string, string> = {
  monthly: "Mensal",
  yearly: "Anual",
  annual: "Anual",
};

function buildCheckoutUrl(planCode: string) {
  return PLAN_CHECKOUT_URLS[planCode] || env?.VITE_UPGRADE_CHECKOUT_URL?.trim() || null;
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
  return (
    BILLING_PERIOD_LABELS[billingPeriod.toLowerCase()]
    ?? billingPeriod.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())
  );
}

export default function Assinatura() {
  const { handleError } = useApiErrorHandler();
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  const upgraded = searchParams.get("upgraded") === "1";

  const [plans, setPlans] = useState<CorePlan[]>([]);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recheckingPayment, setRecheckingPayment] = useState(false);

  const {
    state: subscriptionState,
    product: crmProduct,
    isLoading: subscriptionLoading,
    refetch: refetchSubscription,
  } = useSubscriptionStatus();
  const isActive = subscriptionState === "active";
  // Sem plano activo confirmado (expirado, cancelado ou nunca subscrito) — "unknown" não conta
  const isLocked = !isActive && subscriptionState !== "unknown";

  const renewalDate = useMemo(() => {
    const end = crmProduct?.current_period_end;
    if (!end) return null;
    return new Date(end).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
  }, [crmProduct]);

  const currentPlanName = useMemo(() => {
    const code = crmProduct?.plan_code;
    if (!code) return null;
    return plans.find((plan) => plan.code === code)?.name ?? code;
  }, [crmProduct, plans]);

  const sellablePlans = useMemo(
    () =>
      SELLABLE_PLAN_CODES
        .map((code) => plans.find((plan) => plan.code === code))
        .filter((plan): plan is CorePlan => !!plan),
    [plans]
  );

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
      const [plansResponse, meResponse] = await Promise.all([
        api.core.getPlans("crm"),
        api.auth.me(),
      ]);

      setPlans(Array.isArray(plansResponse) ? plansResponse : []);
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
      const checkoutUrl = buildCheckoutUrl(plan.code);
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

  const scrollToPlans = useCallback(() => {
    document.getElementById("planos")?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const handleRenew = useCallback(() => {
    const planCode = crmProduct?.plan_code;
    const checkoutUrl = crmProduct?.renewal_checkout_url || (planCode ? buildCheckoutUrl(planCode) : null);
    if (checkoutUrl) {
      window.open(checkoutUrl, "_blank", "noopener");
      return;
    }
    scrollToPlans();
  }, [crmProduct, scrollToPlans]);

  const handleRecheckPayment = useCallback(async () => {
    setRecheckingPayment(true);
    try {
      const { data } = await refetchSubscription();
      const active = data?.products?.some((p) => p?.product_code === "crm" && p?.status === "active");
      toast(
        active
          ? { title: "Plano ativo!", description: "O acesso ao CRM foi liberado." }
          : {
              title: "Pagamento ainda não confirmado",
              description: "A confirmação pode levar alguns minutos. Tenta novamente daqui a pouco.",
            }
      );
    } finally {
      setRecheckingPayment(false);
    }
  }, [refetchSubscription, toast]);

  const supportUrl = buildWhatsAppUrl(crmProduct?.plan_code ?? "crm", currentPlanName ?? undefined, userEmail);

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

      {isLocked && (
        <Alert className="max-w-3xl border-amber-500/50 bg-amber-500/10">
          <Lock className="h-4 w-4 text-amber-600" />
          <AlertTitle className="text-amber-700 dark:text-amber-400">
            {subscriptionState === "none"
              ? "Ainda não tens um plano ativo"
              : subscriptionState === "expired"
              ? `O teu plano ${currentPlanName ?? ""} expirou${renewalDate ? ` em ${renewalDate}` : ""}`
              : `A tua assinatura ${currentPlanName ?? ""} foi cancelada`}
          </AlertTitle>
          <AlertDescription className="space-y-3 text-sm">
            {subscriptionState === "none" ? (
              <p>Escolhe um plano para começar a usar o CRM e pôr a Lara a responder aos teus clientes.</p>
            ) : (
              <p>
                Os teus leads, conversas e configurações continuam guardados. A Lara está em pausa e
                não responde aos teus clientes até {subscriptionState === "expired" ? "renovares" : "reativares"} o plano.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              {subscriptionState === "none" ? (
                <Button onClick={scrollToPlans}>Escolher plano</Button>
              ) : (
                <Button onClick={handleRenew}>
                  {subscriptionState === "expired" ? "Renovar agora" : "Reativar plano"}
                </Button>
              )}
              <Button variant="outline" onClick={handleRecheckPayment} disabled={recheckingPayment}>
                {recheckingPayment && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Já paguei — atualizar
              </Button>
              {supportUrl && (
                <Button asChild variant="ghost">
                  <a href={supportUrl} target="_blank" rel="noopener noreferrer">
                    Falar com suporte
                  </a>
                </Button>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Depois do pagamento, o acesso é ativado automaticamente assim que a confirmação chega
              (pode levar alguns minutos).
            </p>
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
            {subscriptionLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-6 w-40" />
                <Skeleton className="h-4 w-28" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-semibold">
                  {currentPlanName || "Sem plano"}
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Badge variant={isActive ? "default" : "secondary"}>
                    {subscriptionState === "unknown" ? "indefinido" : SUBSCRIPTION_STATE_LABELS[subscriptionState]}
                  </Badge>
                  <span>Produto: CRM</span>
                </div>
                {renewalDate && (
                  <div className="flex items-center gap-1.5 text-sm text-muted-foreground mt-1">
                    <Calendar className="h-3.5 w-3.5 shrink-0" />
                    <span>
                      {isActive ? "Activo até" : subscriptionState === "expired" ? "Expirou em" : "Período terminou em"}{" "}
                      <strong>{renewalDate}</strong>
                    </span>
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
              <Button variant="default" onClick={scrollToPlans}>
                Ver planos
              </Button>
              {/* Limites e uso vivem no backend-crm — inacessíveis sem plano activo */}
              {!isLocked && (
                <>
                  <Button asChild variant="outline">
                    <Link to="/minha-conta">Ver limites</Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link to="/uso-do-plano">Ver uso</Link>
                  </Button>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {isActive && (
        <Alert className="max-w-3xl border-blue-500/40 bg-blue-500/5">
          <Info className="h-4 w-4 text-blue-500" />
          <AlertTitle className="text-blue-700 dark:text-blue-400">Como trocar de plano</AlertTitle>
          <AlertDescription className="space-y-2 text-sm">
            <p>
              A troca de plano não é automática — ao subscrever um plano superior é criada uma
              nova assinatura independente. Para evitar pagar dois planos em simultâneo:
            </p>
            <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
              <li>
                Subscreve o novo plano <strong>próximo da data de renovação</strong>
                {renewalDate ? <> (<strong>{renewalDate}</strong>)</> : ""}.
              </li>
              <li>
                Após a confirmação de pagamento, contacta o suporte para cancelar a assinatura
                actual.
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
          <div className="grid max-w-3xl grid-cols-1 gap-4 md:grid-cols-2">
            {SELLABLE_PLAN_CODES.map((key) => (
              <Card key={key} className="space-y-4 p-4">
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
              </Card>
            ))}
          </div>
        )}

        {!isLoadingList && (
          <div className="grid max-w-3xl grid-cols-1 gap-4 md:grid-cols-2">
            {sellablePlans.map((plan) => {
              const isCurrent = isActive && plan.code === crmProduct?.plan_code;
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
                    <CardDescription className="text-sm">Faturamento: {billing}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="text-sm text-muted-foreground">
                      Valor apresentado no checkout
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
