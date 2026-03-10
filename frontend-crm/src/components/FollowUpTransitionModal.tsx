import { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Lead } from "@/types/crm";
import { api } from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { Loader2 } from "lucide-react";

type MeetingHappened = "yes" | "no_show" | "canceled" | "needs_reschedule";
type AgentType = "agent_1" | "agent_3";

interface FollowUpTransitionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lead: Lead | null;
  onSuccess: () => void;
}

export function FollowUpTransitionModal({ open, onOpenChange, lead, onSuccess }: FollowUpTransitionModalProps) {
  const { toast } = useToast();
  const [meetingHappened, setMeetingHappened] = useState<MeetingHappened | "">("");
  const [outcome, setOutcome] = useState<string>("");
  const [followupGoal, setFollowupGoal] = useState<string>("");
  const [proposalSent, setProposalSent] = useState<"yes" | "no" | "">("");
  const [operatorNote, setOperatorNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const agentType = (lead?.agent_type || "") as AgentType;
  const isAgent1 = agentType === "agent_1";
  const isAgent3 = agentType === "agent_3";

  const showMeetingYes = meetingHappened === "yes";

  const canSubmit = useMemo(() => {
    if (!lead || !(isAgent1 || isAgent3)) return false;
    if (!meetingHappened) return false;
    if (showMeetingYes) {
      if (!outcome) return false;
      if (isAgent1) {
        if (!followupGoal) return false;
        if (!proposalSent) return false;
      }
      if (isAgent3) {
        if (outcome === "interested_not_closed" && !followupGoal) return false;
        if (outcome === "reschedule_needed" && !proposalSent) return false;
      }
      return true;
    }
    return !!followupGoal;
  }, [lead, isAgent1, isAgent3, meetingHappened, showMeetingYes, outcome, followupGoal, proposalSent]);

  const resetState = () => {
    setMeetingHappened("");
    setOutcome("");
    setFollowupGoal("");
    setProposalSent("");
    setOperatorNote("");
  };

  const handleOpenChange = (next: boolean) => {
    if (!next && submitting) return;
    onOpenChange(next);
    if (!next) resetState();
  };

  const submit = async () => {
    if (!lead || !canSubmit || !(isAgent1 || isAgent3)) return;
    setSubmitting(true);
    try {
      await api.startFollowup({
        lead_id: lead.id,
        agent_type: agentType,
        meeting_or_session_happened: meetingHappened as MeetingHappened,
        outcome: outcome || null,
        followup_goal: followupGoal || null,
        proposal_sent: proposalSent ? proposalSent === "yes" : null,
        operator_note: operatorNote.trim() || null,
      });
      toast({ title: "Follow-up iniciado", description: "Lead movido e bot reativado." });
      onSuccess();
      handleOpenChange(false);
    } catch (error: any) {
      toast({
        title: "Erro ao iniciar follow-up",
        description: error?.message ?? "Não foi possível iniciar o follow-up.",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const renderAgent1 = () => {
    if (showMeetingYes) {
      return (
        <>
          <div className="space-y-2">
            <Label>Como esse lead saiu da reunião?</Label>
            <Select value={outcome} onValueChange={setOutcome}>
              <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="hot">Quente</SelectItem>
                <SelectItem value="warm">Morno</SelectItem>
                <SelectItem value="cold">Frio</SelectItem>
                <SelectItem value="lost">Perdido</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Você enviou proposta?</Label>
            <Select value={proposalSent} onValueChange={(v) => setProposalSent(v as any)}>
              <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="yes">Sim</SelectItem>
                <SelectItem value="no">Não</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Qual o objetivo do follow-up?</Label>
            <Select value={followupGoal} onValueChange={setFollowupGoal}>
              <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="advance_closing">Avançar para fechamento</SelectItem>
                <SelectItem value="nurture">Nutrir relacionamento</SelectItem>
                <SelectItem value="reschedule_conversation">Reagendar conversa</SelectItem>
                <SelectItem value="register_only">Apenas registrar</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </>
      );
    }

    return (
      <div className="space-y-2">
        <Label>O que você quer que o bot faça?</Label>
        <Select value={followupGoal} onValueChange={setFollowupGoal}>
          <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="recover_and_reschedule">Recuperar e reagendar</SelectItem>
            <SelectItem value="reengage">Reengajar</SelectItem>
            <SelectItem value="register_only">Apenas registrar</SelectItem>
          </SelectContent>
        </Select>
      </div>
    );
  };

  const renderAgent3 = () => {
    if (showMeetingYes) {
      return (
        <>
          <div className="space-y-2">
            <Label>Como terminou a sessão?</Label>
            <Select value={outcome} onValueChange={(v) => { setOutcome(v); setFollowupGoal(""); setProposalSent(""); }}>
              <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="interested_not_closed">Interessado, mas ainda não fechou</SelectItem>
                <SelectItem value="reschedule_needed">Precisa reagendar</SelectItem>
                <SelectItem value="lost">Perdido</SelectItem>
                <SelectItem value="converted">Convertido</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {outcome === "interested_not_closed" && (
            <div className="space-y-2">
              <Label>O que o bot deve fazer?</Label>
              <Select value={followupGoal} onValueChange={setFollowupGoal}>
                <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="nurture_interest">Nutrir interesse</SelectItem>
                  <SelectItem value="prompt_reply">Incentivar resposta</SelectItem>
                  <SelectItem value="prepare_next_conversation">Preparar próxima conversa</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {outcome === "reschedule_needed" && (
            <div className="space-y-2">
              <Label>O bot deve tentar remarcar automaticamente?</Label>
              <Select value={proposalSent} onValueChange={(v) => setProposalSent(v as any)}>
                <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="yes">Sim</SelectItem>
                  <SelectItem value="no">Não</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        </>
      );
    }

    return (
      <div className="space-y-2">
        <Label>O que o bot deve tentar fazer agora?</Label>
        <Select value={followupGoal} onValueChange={setFollowupGoal}>
          <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="recover_and_reschedule">Recuperar e reagendar</SelectItem>
            <SelectItem value="reengage_conversation">Reengajar conversa</SelectItem>
            <SelectItem value="register_only">Apenas registrar</SelectItem>
          </SelectContent>
        </Select>
      </div>
    );
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Iniciar follow-up assistido</DialogTitle>
          <DialogDescription>
            Registre o contexto da etapa humana para iniciar o follow-up automático.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>A reunião/sessão aconteceu?</Label>
            <Select value={meetingHappened} onValueChange={(v) => { setMeetingHappened(v as MeetingHappened); setOutcome(""); setFollowupGoal(""); setProposalSent(""); }}>
              <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="yes">Sim</SelectItem>
                <SelectItem value="no_show">Não compareceu</SelectItem>
                <SelectItem value="canceled">Cancelada</SelectItem>
                <SelectItem value="needs_reschedule">Precisa reagendar</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {isAgent1 && meetingHappened && renderAgent1()}
          {isAgent3 && meetingHappened && renderAgent3()}

          <div className="space-y-2">
            <Label>Observação (opcional)</Label>
            <Textarea value={operatorNote} onChange={(e) => setOperatorNote(e.target.value)} placeholder="Ex.: quer falar com o sócio antes de avançar." />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={submitting}>Cancelar</Button>
          <Button onClick={submit} disabled={!canSubmit || submitting}>
            {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Salvar e iniciar follow-up
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
