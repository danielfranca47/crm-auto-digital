import { useCallback, useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  DragEndEvent,
  DragOverEvent,
  DragStartEvent,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  closestCorners,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { Lead, NewLeadForm, Appointment } from "../types/crm";
import { KanbanColumn } from "./KanbanColumn";
import { CrmHeader } from "./CrmHeader";
import { NewLeadModal } from "./NewLeadModal";
import { LeadCardDialog } from "./LeadCardDialog";
import { AddLeadResult, useLeads } from "@/contexts/LeadsContext";
import { Button } from "./ui/button";
import { Archive, AlertCircle, RefreshCw } from "lucide-react";
import { ScheduleAppointmentDialog } from "./ScheduleAppointmentDialog";
import { useAppointments, useCancelAppointment } from "@/hooks/useAppointments";
import { useToast } from "@/hooks/use-toast";
import { Alert, AlertDescription, AlertTitle } from "./ui/alert";
import { FollowUpTransitionModal } from "./FollowUpTransitionModal";
import { useNotifications } from "@/hooks/useNotifications";

interface KanbanBoardProps {
  onDashboard: () => void;
}

export function KanbanBoard({ onDashboard }: KanbanBoardProps) {
  const {
    columns,
    archivedColumns,
    updateLead,
    moveLead,
    archiveLead,
    addLead,
    deleteLead,
    leadsError,
    reloadAllLeads,
    setLeadNextAction,
  } = useLeads();
  const { data: appointments = [] } = useAppointments();
  const cancelAppointment = useCancelAppointment();
  const { toast } = useToast();

  const sensors = useSensors(
    useSensor(MouseSensor, {
      activationConstraint: {
        distance: 6,
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 180,
        tolerance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const [isNewLeadModalOpen, setIsNewLeadModalOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [isLeadDialogOpen, setIsLeadDialogOpen] = useState(false);
  const [isAppointmentDialogOpen, setIsAppointmentDialogOpen] = useState(false);
  const [appointmentDialogLeadId, setAppointmentDialogLeadId] = useState<string | null>(null);
  const [appointmentToEdit, setAppointmentToEdit] = useState<Appointment | null>(null);
  const [followupModalOpen, setFollowupModalOpen] = useState(false);
  const [followupLead, setFollowupLead] = useState<Lead | null>(null);
  const [profileAgentType, setProfileAgentType] = useState<"agent_1" | "agent_2" | "agent_3" | null>(null);
  const { notifiedLeadIds } = useNotifications();

  useEffect(() => {
    let mounted = true;
    const inferAgentTypeFromProfile = async () => {
      try {
        const profile = await api.core.getAiProfileMe();
        const templateKey = String(profile?.template_key || "").trim().toLowerCase();
        const inferred: "agent_1" | "agent_2" | "agent_3" =
          templateKey === "hybrid_scheduler"
            ? "agent_3"
            : templateKey.startsWith("closer")
            ? "agent_2"
            : "agent_1";
        if (mounted) {
          setProfileAgentType(inferred);
        }
      } catch {
        if (mounted) {
          setProfileAgentType(null);
        }
      }
    };
    inferAgentTypeFromProfile();
    return () => {
      mounted = false;
    };
  }, []);

  const allColumns = useMemo(() => [...columns, ...archivedColumns], [columns, archivedColumns]);

  const filterLeads = useCallback(
    (leads: Lead[]) => {
      if (!searchTerm.trim()) return leads;
      const term = searchTerm.toLowerCase();
      return leads.filter((lead) =>
        lead.contactName.toLowerCase().includes(term) ||
        lead.companyName.toLowerCase().includes(term) ||
        lead.phone.toLowerCase().includes(term) ||
        lead.origin.toLowerCase().includes(term) ||
        (!!lead.observations && lead.observations.toLowerCase().includes(term))
      );
    },
    [searchTerm]
  );

  const filteredColumns = useMemo(
    () => columns.map((col) => ({ ...col, leads: filterLeads(col.leads) })),
    [columns, filterLeads]
  );

  const filteredArchivedColumns = useMemo(
    () => archivedColumns.map((col) => ({ ...col, leads: filterLeads(col.leads) })),
    [archivedColumns, filterLeads]
  );

  const findColumn = useCallback(
    (leadId: string) => allColumns.find((col) => col.leads.some((lead) => lead.id === leadId)),
    [allColumns]
  );

  const findLead = useCallback(
    (leadId: string) => {
      for (const column of allColumns) {
        const lead = column.leads.find((l) => l.id === leadId);
        if (lead) return lead;
      }
      return null;
    },
    [allColumns]
  );

  const activeLead = useMemo(() => {
    if (!activeId) return null;
    return findLead(activeId);
  }, [activeId, findLead]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    const activeColumn = findColumn(activeId);
    const overColumn = allColumns.find((col) => col.id === overId) || findColumn(overId);

    if (!activeColumn || !overColumn || activeColumn === overColumn) return;
  };

  const getEffectiveAgentType = useCallback(
    (lead: Lead): "agent_1" | "agent_2" | "agent_3" | null => {
      const raw = String(lead.agent_type || "").trim().toLowerCase();
      if (raw === "agent_1" || raw === "agent_2" || raw === "agent_3") {
        return raw;
      }
      return profileAgentType;
    },
    [profileAgentType]
  );

  const resolveAgentTypeForLead = useCallback(
    async (lead: Lead): Promise<"agent_1" | "agent_2" | "agent_3" | null> => {
      const current = getEffectiveAgentType(lead);
      if (current) return current;

      try {
        const profile = await api.core.getAiProfileMe();
        const templateKey = String(profile?.template_key || "").trim().toLowerCase();
        const inferred: "agent_1" | "agent_2" | "agent_3" =
          templateKey === "hybrid_scheduler"
            ? "agent_3"
            : templateKey.startsWith("closer")
            ? "agent_2"
            : "agent_1";
        setProfileAgentType(inferred);
        return inferred;
      } catch {
        return null;
      }
    },
    [getEffectiveAgentType]
  );

  const requiresFollowupTransition = useCallback((lead: Lead, targetCategory: string) => {
    if (lead.category !== "apresentation" || targetCategory !== "follow-up") return false;
    const effectiveAgentType = getEffectiveAgentType(lead);
    return effectiveAgentType === "agent_1" || effectiveAgentType === "agent_3";
  }, [getEffectiveAgentType]);

  const handleMoveWithRules = useCallback(async (lead: Lead, targetCategory: string) => {
    const isFollowupTransition = lead.category === "apresentation" && targetCategory === "follow-up";

    if (isFollowupTransition) {
      const effectiveAgentType = await resolveAgentTypeForLead(lead);

      if (effectiveAgentType === "agent_1" || effectiveAgentType === "agent_3") {
        setFollowupLead(
          lead.agent_type !== effectiveAgentType
            ? { ...lead, agent_type: effectiveAgentType }
            : lead
        );
        setFollowupModalOpen(true);
        return;
      }

      // agent_2 (closer): sem popup — carrinho abandonado é ativado automaticamente
      // quando o bot envia o link de pagamento. Prossegue com movimentação direta.
    }

    if (requiresFollowupTransition(lead, targetCategory)) {
      const effectiveAgentType = await resolveAgentTypeForLead(lead);
      setFollowupLead(
        effectiveAgentType && lead.agent_type !== effectiveAgentType
          ? { ...lead, agent_type: effectiveAgentType }
          : lead
      );
      setFollowupModalOpen(true);
      return;
    }

    moveLead(lead.id, targetCategory as any);
  }, [moveLead, requiresFollowupTransition, resolveAgentTypeForLead, toast]);

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveId(null);

    const { active, over } = event;
    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    const activeColumn = findColumn(activeId);
    const overColumn = allColumns.find((col) => col.id === overId) || findColumn(overId);

    if (!activeColumn || !overColumn) return;

    const lead = findLead(activeId);
    if (!lead) return;

    if (activeColumn.id !== overColumn.id) {
      handleMoveWithRules(lead, overColumn.id);
    } else {
      const activeIndex = activeColumn.leads.findIndex((item) => item.id === activeId);
      const overIndex = overColumn.leads.findIndex((item) => item.id === overId);

      if (activeIndex !== overIndex) {
        updateLead(activeId, {
          lastMovement: new Date(),
        });
      }
    }
  };

  const handleMoveLead = (leadId: string, newCategory: string) => {
    const lead = findLead(leadId);
    if (!lead) return;
    handleMoveWithRules(lead, newCategory);
  };

  const handleArchiveLead = (leadId: string, archiveCategory: string) => {
    archiveLead(leadId, archiveCategory as any);
  };

  const findAppointmentById = useCallback(
    (appointmentId?: string | null) => {
      if (!appointmentId) return null;
      const match = appointments.find((item) => item.id === appointmentId);
      return match ?? null;
    },
    [appointments]
  );

  const handleScheduleMeeting = (leadId: string) => {
    setAppointmentDialogLeadId(leadId);
    setAppointmentToEdit(null);
    setIsAppointmentDialogOpen(true);
  };

  const handleRescheduleMeeting = (lead: Lead) => {
    const nextAction = lead.nextScheduledAction;
    if (!nextAction?.id) {
      toast({ title: "Nenhum compromisso para reagendar", variant: "destructive" });
      return;
    }

    const appointment =
      findAppointmentById(nextAction.id) ||
      ({
        id: nextAction.id,
        leadId: lead.id,
        title: nextAction.description,
        description: nextAction.description,
        type: nextAction.type ?? "meeting",
        status: "pending",
        startTime: nextAction.date.toISOString(),
        endTime: undefined,
        leadName: lead.contactName,
        leadCompany: lead.companyName,
      } as Appointment);

    setAppointmentDialogLeadId(lead.id);
    setAppointmentToEdit(appointment);
    setIsAppointmentDialogOpen(true);
  };

  const handleCancelMeeting = async (lead: Lead) => {
    const appointmentId = lead.nextScheduledAction?.id;
    if (!appointmentId) {
      toast({ title: "Nenhum compromisso para cancelar", variant: "destructive" });
      return;
    }

    try {
      await cancelAppointment.mutateAsync(appointmentId);
      setLeadNextAction(lead.id, undefined);
      setSelectedLead((prev) => (prev?.id === lead.id ? { ...prev, nextScheduledAction: undefined } : prev));
      toast({ title: "Compromisso cancelado" });
    } catch (error: any) {
      toast({
        title: "Erro ao cancelar compromisso",
        description: error?.message ?? "Não foi possível cancelar o compromisso.",
        variant: "destructive",
      });
    }
  };

  const handleOpenCard = (leadId: string) => {
    const lead = findLead(leadId);
    if (lead) {
      setSelectedLead(lead);
      setIsLeadDialogOpen(true);
    }
  };

  const handleUpdateLead = (leadId: string, updates: Partial<Lead>) => {
    updateLead(leadId, updates);
    if (selectedLead?.id === leadId) {
      setSelectedLead({ ...selectedLead, ...updates });
    }
  };

  const handleNewLead = async (leadData: NewLeadForm) => {
    const result: AddLeadResult = await addLead(leadData);
    if (result.kind === "exists") {
      toast({
        title: "Lead já existe",
        description: "Abrimos o cadastro existente.",
      });

      const leadFromState = findLead(result.existingLeadId);
      const leadToOpen = leadFromState || result.existingLead || null;
      if (leadToOpen) {
        setSelectedLead(leadToOpen);
        setIsLeadDialogOpen(true);
      }
    }
  };

  const handleDeleteLead = async (leadId: string) => {
    try {
      await deleteLead(leadId);
      if (selectedLead?.id === leadId) {
        setIsLeadDialogOpen(false);
        setSelectedLead(null);
      }
      toast({ title: "Lead excluído" });
    } catch (error: any) {
      toast({
        title: "Erro ao excluir lead",
        description: error?.message ?? "Não foi possível excluir o lead.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="min-h-screen bg-background relative">
      <CrmHeader
        onNewLead={() => setIsNewLeadModalOpen(true)}
        onDashboard={onDashboard}
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
        allColumns={allColumns}
        onLeadSelect={handleOpenCard}
      />

      <main className="p-6">
        {leadsError && (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Não foi possível carregar os leads</AlertTitle>
            <AlertDescription className="flex items-center justify-between gap-4">
              <span>{leadsError}</span>
              <Button
                size="sm"
                variant="outline"
                onClick={reloadAllLeads}
                className="shrink-0"
              >
                <RefreshCw className="mr-2 h-4 w-4" /> Tentar novamente
              </Button>
            </AlertDescription>
          </Alert>
        )}

        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
        >
          <DragOverlay>
            {activeLead ? (
              <div className="lead-card p-4 w-72 rotate-1 shadow-2xl cursor-grabbing">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-semibold text-foreground text-sm">
                    {activeLead.companyName} - {activeLead.contactName}
                  </h4>
                </div>
                <div className="text-xs text-muted-foreground truncate">{activeLead.phone}</div>
                <div className="text-xs text-muted-foreground truncate mt-1">{activeLead.origin}</div>
              </div>
            ) : null}
          </DragOverlay>

          <div className="flex justify-between items-center mb-4">
            <h1 className="text-xl font-semibold text-foreground">Quadro Kanban</h1>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowArchived((prev) => !prev)}>
                <Archive className="w-4 h-4 mr-2" />
                {showArchived ? "Ocultar Arquivados" : "Ver Arquivados"}
              </Button>
              <Button size="sm" onClick={() => setIsNewLeadModalOpen(true)}>
                Novo Lead
              </Button>
            </div>
          </div>

          <div className="flex gap-4 overflow-x-auto pb-6">
            {filteredColumns.map((column) => (
              <KanbanColumn
                key={column.id}
                column={column}
                columns={columns}
                archivedColumns={archivedColumns}
                onMoveLead={handleMoveLead}
                onArchiveLead={handleArchiveLead}
                onScheduleMeeting={handleScheduleMeeting}
                onRescheduleMeeting={handleRescheduleMeeting}
                onCancelMeeting={handleCancelMeeting}
                onOpenCard={handleOpenCard}
                onDeleteLead={handleDeleteLead}
                notifiedLeadIds={notifiedLeadIds}
              />
            ))}

            {showArchived &&
              filteredArchivedColumns.map((column) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  columns={columns}
                  archivedColumns={archivedColumns}
                  onMoveLead={handleMoveLead}
                  onArchiveLead={handleArchiveLead}
                  onScheduleMeeting={handleScheduleMeeting}
                  onRescheduleMeeting={handleRescheduleMeeting}
                  onCancelMeeting={handleCancelMeeting}
                  onOpenCard={handleOpenCard}
                  onDeleteLead={handleDeleteLead}
                  notifiedLeadIds={notifiedLeadIds}
                />
              ))}
          </div>
        </DndContext>
      </main>

      <NewLeadModal
        isOpen={isNewLeadModalOpen}
        onClose={() => setIsNewLeadModalOpen(false)}
        onSave={handleNewLead}
      />

      <LeadCardDialog
        lead={selectedLead}
        isOpen={isLeadDialogOpen}
        onClose={() => setIsLeadDialogOpen(false)}
        onUpdateLead={handleUpdateLead}
        onDeleteLead={handleDeleteLead}
      />

      <ScheduleAppointmentDialog
        open={isAppointmentDialogOpen}
        onOpenChange={(open) => {
          setIsAppointmentDialogOpen(open);
          if (!open) {
            setAppointmentDialogLeadId(null);
            setAppointmentToEdit(null);
          }
        }}
        initialLeadId={appointmentDialogLeadId}
        appointmentToEdit={appointmentToEdit}
        initialDate={appointmentToEdit ? new Date(appointmentToEdit.startTime) : undefined}
        onSuccess={(appointment) => {
          setAppointmentDialogLeadId(null);
          setAppointmentToEdit(null);
          if (appointment.leadId) {
            setLeadNextAction(appointment.leadId, {
              id: appointment.id,
              date: new Date(appointment.startTime),
              description: appointment.title,
              type: appointment.type,
            });
            setSelectedLead((prev) =>
              prev?.id === appointment.leadId
                ? {
                    ...prev,
                    nextScheduledAction: {
                      id: appointment.id,
                      date: new Date(appointment.startTime),
                      description: appointment.title,
                      type: appointment.type,
                    },
                  }
                : prev
            );
          }
        }}
      />

      <FollowUpTransitionModal
        open={followupModalOpen}
        onOpenChange={setFollowupModalOpen}
        lead={followupLead}
        onSuccess={async () => {
          if (followupLead) {
            moveLead(followupLead.id, "follow-up" as any);
          }
          setFollowupLead(null);
        }}
      />
    </div>
  );
}
