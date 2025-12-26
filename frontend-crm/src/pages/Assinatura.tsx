import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useUsage } from "@/hooks/useUsage";
import { AlertCircle, CreditCard, Rocket } from "lucide-react";

export default function Assinatura() {
  const { data, loading, error, refetch } = useUsage();
  const entitlements = data?.entitlements;
  const crmProduct = entitlements?.products?.find(
    (product) => product?.product_code === "crm"
  );

  return (
    <div className="p-6 space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Assinatura</h1>
        <p className="text-muted-foreground">Assinatura</p>
      </div>

      {error && (
        <Alert variant="destructive" className="max-w-2xl">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Não foi possível carregar</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-4">
            <span>{error}</span>
            <Button size="sm" variant="outline" onClick={refetch}>
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
            <CardDescription>Informações do produto CRM</CardDescription>
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
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl">
              <Rocket className="h-5 w-5 text-primary" /> Gerenciar assinatura
            </CardTitle>
            <CardDescription>Acesse opções do seu plano</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Em breve você poderá comparar planos e fazer upgrade/downgrade por aqui.
            </p>
            <Button variant="secondary" disabled>
              Ver planos (em breve)
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
