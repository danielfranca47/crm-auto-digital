import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, FlaskConical } from "lucide-react";
import { api, type AiProfile } from "@/services/api";

export interface PlaygroundSession {
  aiProfileId: number;
  aiProfileName: string;
  leadId: number | null;
  scenarioContext: string;
  startedAt: string;
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
      startedAt: new Date().toISOString(),
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
