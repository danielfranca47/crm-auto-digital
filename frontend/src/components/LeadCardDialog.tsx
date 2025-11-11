import { Lead, LeadStatus, Appointment } from "../types/crm";
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
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Separator } from "./ui/separator";
import { useState, useEffect, useMemo } from "react";
import { ScheduleAppointmentDialog } from "./ScheduleAppointmentDialog";
import { useLeadAppointments, useCancelAppointment } from "@/hooks/useAppointments";
import { useToast } from "@/hooks/use-toast";
import { useLeads } from "@/contexts/LeadsContext";

interface LeadCardDialogProps {
  lead: Lead | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdateLead?: (leadId: string, updates: Partial<Lead>) => void;
}

//TODO Estava dando erros aqui, com nomes de colunas antigas. Ajustei conforme as atuais.
/** Cores/labels de status (alinhado com mockData.ts) */
//Ela era basicamente a “tabela de tradução” dos status do lead – o dicionário que dizia: qual nome amigável mostrar na telaqual cor usar em cada statusE isso era usado dentro do componente LeadCardDialog para montar aquele selo colorido (badge/pílula) que aparece no card do lead.
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
  scheduled: "Agendado",
  completed: "Concluído",
  canceled: "Cancelado",
} as const;

const appointmentStatusClasses = {
  scheduled: "bg-primary/10 text-primary border border-primary/20",
  completed: "bg-success/10 text-success border border-success/20",
  canceled: "bg-destructive/10 text-destructive border border-destructive/20",
} as const;

/** Wrapper sem hooks — evita o erro de Hooks. */
export function LeadCardDialog({ lead, isOpen, onClose, onUpdateLead }: LeadCardDialogProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      {isOpen && lead ? (
        <LeadCardDialogBody lead={lead} isOpen={isOpen} onClose={onClose} onUpdateLead={onUpdateLead} />
      ) : null}
    </Dialog>
  );
}

/** Body com os hooks — só é montado quando isOpen && lead. */
function LeadCardDialogBody({
  lead,
  onUpdateLead,
}: LeadCardDialogProps & { lead: Lead }) {
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

  const asDate = (iso: string) => new Date(iso);
  const isActiveStatus = (s?: string | null) =>
    ["scheduled", "pending"].includes(String(s));

  // Itens futuros **não cancelados**
  const upcomingAppointments = useMemo(() => {
    const nowTs = Date.now();

    return appointments
      .filter((a) => {
        if (a.status === "canceled") return false;
        if (!isActiveStatus(a.status)) return false; // só "scheduled" | "pending"
        const ts = new Date(a.startTime).getTime();
        return Number.isFinite(ts) && ts >= nowTs;
      })
      .sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime());
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

  const handleCancel = () => {
    setEditedLead({ ...lead });
    setIsEditing(false);
  };

  const openScheduleDialog = (appointment?: Appointment | null) => {
    setAppointmentToEdit(appointment ?? null);
    setIsScheduleDialogOpen(true);
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
  };

  const currentLead = isEditing ? editedLead! : lead;
  const nextScheduledAppointment = useMemo(() => {
    const appointmentId = currentLead.nextScheduledAction?.id;
    if (!appointmentId) return null;

    const appt = appointments.find(a => a.id === appointmentId) ?? null;
    // se o compromisso foi cancelado, não consideramos como “próxima ação”
    return appt && appt.status !== "canceled" ? appt : null;
  }, [appointments, currentLead.nextScheduledAction?.id]);


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
              <span className="text-xs text-muted-foreground">ID: {currentLead.id}</span>
            </div>
          </div>
          <div className="flex gap-2">
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
                      onClick={() => openScheduleDialog(nextScheduledAppointment)}
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
                                onClick={() => openScheduleDialog(appointment)}
                              >
                                Reagendar
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
                      type UiStatus = keyof typeof appointmentStatusClasses; // "scheduled" | "completed" | "canceled"
                      const statusStr = String(appointment.status);
                      const normalized: UiStatus =
                        (statusStr === "pending" ? "scheduled" : statusStr) as UiStatus;

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
    </DialogContent>
  );
}
