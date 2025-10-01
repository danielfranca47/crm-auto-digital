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
import { CalendarIcon, Loader2 } from "lucide-react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { useCreateAppointment, useUpdateAppointment } from "@/hooks/useAppointments";
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
}

export function ScheduleAppointmentDialog({
  open,
  onOpenChange,
  initialLeadId = null,
  initialDate,
  appointmentToEdit = null,
  onSuccess,
}: ScheduleAppointmentDialogProps) {
  const { toast } = useToast();
  const { columns, archivedColumns, setLeadNextAction } = useLeads();
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(initialLeadId);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState<AppointmentType>("meeting");
  const [date, setDate] = useState<Date>(initialDate ?? new Date());
  const [time, setTime] = useState("09:00");
  const [isDateOpen, setIsDateOpen] = useState(false);
  const appointmentIdToEdit = appointmentToEdit?.id ?? null;

  const createMutation = useCreateAppointment();
  const updateMutation = useUpdateAppointment();

  useEffect(() => {
    if (!open) return;

    setSelectedLeadId(appointmentToEdit?.leadId ?? initialLeadId ?? null);
    setDate(appointmentToEdit ? new Date(appointmentToEdit.startTime) : initialDate ?? new Date());
    setTime("09:00");
    setTitle(appointmentToEdit?.title ?? "");
    setDescription(appointmentToEdit?.description ?? "");
    setType(appointmentToEdit?.type ?? "meeting");

    if (appointmentToEdit) {
      const start = new Date(appointmentToEdit.startTime);
      const hours = String(start.getHours()).padStart(2, "0");
      const minutes = String(start.getMinutes()).padStart(2, "0");
      setTime(`${hours}:${minutes}`);
    }
  }, [open, initialLeadId, initialDate, appointmentToEdit]);

  const allLeads = useMemo(() => {
    const map = new Map<string, { id: string; name: string }>();
    const ingest = (items: typeof columns[number]["leads"]) => {
      for (const lead of items) {
        if (!map.has(lead.id)) {
          map.set(lead.id, {
            id: lead.id,
            name: lead.companyName || lead.contactName || `Lead #${lead.id}`,
          });
        }
      }
    };
    columns.forEach((column) => ingest(column.leads));
    archivedColumns.forEach((column) => ingest(column.leads));
    const fallbackId = appointmentToEdit?.leadId ?? initialLeadId ?? null;
    if (fallbackId && !map.has(fallbackId)) {
      map.set(fallbackId, {
        id: fallbackId,
        name:
          appointmentToEdit?.leadName ||
          appointmentToEdit?.leadCompany ||
          `Lead #${fallbackId}`,
      });
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [columns, archivedColumns, appointmentToEdit, initialLeadId]);

  useEffect(() => {
    if (!selectedLeadId && allLeads.length > 0) {
      setSelectedLeadId(allLeads[0].id);
    }
  }, [selectedLeadId, allLeads]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedLeadId) {
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

    const payload = {
      leadId: selectedLeadId,
      title: title || appointmentTypeLabels[type],
      description: description || undefined,
      type,
      startTime: startAt.toISOString(),
    };

    try {
      let result: Appointment;
      if (appointmentToEdit) {
        const response = await updateMutation.mutateAsync({
          id: appointmentToEdit.id,
          data: payload,
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

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

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
          <div className="space-y-2">
            <Label htmlFor="lead">Lead</Label>
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
          </div>

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
              <Label htmlFor="time">Hora</Label>
              <Input
                id="time"
                type="time"
                value={time}
                onChange={(event) => setTime(event.target.value)}
                disabled={isSubmitting}
              />
            </div>
          </div>

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

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting || allLeads.length === 0}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {appointmentToEdit ? "Salvar alterações" : "Agendar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
