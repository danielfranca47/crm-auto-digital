import { Lead, LeadStatus, Appointment } from "../types/crm";
import { QualificationField } from "../types/agente";
import {
  Calendar,
  Building2,
  User,
  Phone,
  Mail,
  MessageSquare,
  Clock,
  Tag,
  Plus,
  RefreshCw,
  AlertTriangle,
  Zap,
  ExternalLink,
  ClipboardCheck,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "./ui/alert-dialog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Separator } from "./ui/separator";
import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ScheduleAppointmentDialog } from "./ScheduleAppointmentDialog";
import { useLeadAppointments, useCancelAppointment } from "@/hooks/useAppointments";
import { useToast } from "@/hooks/use-toast";
import { useLeads } from "@/contexts/LeadsContext";
import { api, FollowUpContract } from "@/services/api";

interface LeadCardDialogProps {
  lead: Lead | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdateLead?: (leadId: string, updates: Partial<Lead>) => void;
  onDeleteLead?: (leadId: string) => Promise<void>;
}

//TODO Estava dando erros aqui, com nomes de colunas antigas. Ajustei conforme as atuais.
/** Cores/labels de status (alinhado com mockData.ts) */
//Ela era basicamente a "tabela de tradução" dos status do lead – o dicionário que dizia: qual nome amigável mostrar na telaqual cor usar em cada statusE isso era usado dentro do componente LeadCardDialog para montar aquele selo colorido (badge/pílula) que aparece no card do lead.
const statusColors: Record<LeadStatus, string> = {
  "to-prospect": "bg-gray-500",        // À Prospectar
  "qualification": "bg-sky-500",       // Qualificação
  "apresentation": "bg-blue-500",      // Apresentação
  "follow-up": "bg-yellow-500",        // Follow-up
  "closing": "bg-purple-500",          // Fechamento
  "client-list": "bg-emerald-600",     // Lista de clientes

  // Secundários (prospecção / arquivados)
  "in-progress": "bg-indigo-500",      // Em andamento
  "prospect-refused": "bg-red-500",    // Prospecção recusada
  "disqualified": "bg-red-600",        // Desqualificado
};


const statusLabels: Record<LeadStatus, string> = {
  "to-prospect": "À Prospectar",
  "qualification": "Qualificação",
  "apresentation": "Apresentação",
  "follow-up": "Follow-up",
  "closing": "Fechamento",
  "client-list": "Lista de Clientes",

  "in-progress": "Em Andamento",
  "prospect-refused": "Prospecção Recusada",
  "disqualified": "Desqualificado",
};
//

const appointmentTypeLabels = {
  meeting: "Reunião",
  call: "Ligação",
  "follow-up": "Follow-up",
  presentation: "Apresentação",
} as const;

const appointmentTypeClasses = {
  meeting: "bg-primary/10 text-primary border border-primary/20",
  call: "bg-success/10 text-success border border-success/20",
  "follow-up": "bg-warning/10 text-warning border border-warning/20",
  presentation: "bg-info/10 text-info border border-info/20",
} as const;

const appointmentStatusLabels = {
  pending: "Agendado",
  completed: "Concluído",
  canceled: "Cancelado",
} as const;

const appointmentStatusClasses = {
  pending: "bg-primary/10 text-primary border border-primary/20",
  completed: "bg-success/10 text-success border border-success/20",
  canceled: "bg-destructive/10 text-destructive border border-destructive/20",
} as const;

const appointmentOutcomeLabels = {
  completed: "Concluída",
  no_show: "No-show",
  rescheduled: "Reagendada",
} as const;

const appointmentOutcomeClasses = {
  completed: "bg-success/10 text-success border border-success/20",
  no_show: "bg-destructive/10 text-destructive border border-destructive/20",
  rescheduled: "bg-primary/10 text-primary border border-primary/20",
} as const;

const FOLLOWUP_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  active:    { label: "Ativo",      color: "#52C4A0" },
  paused:    { label: "Pausado",    color: "#F59E0B" },
  done:      { label: "Concluído",  color: "#60A5FA" },
  cancelled: { label: "Cancelado",  color: "#94A3B8" },
};

const FOLLOWUP_VARIANT_CONFIG: Record<string, { label: string; color: string }> = {
  cart_recovery:    { label: "Carrinho",  color: "#52C4A0" },
  hybrid_scheduler: { label: "Híbrido",   color: "#A78BFA" },
  sdr_scheduler:    { label: "SDR",       color: "#60A5FA" },
};

const STOP_REASON_LABELS: Record<string, string> = {
  inbound_reply:        "Lead respondeu",
  max_attempts_reached: "Limite de tentativas atingido",
  manual_cancel:        "Cancelado manualmente",
  deal_closed:          "Negócio fechado",
  explicit_rejection:   "Rejeição explícita",
  handoff_human:        "Passado para humano",
};

