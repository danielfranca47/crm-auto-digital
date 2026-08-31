import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

type ResumeMode = "previously_paused" | "all";

interface BotPauseResumeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (mode: ResumeMode) => Promise<void>;
}

export function BotPauseResumeDialog({ open, onOpenChange, onConfirm }: BotPauseResumeDialogProps) {
  const [mode, setMode] = useState<ResumeMode>("previously_paused");
  const [submitting, setSubmitting] = useState(false);

  const handleOpenChange = (next: boolean) => {
    if (!next && submitting) return;
    onOpenChange(next);
  };

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm(mode);
      handleOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Retomar o bot</DialogTitle>
          <DialogDescription>
            Escolha quais leads devem voltar a receber respostas automáticas.
          </DialogDescription>
        </DialogHeader>

        <RadioGroup value={mode} onValueChange={(v) => setMode(v as ResumeMode)} className="space-y-3">
          <div className="flex items-start space-x-2 rounded-md border border-border p-3">
            <RadioGroupItem value="previously_paused" id="resume-previously-paused" className="mt-1" />
            <Label htmlFor="resume-previously-paused" className="font-normal cursor-pointer">
              <span className="font-medium block">Só os pausados pela pausa geral</span>
              <span className="text-sm text-muted-foreground">
                Reativa apenas os leads que foram pausados quando você clicou em "Pausar". Leads
                pausados manualmente antes continuam pausados.
              </span>
            </Label>
          </div>

          <div className="flex items-start space-x-2 rounded-md border border-border p-3">
            <RadioGroupItem value="all" id="resume-all" className="mt-1" />
            <Label htmlFor="resume-all" className="font-normal cursor-pointer">
              <span className="font-medium block">Reativar todos</span>
              <span className="text-sm text-muted-foreground">
                Reativa todos os leads pausados, incluindo os que foram pausados manualmente.
              </span>
            </Label>
          </div>
        </RadioGroup>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={submitting}>
            Cancelar
          </Button>
          <Button onClick={handleConfirm} disabled={submitting}>
            {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Retomar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
