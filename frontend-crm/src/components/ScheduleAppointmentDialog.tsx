import { useEffect, useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { CalendarIcon, Loader2, Trash2 } from "lucide-react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { useCreateAppointment, useUpdateAppointment, useDeleteAppointment } from "@/hooks/useAppointments";
import { AppointmentType, Appointment } from "@/types/crm";
import { useLeads } from "@/contexts/LeadsContext";
import { ScrollArea } from "@/components/ui/scroll-area";

const appointmentTypeLabels: Record<AppointmentType, string> = {
  meeting: "Reunião",
  call: "Ligação",
  "follow-up": "Follow-up",
  presentation: "Apresentação",
};

interface ScheduleAppointmentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialLeadId?: string | null;
  initialDate?: Date;
  appointmentToEdit?: Appointment | null;
  onSuccess?: (appointment: Appointment) => void;
  /** Quando informado, trava o dialog nesse lead (modo Card do Lead) */
  fixedLeadId?: string;
}

export function ScheduleAppointmentDialog({
  open,
  onOpenChange,
  initialLeadId = null,
  initialDate,
  appointmentToEdit = null,
  onSuccess,
  fixedLeadId,
}: ScheduleAppointmentDialogProps) {
  const { toast } = useToast();

  // Contexto de leads (com fallback seguro para setLeadNextAction)
  const leadsCtx = useLeads();
  const setLeadNextAction =
    ((leadsCtx as any)?.setLeadNextAction as ((leadId: string, next?: any) => void) | undefined) ??
    (() => {});

  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(initialLeadId);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState<AppointmentType>("meeting");
  const [date, setDate] = useState<Date>(initialDate ?? new Date());
  const [time, setTime] = useState("09:00");
  const [endTime, setEndTime] = useState("10:00");
  const [isDateOpen, setIsDateOpen] = useState(false);
  const appointmentIdToEdit = appointmentToEdit?.id ?? null;

  const createMutation = useCreateAppointment();
  const updateMutation = useUpdateAppointment();
  const deleteMutation = useDeleteAppointment();
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);

  // -------- Lista de leads (colunas ativas + arquivadas + fallback do edit) --------
  const allLeads = useMemo(() => {
    const map = new Map<string, { id: string; name: string }>();
    const ingest = (items: any[]) => {
      for (const lead of items ?? []) {
        if (!map.has(lead.id)) {
          map.set(lead.id, {
            id: lead.id,
            name: lead.companyName || lead.contactName || `Lead #${lead.id}`,
          });
        }
      }
    };

    const columns = (leadsCtx as any)?.columns ?? [];
    const archivedColumns = (leadsCtx as any)?.archivedColumns ?? [];

    columns.forEach((c: any) => ingest(c?.leads));
    archivedColumns.forEach((c: any) => ingest(c?.leads));

    const fallbackId = appointmentToEdit?.leadId ?? initialLeadId ?? null;
    if (fallbackId && !map.has(fallbackId)) {
      map.set(fallbackId, {
        id: fallbackId,
        name:
          (appointmentToEdit as any)?.leadName ||
          (appointmentToEdit as any)?.leadCompany ||
          `Lead #${fallbackId}`,
      });
    }

    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [leadsCtx, appointmentToEdit, initialLeadId]);

  // Id efetivo usado na API (fixedLeadId tem prioridade)
  const effectiveLeadId = fixedLeadId ?? selectedLeadId ?? null;

  // Nome amigável do lead quando está travado
  const fixedLeadName = useMemo(() => {
    if (!effectiveLeadId) return null;
    const found = allLeads.find((l) => l.id === effectiveLeadId);
    return (
      found?.name ??
      appointmentToEdit?.leadName ??
      appointmentToEdit?.leadCompany ??
      (effectiveLeadId ? `Lead #${effectiveLeadId}` : null)
    );
  }, [allLeads, effectiveLeadId, appointmentToEdit]);

  // Montagem / reabrir: hidrata o formulário
  useEffect(() => {
    if (!open) return;

    const resolvedLeadId =
      fixedLeadId ??
      appointmentToEdit?.leadId ??
      initialLeadId ??
      null;

    setSelectedLeadId(resolvedLeadId);
    setDate(appointmentToEdit ? new Date(appointmentToEdit.startTime) : initialDate ?? new Date());
    setTitle(appointmentToEdit?.title ?? "");
    setDescription(appointmentToEdit?.description ?? "");
    setType(appointmentToEdit?.type ?? "meeting");

    if (appointmentToEdit) {
      const start = new Date(appointmentToEdit.startTime);
      const hours = String(start.getHours()).padStart(2, "0");
      const minutes = String(start.getMinutes()).padStart(2, "0");
      setTime(`${hours}:${minutes}`);
      if (appointmentToEdit.endTime) {
        const end = new Date(appointmentToEdit.endTime);
        setEndTime(`${String(end.getHours()).padStart(2, "0")}:${String(end.getMinutes()).padStart(2, "0")}`);
      } else {
        const end = new Date(start.getTime() + 60 * 60 * 1000);
        setEndTime(`${String(end.getHours()).padStart(2, "0")}:${String(end.getMinutes()).padStart(2, "0")}`);
      }
    } else if (initialDate) {
      const h = String(initialDate.getHours()).padStart(2, "0");
      const m = String(initialDate.getMinutes()).padStart(2, "0");
      setTime(`${h}:${m}`);
      const endDate = new Date(initialDate.getTime() + 60 * 60 * 1000);
      setEndTime(`${String(endDate.getHours()).padStart(2, "0")}:${String(endDate.getMinutes()).padStart(2, "0")}`);
    } else {
      setTime("09:00");
      setEndTime("10:00");
    }
  }, [open, initialLeadId, initialDate, appointmentToEdit, fixedLeadId]);

  // Ao fechar, limpa o estado
  useEffect(() => {
    if (open) return;
    setSelectedLeadId(initialLeadId ?? null);
    setTitle("");
    setDescription("");
    setType("meeting");
    setDate(initialDate ?? new Date());
    setTime("09:00");
    setEndTime("10:00");
    setIsDateOpen(false);
    setIsConfirmingDelete(false);
  }, [open, initialLeadId, initialDate]);

  // Se nada selecionado e tem leads, escolhe o primeiro (apenas quando não está travado)
  useEffect(() => {
    if (!fixedLeadId && !selectedLeadId && allLeads.length > 0) {
      setSelectedLeadId(allLeads[0].id);
    }
  }, [fixedLeadId, selectedLeadId, allLeads]);

  const isSubmitting = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!effectiveLeadId) {
      toast({
        title: "Selecione um lead",
        description: "Escolha o lead para associar o compromisso.",
        variant: "destructive",
      });
      return;
    }

    if (!date || !time) {
      toast({
        title: "Selecione data e hora",
        variant: "destructive",
      });
      return;
    }

    const [hoursStr, minutesStr] = time.split(":");
    const hours = Number(hoursStr);
    const minutes = Number(minutesStr);
    const startAt = new Date(date);
    startAt.setHours(hours, minutes, 0, 0);

    const [endHoursStr, endMinutesStr] = endTime.split(":");
    const endAt = new Date(date);
    endAt.setHours(Number(endHoursStr), Number(endMinutesStr), 0, 0);
    // Se hora de fim <= início, soma 1h automaticamente
    if (endAt <= startAt) {
      endAt.setTime(startAt.getTime() + 60 * 60 * 1000);
    }

    const payload = {
      leadId: effectiveLeadId,
      title: title || appointmentTypeLabels[type],
      description: description || undefined,
      type,
      startTime: startAt.toISOString(),
      endTime: endAt.toISOString(),
    };

    try {
      let result: Appointment;
      if (appointmentToEdit) {
        const response = await updateMutation.mutateAsync({
          id: appointmentToEdit.id,
          data: payload,
          leadId: effectiveLeadId as string,
        });
        result = response;
        toast({ title: "Compromisso atualizado" });
      } else {
        const response = await createMutation.mutateAsync(payload);
        result = response;
        toast({ title: "Compromisso criado" });
      }

      if (result.leadId) {
        setLeadNextAction(result.leadId, {
          id: result.id,
          date: new Date(result.startTime),
          description: result.title,
          type: result.type,
        });
      }

      onSuccess?.(result);
      onOpenChange(false);
    } catch (error: any) {
      toast({
        title: "Erro ao salvar compromisso",
        description: error?.message ?? "Não foi possível salvar o compromisso.",
        variant: "destructive",
      });
    }
  };

  const handleDelete = async () => {
    if (!appointmentToEdit) return;
    if (!isConfirmingDelete) {
      setIsConfirmingDelete(true);
      return;
    }
    try {
      const arg = effectiveLeadId
        ? { id: appointmentToEdit.id, leadId: effectiveLeadId }
        : appointmentToEdit.id;
      await deleteMutation.mutateAsync(arg as any);
      toast({ title: "Compromisso excluído" });
      onSuccess?.(appointmentToEdit);
      onOpenChange(false);
    } catch (error: any) {
      toast({
        title: "Erro ao excluir compromisso",
        description: error?.message ?? "Não foi possível excluir o compromisso.",
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {appointmentIdToEdit ? "Editar compromisso" : "Agendar compromisso"}
          </DialogTitle>
          <DialogDescription>
            Preencha os detalhes para registrar o compromisso na agenda.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Lead */}
          <div className="space-y-2">
            <Label htmlFor="lead">Lead</Label>

            {fixedLeadId ? (
              // Modo CARD: lead travado (sem lista)
              <div className="rounded-md border border-border bg-muted/50 px-3 py-2 text-sm">
                <span className="font-medium">Selecionado:</span>{" "}
                <span className="inline-flex items-center gap-2">
                  <span className="rounded-full px-2 py-0.5 bg-primary/10 text-primary border border-primary/20">
                    #{fixedLeadId}
                  </span>
                  <span className="text-foreground">{fixedLeadName}</span>
                </span>
              </div>
            ) : (
              // Modo DASHBOARD: lista de leads
              <ScrollArea className="h-24 rounded-md border border-border">
                <div className="p-2 space-y-1">
                  {allLeads.map((lead) => (
                    <button
                      key={lead.id}
                      type="button"
                      onClick={() => setSelectedLeadId(lead.id)}
                      className={cn(
                        "w-full text-left text-sm px-3 py-2 rounded-md border transition-smooth",
                        selectedLeadId === lead.id
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-background hover:bg-muted border-border"
                      )}
                      disabled={isSubmitting}
                    >
                      {lead.name}
                    </button>
                  ))}
                  {allLeads.length === 0 && (
                    <p className="text-xs text-muted-foreground px-3 py-2">
                      Nenhum lead disponível. Cadastre um lead antes de agendar.
                    </p>
                  )}
                </div>
              </ScrollArea>
            )}
          </div>

          {/* Tipo e Horários */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="type">Tipo</Label>
              <div className="flex flex-wrap gap-2">
                {(Object.keys(appointmentTypeLabels) as AppointmentType[]).map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setType(key)}
                    className={cn(
                      "px-3 py-1 rounded-full border text-sm transition-smooth",
                      type === key
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-background border-border hover:bg-muted"
                    )}
                    disabled={isSubmitting}
                  >
                    {appointmentTypeLabels[key]}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label>Horário</Label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Início</p>
                  <Input
                    id="time"
                    type="time"
                    value={time}
                    onChange={(event) => setTime(event.target.value)}
                    disabled={isSubmitting}
                  />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Fim</p>
                  <Input
                    id="endTime"
                    type="time"
                    value={endTime}
                    onChange={(event) => setEndTime(event.target.value)}
                    disabled={isSubmitting}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Data */}
          <div className="space-y-2">
            <Label>Data</Label>
            <Popover open={isDateOpen} onOpenChange={setIsDateOpen}>
              <PopoverTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className={cn(
                    "w-full justify-start text-left font-normal",
                    !date && "text-muted-foreground"
                  )}
                  disabled={isSubmitting}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {date ? format(date, "PPP", { locale: ptBR }) : "Selecione uma data"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={date}
                  onSelect={(selected) => {
                    if (selected) {
                      setDate(selected);
                      setIsDateOpen(false);
                    }
                  }}
                  initialFocus
                />
              </PopoverContent>
            </Popover>
          </div>

          {/* Título */}
          <div className="space-y-2">
            <Label htmlFor="title">Título</Label>
            <Input
              id="title"
              placeholder="Ex: Reunião de apresentação"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              disabled={isSubmitting}
            />
          </div>

          {/* Descrição */}
          <div className="space-y-2">
            <Label htmlFor="description">Descrição</Label>
            <Textarea
              id="description"
              placeholder="Detalhes adicionais, link da reunião, objetivos..."
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              disabled={isSubmitting}
            />
          </div>

          <DialogFooter className="flex-col sm:flex-row sm:justify-between gap-2">
            {appointmentToEdit && (
              <Button
                type="button"
                variant={isConfirmingDelete ? "destructive" : "outline"}
                className={isConfirmingDelete ? "" : "text-destructive border-destructive/40 hover:bg-destructive/10"}
                onClick={handleDelete}
                disabled={isSubmitting}
              >
                {deleteMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="mr-2 h-4 w-4" />
                )}
                {isConfirmingDelete ? "Confirmar exclusão" : "Excluir"}
              </Button>
            )}
            <div className="flex gap-2 justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  if (isConfirmingDelete) {
                    setIsConfirmingDelete(false);
                  } else {
                    onOpenChange(false);
                  }
                }}
                disabled={isSubmitting}
              >
                {isConfirmingDelete ? "Manter" : "Cancelar"}
              </Button>
              {!isConfirmingDelete && (
                <Button type="submit" disabled={isSubmitting || (!fixedLeadId && allLeads.length === 0)}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {appointmentToEdit ? "Salvar alterações" : "Agendar"}
                </Button>
              )}
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