function FollowUpContractSummary({ contract }: { contract: FollowUpContract }) {
  const statusCfg = FOLLOWUP_STATUS_CONFIG[contract.status] ?? { label: contract.status, color: "#94A3B8" };
  const variantCfg = contract.followup_variant ? FOLLOWUP_VARIANT_CONFIG[contract.followup_variant] : null;

  const fmt = (iso: string | null | undefined) =>
    iso
      ? new Intl.DateTimeFormat("pt-PT", {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        }).format(new Date(iso))
      : null;

  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 space-y-2.5 text-sm">
      {/* Status + variant + attempts */}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className="text-[11px] font-medium px-2 py-0.5 rounded-full border"
          style={{ background: statusCfg.color + "22", color: statusCfg.color, borderColor: statusCfg.color + "55" }}
        >
          {statusCfg.label}
        </span>
        {variantCfg && (
          <span
            className="text-[11px] font-medium px-2 py-0.5 rounded-full border"
            style={{ background: variantCfg.color + "22", color: variantCfg.color, borderColor: variantCfg.color + "55" }}
          >
            {variantCfg.label}
          </span>
        )}
        <div className="flex items-center gap-1.5 ml-auto text-muted-foreground text-xs">
          <span>{contract.attempts}/{contract.max_attempts} envios</span>
          <div className="flex gap-1">
            {Array.from({ length: contract.max_attempts }).map((_, i) => (
              <span
                key={i}
                className="inline-block rounded-full"
                style={{
                  width: 7,
                  height: 7,
                  background: i < contract.attempts ? statusCfg.color : statusCfg.color + "33",
                }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Datas */}
      <div className="space-y-1 text-xs text-muted-foreground">
        {contract.last_followup_at && (
          <div className="flex items-center gap-1.5">
            <Clock className="w-3 h-3 shrink-0" />
            <span>Último envio: <span className="text-foreground/80">{fmt(contract.last_followup_at)}</span></span>
          </div>
        )}
        {contract.next_followup_at && contract.status === "active" && (
          <div className="flex items-center gap-1.5">
            <Calendar className="w-3 h-3 shrink-0" />
            <span>Próximo envio: <span className="text-foreground/80">{fmt(contract.next_followup_at)}</span></span>
          </div>
        )}
        {contract.stop_reason && (
          <div className="flex items-center gap-1.5">
            <Tag className="w-3 h-3 shrink-0" />
            <span>Motivo: <span className="text-foreground/80">{STOP_REASON_LABELS[contract.stop_reason] ?? contract.stop_reason}</span></span>
          </div>
        )}
        {contract.operator_note && (
          <div className="flex items-center gap-1.5 pt-0.5 border-t border-border">
            <MessageSquare className="w-3 h-3 shrink-0" />
            <span className="italic">{contract.operator_note}</span>
          </div>
        )}
      </div>
    </div>
  );
}

/** Wrapper sem hooks — evita o erro de Hooks. */
export function LeadCardDialog({ lead, isOpen, onClose, onUpdateLead, onDeleteLead }: LeadCardDialogProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      {isOpen && lead ? (
        <LeadCardDialogBody
          lead={lead}
          isOpen={isOpen}
          onClose={onClose}
          onUpdateLead={onUpdateLead}
          onDeleteLead={onDeleteLead}
        />
      ) : null}
    </Dialog>
  );
}

/** Body com os hooks — só é montado quando isOpen && lead. */
function LeadCardDialogBody({
  lead,
  onClose,
  onUpdateLead,
  onDeleteLead,
}: LeadCardDialogProps & { lead: Lead }) {
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [editedLead, setEditedLead] = useState<Lead | null>(null);
  const { toast } = useToast();

  // Contexto + fallback no-op
  const leadsCtx = useLeads();
  const setLeadNextAction =
    ((leadsCtx as any)?.setLeadNextAction as ((leadId: string, next?: any) => void) | undefined) ??
    (() => {});

  const cancelAppointment = useCancelAppointment();
  const [isScheduleDialogOpen, setIsScheduleDialogOpen] = useState(false);
  const [appointmentToEdit, setAppointmentToEdit] = useState<Appointment | null>(null);
  const [rescheduleOutcomeId, setRescheduleOutcomeId] = useState<string | null>(null);
  const [showDisableModal, setShowDisableModal] = useState(false);
  const [showReactivateWarningModal, setShowReactivateWarningModal] = useState(false);
  const [disableAware, setDisableAware] = useState(false);
  const [reactivateAware, setReactivateAware] = useState(false);
  const [qualifFields, setQualifFields] = useState<Record<string, string>>({});
  const [aiQualFields, setAiQualFields] = useState<QualificationField[]>([]);
  const [isEditingQualif, setIsEditingQualif] = useState(false);
  const [editingQualif, setEditingQualif] = useState<Record<string, string>>({});

  // Carrega compromissos do lead (rota: GET /leads/{id}/appointments)
  const leadId = lead?.id;

  const {
    data: appointments = [],
    isLoading: isLoadingAppointments,
    isError: appointmentsError,
    refetch: refetchAppointments,
  } = useLeadAppointments(leadId, { enabled: !!leadId });

  // Refetch ao abrir
  useEffect(() => {
    refetchAppointments();
  }, [refetchAppointments]);

  // Carga dos critérios de qualificação e campos do AI Profile
  useEffect(() => {
    if (!lead?.id) return;
    void Promise.all([
      api.getLeadQualificationFields(Number(lead.id)),
      api.core.getAiProfileMe(),
    ]).then(([qRes, profileRes]) => {
      setQualifFields((qRes as any)?.fields ?? {});
      setAiQualFields((profileRes as any)?.qualification_fields ?? []);
    });
  }, [lead?.id]);

  // Mensagens WhatsApp para histórico de follow-up
  const { data: messagesData } = useQuery({
    queryKey: ["lead-messages", leadId],
    queryFn: () => api.assistenteIA.mensagens(leadId!, false),
    enabled: !!leadId && !!lead.followup_contract,
    staleTime: 60_000,
  });

  const asDate = (iso: string) => new Date(iso);
  const isActiveStatus = (s?: string | null) =>
    ["pending"].includes(String(s));

  // Itens futuros **não cancelados**
  const upcomingAppointments = useMemo(() => {
    const nowTs = Date.now();

    return appointments
      .filter((a) => {
        if (a.status === "canceled") return false;
        if (!isActiveStatus(a.status)) return false; // só "pending"
        const ts = new Date(a.startTime).getTime();
        return Number.isFinite(ts) && ts >= nowTs;
      })
      .sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime());
  }, [appointments]);

  const nextMeetingAppointment = useMemo(() => {
    const nowTs = Date.now();
    return (
      appointments
        .filter((appointment) => {
          const isMeetingType = ["meeting", "presentation"].includes(String(appointment.type));
          const normalizedStatus = String(appointment.status) === "scheduled" ? "pending" : String(appointment.status);
          const startsAt = new Date(appointment.startTime).getTime();
          return isMeetingType && normalizedStatus === "pending" && Number.isFinite(startsAt) && startsAt >= nowTs;
        })
        .sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime())[0] ?? null
    );
  }, [appointments]);

  // Itens passados **não cancelados**
  const pastAppointments = useMemo(() => {
    const nowTs = Date.now();

    return appointments
      .filter((a) => {
        if (a.status === "canceled") return false;
        const ts = new Date(a.startTime).getTime();
        return Number.isFinite(ts) && ts < nowTs;
      })
      .sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime());
  }, [appointments]);

    useEffect(() => {
      setEditedLead({ ...lead });
    }, [lead]);

  const formatDate = (date: Date) =>
    new Intl.DateTimeFormat("pt-PT", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);

  const handleSave = () => {
    if (editedLead && onUpdateLead) {
      onUpdateLead(lead.id, editedLead);
      setIsEditing(false);
    }
  };

  const handleDeleteLead = async () => {
    if (!onDeleteLead) return;
    const confirmed = window.confirm(
      "Tem certeza? Isso apagará histórico e compromissos deste lead."
    );
    if (!confirmed) return;
    await onDeleteLead(lead.id);
    onClose();
  };

  const handleCancel = () => {
    setEditedLead({ ...lead });
    setIsEditing(false);
  };

  const openScheduleDialog = (appointment?: Appointment | null) => {
    setAppointmentToEdit(appointment ?? null);
    setIsScheduleDialogOpen(true);
  };

  const handleRescheduleOutcome = (appointment: Appointment) => {
    setRescheduleOutcomeId(appointment.id);
    openScheduleDialog(appointment);
  };

  const handleCancelAppointmentAction = async (appointment: Appointment) => {
    try {
      await cancelAppointment.mutateAsync({ id: appointment.id, leadId: lead.id });
      setLeadNextAction(lead.id, undefined);
      setEditedLead((prev) => (prev ? { ...prev, nextScheduledAction: undefined } : prev));
      onUpdateLead?.(lead.id, { nextScheduledAction: undefined } as Partial<Lead>);
      toast({ title: "Compromisso cancelado" });
      refetchAppointments();
    } catch (error: any) {
      toast({
        title: "Erro ao cancelar compromisso",
        description: error?.message ?? "Não foi possível cancelar o compromisso.",
        variant: "destructive",
      });
    }
  };

  const handleAppointmentSuccess = (appointment: Appointment) => {
    const nextAction = {
      id: appointment.id,
      date: new Date(appointment.startTime),
      description: appointment.title,
      type: appointment.type,
    };

    setLeadNextAction(lead.id, nextAction);
    setEditedLead((prev) => (prev ? { ...prev, nextScheduledAction: nextAction } : prev));
    onUpdateLead?.(lead.id, { nextScheduledAction: nextAction } as Partial<Lead>);
    setIsScheduleDialogOpen(false);
    setAppointmentToEdit(null);
    refetchAppointments();

    if (rescheduleOutcomeId && appointment.id === rescheduleOutcomeId) {
      api.appointments
        .setOutcome(appointment.id, {
          outcome: "rescheduled",
          reschedule_start_at: appointment.startTime,
          reschedule_end_at: appointment.endTime ?? null,
          reactivate_bot: true,
        })
        .then(() => {
          setEditedLead((prev) => (prev ? { ...prev, bot_disabled: false } : prev));
          onUpdateLead?.(lead.id, { bot_disabled: false } as Partial<Lead>);
          toast({ title: "Compromisso reagendado" });
          refetchAppointments();
        })
        .catch((error: any) => {
          toast({
            title: "Erro ao reagendar compromisso",
            description: error?.message ?? "Não foi possível reagendar o compromisso.",
            variant: "destructive",
          });
        })
        .finally(() => {
          setRescheduleOutcomeId(null);
        });
    }
  };

  const handleDisableBot = async () => {
    try {
      await api.setLeadBotDisabled(lead.id, { disabled: true, reason: "manual_disable" });
      setEditedLead((prev) =>
        prev ? { ...prev, bot_disabled: true, bot_disabled_reason: "manual_disable" } : prev
      );
      onUpdateLead?.(lead.id, {
        bot_disabled: true,
        bot_disabled_reason: "manual_disable",
      } as Partial<Lead>);
      toast({ title: "Bot desativado para este lead" });
    } catch (error: any) {
      toast({
        title: "Erro ao desativar bot",
        description: error?.message ?? "Não foi possível desativar o bot.",
        variant: "destructive",
      });
    } finally {
      setShowDisableModal(false);
      setDisableAware(false);
    }
  };

  const handleReactivateBot = async () => {
    if (currentLead.bot_disabled_reason === "manual_disable" && !showReactivateWarningModal) {
      setShowReactivateWarningModal(true);
      return;
    }
    try {
      await api.setLeadBotDisabled(lead.id, {
        disabled: false,
        reason: "manual_reactivate",
      });
      setEditedLead((prev) =>
        prev ? { ...prev, bot_disabled: false, bot_disabled_reason: null } : prev
      );
      onUpdateLead?.(lead.id, {
        bot_disabled: false,
        bot_disabled_reason: null,
      } as Partial<Lead>);
      toast({ title: "Bot reativado" });
    } catch (error: any) {
      toast({
        title: "Erro ao reativar bot",
        description: error?.message ?? "Não foi possível reativar o bot.",
        variant: "destructive",
      });
    } finally {
      setShowReactivateWarningModal(false);
      setReactivateAware(false);
    }
  };

  const currentLead = isEditing ? editedLead! : lead;
  const botPauseReason = useMemo(() => {
    if (!currentLead?.bot_disabled) return null;
    if (nextMeetingAppointment) return "Reunião agendada";
    const rawReason = (currentLead.bot_disabled_reason || "").trim();
    if (rawReason === "category_closing") return "Closing (humano assume)";
    if (rawReason === "manual_disable") return "Desativado manualmente";
    if (rawReason) return rawReason;
    if (currentLead.category === "closing") return "Closing (humano assume)";
    return "Motivo indisponível";
  }, [
    currentLead?.bot_disabled,
    currentLead?.bot_disabled_reason,
    currentLead?.category,
    nextMeetingAppointment,
  ]);

  const nextScheduledAppointment = useMemo(() => {
    const appointmentId = currentLead.nextScheduledAction?.id;
    if (!appointmentId) return null;

    const appt = appointments.find(a => a.id === appointmentId) ?? null;
    // se o compromisso foi cancelado, não consideramos como "próxima ação"
    return appt && appt.status !== "canceled" ? appt : null;
  }, [appointments, currentLead.nextScheduledAction?.id]);

  const qualifPendingCount = useMemo(() => {
    const required = aiQualFields.filter(f => f.mode === "required").map(f => f.key);
    return required.filter(k => !qualifFields[k]?.trim()).length;
  }, [aiQualFields, qualifFields]);

  const handleSaveQualification = async () => {
    try {
      await api.patchLeadQualificationFields(Number(lead!.id), editingQualif);
      setQualifFields(editingQualif);
      setIsEditingQualif(false);
      toast({ title: "Qualificação atualizada" });
    } catch (error: any) {
      toast({ title: "Erro ao salvar qualificação", description: error?.message, variant: "destructive" });
    }
  };

  const handleSetOutcome = async (
    appointment: Appointment,
    outcome: "completed" | "no_show"
  ) => {
    const note = window.prompt("Observação (opcional):") ?? undefined;
    try {
      await api.appointments.setOutcome(appointment.id, {
        outcome,
        note,
        reactivate_bot: true,
      });
      setEditedLead((prev) => (prev ? { ...prev, bot_disabled: false } : prev));
      onUpdateLead?.(lead.id, { bot_disabled: false } as Partial<Lead>);
      toast({ title: "Resultado registrado" });
      refetchAppointments();
    } catch (error: any) {
      toast({
        title: "Erro ao registrar resultado",
        description: error?.message ?? "Não foi possível registrar o resultado.",
        variant: "destructive",
      });
    }
  };


  return (
    <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <DialogTitle className="text-xl font-semibold text-foreground">
              {currentLead.companyName || currentLead.contactName}
            </DialogTitle>
            <div className="flex items-center gap-2">
              <Badge className={`${statusColors[currentLead.category]} text-white`}>
                {statusLabels[currentLead.category]}
              </Badge>
              {currentLead.bot_disabled && (
                <Badge variant="secondary">Agente desativado</Badge>
              )}
              <span className="text-xs text-muted-foreground">ID: {currentLead.id}</span>
            </div>
          </div>
          <div className="flex gap-2">
            {!currentLead.bot_disabled && (
              <Button variant="outline" size="sm" onClick={() => setShowDisableModal(true)}>
                Desativar bot
              </Button>
            )}
            <Button variant="destructive" size="sm" onClick={() => void handleDeleteLead()}>
              Excluir
            </Button>
            {!isEditing ? (
              <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
                Editar
              </Button>
            ) : (
              <>
                <Button variant="outline" size="sm" onClick={handleCancel}>
                  Cancelar
                </Button>
                <Button size="sm" onClick={handleSave}>
                  Salvar
                </Button>
              </>
            )}
          </div>
        </div>
      </DialogHeader>

      <div className="space-y-6">
        {currentLead.bot_disabled && (
          <div className="rounded-md border border-warning/30 bg-warning/10 p-4 space-y-2">
            <div className="flex items-center gap-2 text-warning font-medium">
              <AlertTriangle className="h-4 w-4" />
              ⚠️ Bot pausado
            </div>
            <p className="text-sm text-foreground">
              <span className="font-medium">Motivo:</span> {botPauseReason}
            </p>
            {nextMeetingAppointment && (
              <p className="text-sm text-foreground">
                <span className="font-medium">Data:</span> {formatDate(new Date(nextMeetingAppointment.startTime))}
              </p>
            )}
            <Button size="sm" variant="outline" onClick={() => void handleReactivateBot()}>
              Reativar bot
            </Button>
          </div>
        )}

        {/* Informações Básicas */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-foreground flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            Informações Básicas
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="companyName" className="text-sm font-medium">
                Nome da Empresa
              </Label>
              {isEditing ? (
                <Input
                  id="companyName"
                  value={editedLead?.companyName || ""}
                  onChange={(e) =>
                    setEditedLead((prev) => (prev ? { ...prev, companyName: e.target.value } : null))
                  }
                  placeholder="Nome da empresa"
                />
              ) : (
                <p className="text-sm text-foreground">
                  {currentLead.companyName || "Não informado"}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="contactName" className="text-sm font-medium">
                Nome do Contato
              </Label>
              {isEditing ? (
                <Input
                  id="contactName"
                  value={editedLead?.contactName || ""}
                  onChange={(e) =>
                    setEditedLead((prev) => (prev ? { ...prev, contactName: e.target.value } : null))
                  }
                  placeholder="Nome do contato"
                />
              ) : (
                <div className="flex items-center gap-2 text-sm text-foreground">
                  <User className="h-4 w-4" />
                  {currentLead.contactName}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone" className="text-sm font-medium">
                Telefone
              </Label>
              {isEditing ? (
                <Input
                  id="phone"
                  value={editedLead?.phone || ""}
                  onChange={(e) =>
                    setEditedLead((prev) => (prev ? { ...prev, phone: e.target.value } : null))
                  }
                  placeholder="Telefone"
                />
              ) : (
                <div className="flex items-center gap-2 text-sm text-foreground">
                  <Phone className="h-4 w-4" />
                  {currentLead.phone}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium">
                Email
              </Label>
              {isEditing ? (
                <Input
                  id="email"
                  type="email"
                  value={editedLead?.email || ""}
                  onChange={(e) =>
                    setEditedLead((prev) => (prev ? { ...prev, email: e.target.value } : null))
                  }
                  placeholder="Email"
                />
              ) : (
                <div className="flex items-center gap-2 text-sm text-foreground">
                  <Mail className="h-4 w-4" />
                  {currentLead.email || "Não informado"}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="origin" className="text-sm font-medium">
              Fonte do Lead
            </Label>
            {isEditing ? (
              <Input
                id="origin"
                value={editedLead?.origin || ""}
                onChange={(e) =>
                  setEditedLead((prev) => (prev ? { ...prev, origin: e.target.value } : null))
                }
                placeholder="Ex: Indicação, Website, Google Ads..."
              />
            ) : (
              <div className="flex items-center gap-2 text-sm text-foreground">
                <Tag className="h-4 w-4" />
                {currentLead.origin}
              </div>
            )}
          </div>
        </div>

        <Separator />

        {/* Mensagens e Notas */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-foreground flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            Mensagens e Notas
          </h3>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="customMessage" className="text-sm font-medium">
                Mensagem Personalizada
              </Label>
              {isEditing ? (
                <Textarea
                  id="customMessage"
                  value={editedLead?.customMessage || ""}
                  onChange={(e) =>
                    setEditedLead((prev) => (prev ? { ...prev, customMessage: e.target.value } : null))
                  }
                  placeholder="Mensagem personalizada para este lead..."
                  rows={3}
                />
              ) : (
                <p className="text-sm text-foreground bg-muted p-3 rounded-md">
                  {currentLead.customMessage || "Nenhuma mensagem personalizada"}
                </p>
              )}
            </div>

            {/* Critérios de Qualificação */}
            {aiQualFields.length > 0 && (
              <div className="space-y-3 border border-border rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ClipboardCheck className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">Critérios de Qualificação</span>
                    {qualifPendingCount > 0 ? (
                      <Badge variant="destructive" className="text-xs">
                        {qualifPendingCount} pendente{qualifPendingCount > 1 ? "s" : ""}
                      </Badge>
                    ) : (
                      <Badge className="text-xs bg-green-600 text-white hover:bg-green-600">Completo</Badge>
                    )}
                  </div>
                  {!isEditingQualif ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => { setIsEditingQualif(true); setEditingQualif({ ...qualifFields }); }}
                    >
                      Editar
                    </Button>
                  ) : (
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => setIsEditingQualif(false)}>
                        Cancelar
                      </Button>
                      <Button size="sm" onClick={() => void handleSaveQualification()}>
                        Salvar
                      </Button>
                    </div>
                  )}
                </div>
                <div className="space-y-3">
                  {aiQualFields.map(field => (
                    <div key={field.key}>
                      <p className="text-xs text-muted-foreground mb-1">
                        {field.label}
                        {field.mode === "required" && <span className="text-destructive ml-1">*</span>}
                      </p>
                      {isEditingQualif ? (
                        <Input
                          value={editingQualif[field.key] ?? ""}
                          onChange={e => setEditingQualif(prev => ({ ...prev, [field.key]: e.target.value }))}
                          placeholder={field.question ?? `Preencher ${field.label.toLowerCase()}...`}
                          className="h-8 text-sm"
                        />
                      ) : (
                        <p className="text-sm">
                          {qualifFields[field.key]?.trim()
                            ? qualifFields[field.key]
                            : <span className="text-muted-foreground italic">Não preenchido</span>}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="observations" className="text-sm font-medium">
                Comentários/Notas
              </Label>
              {isEditing ? (
                <Textarea
                  id="observations"
                  value={editedLead?.observations || ""}
                  onChange={(e) =>
                    setEditedLead((prev) => (prev ? { ...prev, observations: e.target.value } : null))
                  }
                  placeholder="Comentários e observações internas..."
                  rows={3}
                />
              ) : (
                <p className="text-sm text-foreground bg-muted p-3 rounded-md">
                  {currentLead.observations || "Nenhuma observação"}
                </p>
              )}
            </div>
          </div>
        </div>

        <Separator />

        {/* Datas e Ações */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-foreground flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Cronologia e Ações
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Data de Criação</Label>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Calendar className="h-4 w-4" />
                {formatDate(currentLead.createdAt)}
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Última Interação</Label>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Calendar className="h-4 w-4" />
                {formatDate(currentLead.lastMovement)}
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-sm font-medium">Próxima Ação Agendada</Label>
            <div className="bg-muted p-3 rounded-md space-y-2">
              {nextScheduledAppointment ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <Calendar className="h-4 w-4" />
                    {formatDate(new Date(nextScheduledAppointment.startTime))}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {nextScheduledAppointment.title}
                  </p>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Plus className="h-4 w-4" />
                  Nenhuma ação agendada
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => openScheduleDialog()}>
                  <Plus className="h-3 w-3 mr-2" />
                  Agendar follow-up
                </Button>

                {nextScheduledAppointment && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleRescheduleOutcome(nextScheduledAppointment)}
                    >
                      Reagendar
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => handleCancelAppointmentAction(nextScheduledAppointment)}
                    >
                      Cancelar
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        <Separator />

        {/* Compromissos */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-foreground flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Compromissos
            </h3>
            <div className="flex items-center gap-2">
              {appointmentsError && (
                <Button variant="outline" size="sm" onClick={() => refetchAppointments()}>
                  <RefreshCw className="h-4 w-4 mr-1" />
                  Recarregar
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => openScheduleDialog()}>
                <Plus className="h-4 w-4 mr-2" />
                Novo
              </Button>
            </div>
          </div>

          {isLoadingAppointments ? (
            <p className="text-sm text-muted-foreground">Carregando compromissos...</p>
          ) : appointmentsError ? (
            <p className="text-sm text-destructive">Não foi possível carregar os compromissos.</p>
          ) : (
            <>
              {/* Próximos */}
              {(() => {
                const now = new Date();

                // filtro extra de segurança p/ nunca exibir cancelados aqui
                const visibleUpcoming = upcomingAppointments.filter(
                  (a) => a.status !== "canceled" && new Date(a.startTime) >= now
                );

                if (visibleUpcoming.length === 0) return null;

                return (
                  <div className="space-y-2">
                    <h4 className="text-sm font-semibold text-foreground">Próximos</h4>
                    <div className="space-y-2">
                      {visibleUpcoming.map((appointment) => {
                        const start = new Date(appointment.startTime);
                        return (
                          <div
                            key={appointment.id}
                            className="border border-border rounded-md p-3 space-y-2 bg-background/80"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Badge className={appointmentTypeClasses[appointment.type]}>
                                  {appointmentTypeLabels[appointment.type]}
                                </Badge>
                                <Badge className={appointmentStatusClasses[appointment.status]}>
                                  {appointmentStatusLabels[appointment.status]}
                                </Badge>
                                {appointment.outcome && (
                                  <Badge className={appointmentOutcomeClasses[appointment.outcome]}>
                                    {appointmentOutcomeLabels[appointment.outcome]}
                                  </Badge>
                                )}
                              </div>
                              <span className="text-xs text-muted-foreground">
                                {formatDate(start)}
                              </span>
                            </div>
                            <div className="space-y-1">
                              <p className="text-sm font-medium text-foreground">
                                {appointment.title}
                              </p>
                              {appointment.description && (
                                <p className="text-xs text-muted-foreground">
                                  {appointment.description}
                                </p>
                              )}
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleRescheduleOutcome(appointment)}
                              >
                                Reagendar
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleSetOutcome(appointment, "completed")}
                              >
                                Concluir
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleSetOutcome(appointment, "no_show")}
                              >
                                No-show
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-destructive hover:text-destructive"
                                onClick={() => handleCancelAppointmentAction(appointment)}
                              >
                                Cancelar
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}

              {/* Histórico */}
              {pastAppointments.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-foreground">Histórico</h4>
                  <div className="space-y-2">
                    {pastAppointments.map((appointment) => {
                      const start = new Date(appointment.startTime);

                      // normaliza status para as chaves aceitas nos mapas de UI
                      type UiStatus = keyof typeof appointmentStatusClasses; // "pending" | "completed" | "canceled"
                      const statusStr = String(appointment.status);
                      const normalized: UiStatus =
                        (statusStr === "scheduled" ? "pending" : statusStr) as UiStatus;

                      return (
                        <div
                          key={appointment.id}
                          className="border border-border rounded-md p-3 space-y-1 bg-muted/40"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <Badge className={appointmentTypeClasses[appointment.type]}>
                                {appointmentTypeLabels[appointment.type]}
                              </Badge>
                              <Badge className={appointmentStatusClasses[normalized]}>
                                {appointmentStatusLabels[normalized]}
                              </Badge>
                              {appointment.outcome && (
                                <Badge className={appointmentOutcomeClasses[appointment.outcome]}>
                                  {appointmentOutcomeLabels[appointment.outcome]}
                                </Badge>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {formatDate(start)}
                            </span>
                          </div>
                          <p className="text-sm text-foreground font-medium">
                            {appointment.title}
                          </p>
                          {appointment.description && (
                            <p className="text-xs text-muted-foreground">
                              {appointment.description}
                            </p>
                          )}
                          {!appointment.outcome && (
                            <div className="flex flex-wrap items-center gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleSetOutcome(appointment, "completed")}
                              >
                                Concluir
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleSetOutcome(appointment, "no_show")}
                              >
                                No-show
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleRescheduleOutcome(appointment)}
                              >
                                Reagendar
                              </Button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}



              {upcomingAppointments.length === 0 && pastAppointments.length === 0 && (
                <p className="text-sm text-muted-foreground">Nenhum compromisso registrado.</p>
              )}
            </>
          )}
        </div>
      </div>

      {/* ---- Histórico de Follow-up ---- */}
      {currentLead.followup_contract && (
        <div className="space-y-3 pt-2">
          <Separator />
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-foreground flex items-center gap-2 text-sm">
              <Zap className="w-4 h-4 text-amber-400" />
              Histórico de Follow-up
            </h3>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs gap-1 text-muted-foreground hover:text-foreground"
              onClick={() => navigate(`/follow-ups?leadId=${currentLead.id}`)}
            >
              Ver na Central
              <ExternalLink className="w-3 h-3" />
            </Button>
          </div>

          {/* Resumo do contrato */}
          <FollowUpContractSummary contract={currentLead.followup_contract as FollowUpContract} />

          {/* Linha do tempo de mensagens */}
          {messagesData?.messages && messagesData.messages.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Mensagens recentes
              </p>
              <div className="space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar pr-1">
                {messagesData.messages.slice(-5).reverse().map((msg) => (
                  <div
                    key={msg.id}
                    className="text-xs rounded-md bg-muted/40 border border-border px-3 py-2 space-y-0.5"
                  >
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <span className="capitalize font-medium">{msg.channel}</span>
                      <span>·</span>
                      <span>
                        {new Intl.DateTimeFormat("pt-PT", {
                          day: "2-digit",
                          month: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        }).format(new Date(msg.createdAt))}
                      </span>
                    </div>
                    <p className="text-foreground/80 line-clamp-2">{msg.body}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {isScheduleDialogOpen && (
        <ScheduleAppointmentDialog
        open={isScheduleDialogOpen}
        onOpenChange={setIsScheduleDialogOpen}
        fixedLeadId={lead.id}
        appointmentToEdit={appointmentToEdit}
        initialDate={appointmentToEdit ? new Date(appointmentToEdit.startTime) : undefined}
        onSuccess={handleAppointmentSuccess}
      />
      )}

      <AlertDialog open={showDisableModal} onOpenChange={setShowDisableModal}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Desativar bot para este lead?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3">
                <p>
                  Ao desativar, o agente deixará de responder a este lead. Ao reativar, o agente
                  provavelmente <strong>não terá contexto suficiente</strong> para retomar a venda
                  de onde parou.
                </p>
                <p className="text-xs text-muted-foreground">
                  Recomendamos reativar apenas em situações de follow-up, fornecendo contexto claro
                  sobre onde a conversa parou.
                </p>
                <label className="flex items-center gap-2 cursor-pointer pt-1">
                  <input
                    type="checkbox"
                    checked={disableAware}
                    onChange={(e) => setDisableAware(e.target.checked)}
                  />
                  <span className="text-sm">
                    Estou ciente que o agente pode perder o contexto ao reativar
                  </span>
                </label>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setShowDisableModal(false);
                setDisableAware(false);
              }}
            >
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={!disableAware}
              onClick={() => void handleDisableBot()}
            >
              Desativar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={showReactivateWarningModal} onOpenChange={setShowReactivateWarningModal}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reativar bot para este lead?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3">
                <p>
                  Você está reativando o bot após uma <strong>pausa manual</strong>. O agente
                  provavelmente não tem contexto suficiente para retomar a venda de onde parou.
                </p>
                <p className="text-xs text-muted-foreground">
                  Recomendamos reativar apenas para follow-up. Antes de reativar, forneça contexto
                  no campo de instruções do follow-up sobre onde a venda parou e o que o agente
                  deve fazer.
                </p>
                <label className="flex items-center gap-2 cursor-pointer pt-1">
                  <input
                    type="checkbox"
                    checked={reactivateAware}
                    onChange={(e) => setReactivateAware(e.target.checked)}
                  />
                  <span className="text-sm">
                    Estou ciente que o agente pode não ter contexto da conversa anterior
                  </span>
                </label>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setShowReactivateWarningModal(false);
                setReactivateAware(false);
              }}
            >
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={!reactivateAware}
              onClick={() => void handleReactivateBot()}
            >
              Reativar mesmo assim
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </DialogContent>
  );
}
