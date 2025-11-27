import { useCallback, useMemo, useState } from "react";
import {
  DndContext,
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
import { useLeads } from "@/contexts/LeadsContext";
import { Button } from "./ui/button";
import { Archive } from "lucide-react";
import { ScheduleAppointmentDialog } from "./ScheduleAppointmentDialog";
import { useAppointments, useCancelAppointment } from "@/hooks/useAppointments";
import { useToast } from "@/hooks/use-toast";

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
    moveLead(activeId, overColumn.id as any);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveId(null);

    const { active, over } = event;
    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    const activeColumn = findColumn(activeId);
    const overColumn = findColumn(overId);

    if (!activeColumn || !overColumn) return;

    const lead = findLead(activeId);
    if (!lead) return;

    if (activeColumn.id !== overColumn.id) {
      updateLead(activeId, {
        category: overColumn.id,
        lastMovement: new Date(),
      });
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
    moveLead(leadId, newCategory as any);
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
        status: "scheduled",
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
    await addLead(leadData); // addLead do LeadsContext deve fazer o optimistic update
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
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
        >
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
    </div>
  );
}
