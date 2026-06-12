import { OnboardingWizard } from "@/components/agente/OnboardingWizard";

export default function Onboarding() {
  return (
    <div className="min-h-screen bg-background flex items-start justify-center py-12 px-4">
      <div className="w-full max-w-xl">
        <div className="mb-8 text-center space-y-1">
          <h1 className="text-2xl font-bold">Vamos configurar seu agente</h1>
          <p className="text-sm text-muted-foreground">
            Responda algumas perguntas básicas sobre seu negócio. Leva menos de 2 minutos.
          </p>
        </div>
        <OnboardingWizard />
      </div>
    </div>
  );
}
