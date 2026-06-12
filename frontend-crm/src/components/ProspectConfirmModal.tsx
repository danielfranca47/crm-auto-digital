import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Lead } from "@/types/crm";
import { api } from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { Loader2 } from "lucide-react";

interface ProspectConfirmModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lead: Lead | null;
  onSuccess: () => void;
  onSkip: () => void;
}

type Step = "ask" | "context";

export function ProspectConfirmModal({
  open,
  onOpenChange,
  lead,
  onSuccess,
  onSkip,
}: ProspectConfirmModalProps) {
  const { toast } = useToast();
  const [step, setStep] = useState<Step>("ask");
  const [contextText, setContextText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const resetState = () => {
    setStep("ask");
    setContextText("");
    setSubmitting(false);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) resetState();
    onOpenChange(open);
  };

  const handleNo = () => {
    resetState();
    onOpenChange(false);
    onSkip();
  };

  const handleConfirm = async () => {
    if (!lead || contextText.trim().length < 10) return;
    setSubmitting(true);
    try {
      await api.updateLead(lead.id, {
        origin: "outbound",
        prospection_context: contextText.trim(),
      });
      resetState();
      onOpenChange(false);
      onSuccess();
    } catch {
      toast({
        title: "Erro ao registar prospecção",
        description: "Não foi possível actualizar o lead. Tenta novamente.",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (!lead) return null;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        {step === "ask" ? (
          <>
            <DialogHeader>
              <DialogTitle>Prospecção activa</DialogTitle>
            </DialogHeader>

            <div className="py-4 text-sm text-muted-foreground">
              Já prospectou{" "}
              <span className="font-medium text-foreground">
                {lead.companyName || lead.contactName}
              </span>{" "}
              activamente (ligação, visita, mensagem manual)?
            </div>

            <DialogFooter className="flex-col gap-2 sm:flex-row">
              <Button variant="outline" onClick={handleNo} className="w-full sm:w-auto">
                Não, a aguardar resposta
              </Button>
              <Button onClick={() => setStep("context")} className="w-full sm:w-auto">
                Sim, já prospectei
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>O que foi feito?</DialogTitle>
            </DialogHeader>

            <div className="py-2 space-y-3">
              <p className="text-sm text-muted-foreground">
                Descreve brevemente como foi a prospecção (canal, resposta, próximo passo…)
              </p>
              <Textarea
                placeholder="Ex: Liguei, apresentei o serviço e ficou de pensar. Vou ligar na próxima semana."
                value={contextText}
                onChange={(e) => setContextText(e.target.value)}
                rows={4}
                autoFocus
              />
              {contextText.trim().length > 0 && contextText.trim().length < 10 && (
                <p className="text-xs text-destructive">Mínimo de 10 caracteres.</p>
              )}
            </div>

            <DialogFooter className="flex-col gap-2 sm:flex-row">
              <Button
                variant="outline"
                onClick={() => setStep("ask")}
                disabled={submitting}
                className="w-full sm:w-auto"
              >
                ← Voltar
              </Button>
              <Button
                onClick={handleConfirm}
                disabled={submitting || contextText.trim().length < 10}
                className="w-full sm:w-auto"
              >
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    A guardar…
                  </>
                ) : (
                  "Confirmar prospecção"
                )}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
