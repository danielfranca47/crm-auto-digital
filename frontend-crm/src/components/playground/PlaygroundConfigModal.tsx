import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, FlaskConical, ArrowDownToLine, ArrowUpFromLine } from "lucide-react";
import { api, type AiProfile } from "@/services/api";

export type ScenarioType = "inbound" | "outbound";

export interface PlaygroundSession {
  aiProfileId: number;
  aiProfileName: string;
  leadId: number | null;
  scenarioContext: string;
  scenarioType: ScenarioType;
  startedAt: string;
  // Snapshot da configuração do AI Profile no momento do teste
  profileSnapshot: {
    agent_mode?: string | null;
    template_key?: string | null;
    presentation_variant?: string | null;
    response_style?: string | null;
    tone_of_voice?: string | null;
    niche?: string | null;
    target_audience?: string | null;
    qualification_required_fields?: string[] | null;
    custom_instructions?: string | null;
    brand_name?: string | null;
  };
}

interface PlaygroundConfigModalProps {
  open: boolean;
  onStart: (session: PlaygroundSession) => void;
}

export function PlaygroundConfigModal({ open, onStart }: PlaygroundConfigModalProps) {
  const [profile, setProfile] = useState<AiProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scenarioContext, setScenarioContext] = useState("");
  const [scenarioType, setScenarioType] = useState<ScenarioType>("inbound");

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    api.core
      .getAiProfileMe()
      .then((p) => setProfile(p))
      .catch(() => setError("Não foi possível carregar o perfil de IA. Verifique se está configurado."))
      .finally(() => setLoading(false));
  }, [open]);

  function handleStart() {
    if (!profile?.id) return;
    onStart({
      aiProfileId: profile.id,
      aiProfileName: profile.name ?? `Perfil #${profile.id}`,
      leadId: null,
      scenarioContext: scenarioContext.trim(),
      scenarioType,
      startedAt: new Date().toISOString(),
      profileSnapshot: {
        agent_mode: profile.agent_mode,
        template_key: profile.template_key,
        presentation_variant: (profile as any).presentation_variant ?? null,
        response_style: profile.response_style,
        tone_of_voice: profile.tone_of_voice,
        niche: profile.niche,
        target_audience: profile.target_audience,
        qualification_required_fields: profile.qualification_required_fields,
        custom_instructions: profile.custom_instructions,
        brand_name: profile.brand_name,
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="sm:max-w-md" onInteractOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5" />
            Configurar Sessão de Playground
          </DialogTitle>
          <DialogDescription>
            Configure o cenário antes de iniciar a simulação de conversa.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 pt-2">
          {/* Perfil de IA */}
          <div className="space-y-1.5">
            <Label>Perfil de IA (agente)</Label>
            {loading ? (
              <Skeleton className="h-10 w-full" />
            ) : error ? (
              <div className="flex items-center gap-2 text-sm text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            ) : profile ? (
              <div className="rounded-md border px-3 py-2 bg-muted text-sm">
                <span className="font-medium">{profile.name ?? "Perfil sem nome"}</span>
                <span className="text-muted-foreground ml-2">
                  · {profile.agent_mode ?? "—"} / {profile.template_key ?? "—"}
                </span>
              </div>
            ) : null}
          </div>

          {/* Tipo de cenário */}
          <div className="space-y-1.5">
            <Label>Tipo de cenário</Label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setScenarioType("inbound")}
                className={`flex items-center gap-2 rounded-md border px-3 py-2.5 text-sm transition-colors text-left ${
                  scenarioType === "inbound"
                    ? "border-primary bg-primary/10 text-primary font-medium"
                    : "border-border bg-background text-muted-foreground hover:border-muted-foreground"
                }`}
              >
                <ArrowDownToLine className="h-4 w-4 shrink-0" />
                <div>
                  <div className="font-medium leading-tight">Inbound</div>
                  <div className="text-xs leading-tight opacity-70">Lead inicia contato</div>
                </div>
              </button>
              <button
                type="button"
                onClick={() => setScenarioType("outbound")}
                className={`flex items-center gap-2 rounded-md border px-3 py-2.5 text-sm transition-colors text-left ${
                  scenarioType === "outbound"
                    ? "border-primary bg-primary/10 text-primary font-medium"
                    : "border-border bg-background text-muted-foreground hover:border-muted-foreground"
                }`}
              >
                <ArrowUpFromLine className="h-4 w-4 shrink-0" />
                <div>
                  <div className="font-medium leading-tight">Outbound</div>
                  <div className="text-xs leading-tight opacity-70">Bot inicia contato</div>
                </div>
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              {scenarioType === "inbound"
                ? "Simula um lead que te procura. Você digita como o lead e o bot responde."
                : "Simula uma abordagem ativa. O bot envia a mensagem de abertura outbound primeiro."}
            </p>
          </div>

          {/* Contexto do cenário */}
          <div className="space-y-1.5">
            <Label htmlFor="scenario-context">
              Contexto do cenário{" "}
              <span className="text-muted-foreground font-normal">(opcional)</span>
            </Label>
            <Textarea
              id="scenario-context"
              placeholder="Ex: Testar comportamento com lead que pede informações sobre preço antes de qualificar..."
              value={scenarioContext}
              onChange={(e) => setScenarioContext(e.target.value)}
              rows={3}
              className="resize-none"
            />
            <p className="text-xs text-muted-foreground">
              Este texto será incluído no markdown exportado para contextualizar o teste.
            </p>
          </div>

          <Button
            className="w-full"
            onClick={handleStart}
            disabled={loading || !!error || !profile?.id}
          >
            Iniciar Sessão
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
