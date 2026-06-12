import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertCircle, FlaskConical, ArrowDownToLine, ArrowUpFromLine, RefreshCw } from "lucide-react";
import { api, type AiProfile } from "@/services/api";

export type ScenarioType = "inbound" | "outbound" | "followup";

export interface FollowupContext {
  followup_variant: string;
  followup_outcome: string;
  followup_goal: string;
  followup_attempts: number;
  followup_max_attempts: number;
  followup_meeting_happened: boolean;
  followup_proposal_sent: boolean;
}

export interface PlaygroundSession {
  aiProfileId: number;
  aiProfileName: string;
  leadId: number | null;
  scenarioContext: string;
  scenarioType: ScenarioType;
  followupContext?: FollowupContext | null;
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
    audio_transcription_enabled?: boolean;
  };
}

interface PlaygroundConfigModalProps {
  open: boolean;
  onStart: (session: PlaygroundSession) => void;
}

function resolveFollowupVariant(templateKey: string | null | undefined): string {
  if (!templateKey) return "sdr_scheduler";
  if (templateKey.includes("closer")) return "cart_recovery";
  if (templateKey.includes("hybrid")) return "hybrid_scheduler";
  return "sdr_scheduler";
}

export function PlaygroundConfigModal({ open, onStart }: PlaygroundConfigModalProps) {
  const [profile, setProfile] = useState<AiProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scenarioContext, setScenarioContext] = useState("");
  const [scenarioType, setScenarioType] = useState<ScenarioType>("inbound");
  // Follow-up config
  const [fuOutcome, setFuOutcome] = useState("warm");
  const [fuGoal, setFuGoal] = useState("advance_closing");
  const [fuAttempts, setFuAttempts] = useState(1);
  const [fuMeetingHappened, setFuMeetingHappened] = useState(true);
  const [fuProposalSent, setFuProposalSent] = useState(false);

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

  const followupVariant = resolveFollowupVariant((profile as any)?.template_key);
  const isCartRecovery = followupVariant === "cart_recovery";
  const isHybrid = followupVariant === "hybrid_scheduler";

  function handleStart() {
    if (!profile?.id) return;
    const followupContext: FollowupContext | null = scenarioType === "followup" ? {
      followup_variant: followupVariant,
      followup_outcome: fuOutcome,
      followup_goal: fuGoal,
      followup_attempts: fuAttempts,
      followup_max_attempts: 3,
      followup_meeting_happened: fuMeetingHappened,
      followup_proposal_sent: fuProposalSent,
    } : null;
    onStart({
      aiProfileId: profile.id,
      aiProfileName: profile.name ?? `Perfil #${profile.id}`,
      leadId: null,
      scenarioContext: scenarioContext.trim(),
      scenarioType,
      followupContext,
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
        audio_transcription_enabled: (profile as any).audio_transcription_enabled ?? false,
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
            <div className="grid grid-cols-3 gap-2">
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
                  <div className="text-xs leading-tight opacity-70">Lead inicia</div>
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
                  <div className="text-xs leading-tight opacity-70">Bot inicia</div>
                </div>
              </button>
              <button
                type="button"
                onClick={() => setScenarioType("followup")}
                className={`flex items-center gap-2 rounded-md border px-3 py-2.5 text-sm transition-colors text-left ${
                  scenarioType === "followup"
                    ? "border-primary bg-primary/10 text-primary font-medium"
                    : "border-border bg-background text-muted-foreground hover:border-muted-foreground"
                }`}
              >
                <RefreshCw className="h-4 w-4 shrink-0" />
                <div>
                  <div className="font-medium leading-tight">Follow-up</div>
                  <div className="text-xs leading-tight opacity-70">Tick automático</div>
                </div>
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              {scenarioType === "inbound"
                ? "Simula um lead que te procura. Você digita como o lead e o bot responde."
                : scenarioType === "outbound"
                ? "Simula uma abordagem ativa. O bot envia a mensagem de abertura outbound primeiro."
                : "Simula um tick de follow-up automático. Configure o contexto pós-apresentação abaixo."}
            </p>
          </div>

          {/* Painel de configuração do follow-up */}
          {scenarioType === "followup" && (
            <div className="space-y-3 rounded-md border border-border bg-muted/30 px-3 py-3">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Contexto do follow-up
                <span className="ml-2 normal-case font-normal opacity-70">variante: {followupVariant}</span>
              </p>

              {!isCartRecovery && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label className="text-xs">Outcome do lead</Label>
                    <Select value={fuOutcome} onValueChange={setFuOutcome}>
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {isHybrid ? (
                          <>
                            <SelectItem value="interested_not_closed">Interessado, não fechou</SelectItem>
                            <SelectItem value="reschedule_needed">Precisa remarcar</SelectItem>
                            <SelectItem value="converted">Convertido</SelectItem>
                            <SelectItem value="lost">Perdido</SelectItem>
                          </>
                        ) : (
                          <>
                            <SelectItem value="hot">Quente</SelectItem>
                            <SelectItem value="warm">Morno</SelectItem>
                            <SelectItem value="cold">Frio</SelectItem>
                            <SelectItem value="lost">Perdido</SelectItem>
                          </>
                        )}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Objectivo</Label>
                    <Select value={fuGoal} onValueChange={setFuGoal}>
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="advance_closing">Avançar fechamento</SelectItem>
                        <SelectItem value="nurture">Nutrir</SelectItem>
                        <SelectItem value="reschedule_conversation">Reagendar</SelectItem>
                        <SelectItem value="register_only">Apenas registar</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Tentativa nº</Label>
                  <Select value={String(fuAttempts)} onValueChange={(v) => setFuAttempts(Number(v))}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1ª tentativa</SelectItem>
                      <SelectItem value="2">2ª tentativa</SelectItem>
                      <SelectItem value="3">3ª tentativa</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Reunião aconteceu?</Label>
                  <Select value={fuMeetingHappened ? "yes" : "no"} onValueChange={(v) => setFuMeetingHappened(v === "yes")}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="yes">Sim</SelectItem>
                      <SelectItem value="no">Não</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          )}

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
