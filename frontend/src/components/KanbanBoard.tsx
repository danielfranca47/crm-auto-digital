import { useState, useCallback } from "react";
import { 
  DndContext, 
  DragEndEvent, 
  DragOverEvent, 
  closestCorners, 
  DragStartEvent,
  MouseSensor,
  TouchSensor,
  KeyboardSensor,
  useSensor,
  useSensors
} from "@dnd-kit/core";
import { arrayMove, sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { KanbanColumn as KanbanColumnType, Lead, NewLeadForm } from "../types/crm";
import { KanbanColumn } from "./KanbanColumn";
import { CrmHeader } from "./CrmHeader";
import { NewLeadModal } from "./NewLeadModal";
import { LeadCardDialog } from "./LeadCardDialog";
import { useLeads } from "@/contexts/LeadsContext";
import { Button } from "./ui/button";
import { Archive } from "lucide-react";

interface KanbanBoardProps {
  onDashboard: () => void;
}

export function KanbanBoard({ onDashboard }: KanbanBoardProps) {

  const { columns, archivedColumns, updateLead, moveLead, archiveLead, addLead } = useLeads();
  
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

  const allColumns = [...columns, ...archivedColumns];

  // Filter leads based on search term
  const filterLeads = (leads: Lead[]) => {
    if (!searchTerm.trim()) return leads;
    
    const term = searchTerm.toLowerCase();
    return leads.filter(lead => 
      lead.contactName.toLowerCase().includes(term) ||
      lead.companyName.toLowerCase().includes(term) ||
      lead.phone.toLowerCase().includes(term) ||
      lead.origin.toLowerCase().includes(term) ||
      (lead.observations && lead.observations.toLowerCase().includes(term))
    );
  };

  const filteredColumns = columns.map(col => ({
    ...col,
    leads: filterLeads(col.leads)
  }));

  const filteredArchivedColumns = archivedColumns.map(col => ({
    ...col,
    leads: filterLeads(col.leads)
  }));

  const findColumn = useCallback((leadId: string) => {
    return allColumns.find(col => col.leads.some(lead => lead.id === leadId));
  }, [allColumns]);

  const findLead = useCallback((leadId: string) => {
    for (const column of allColumns) {
      const lead = column.leads.find(l => l.id === leadId);
      if (lead) return lead;
    }
    return null;
  }, [allColumns]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    
    if (!over) return;
    
    const activeId = active.id as string;
    const overId = over.id as string;
    
    const activeColumn = findColumn(activeId);
    const overColumn = allColumns.find(col => col.id === overId) || findColumn(overId);
    
    if (!activeColumn || !overColumn || activeColumn === overColumn) return;

    // Use context function to move lead
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

    // Se o lead foi movido para outra coluna (categoria), atualiza a categoria
    if (activeColumn.id !== overColumn.id) {
      updateLead(activeId, {
        category: overColumn.id, // nova categoria com base na coluna de destino
        lastMovement: new Date()
      });
    } else {
      const activeIndex = activeColumn.leads.findIndex(lead => lead.id === activeId);
      const overIndex = overColumn.leads.findIndex(lead => lead.id === overId);

      if (activeIndex !== overIndex) {
        updateLead(activeId, {
          lastMovement: new Date()
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

  const handleScheduleMeeting = (leadId: string) => {
    // Implementar funcionalidade de agendamento
    console.log('Agendar reunião para lead:', leadId);
  };

  const handleOpenCard = (leadId: string) => {
    const allLeads = [...columns, ...archivedColumns].flatMap(col => col.leads);
    const lead = allLeads.find(l => l.id === leadId);
    if (lead) {
      setSelectedLead(lead);
      setIsLeadDialogOpen(true);
    }
  };

  const handleUpdateLead = (leadId: string, updates: Partial<Lead>) => {
    updateLead(leadId, updates);
    
    // Update selected lead if it's the one being updated
    if (selectedLead?.id === leadId) {
      setSelectedLead({ ...selectedLead, ...updates });
    }
  };

  const handleNewLead = (leadData: NewLeadForm) => {
    addLead(leadData);
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
          <div className="flex gap-4 overflow-x-auto custom-scrollbar pb-4">
            {showArchived 
              ? filteredArchivedColumns.map((column) => (
                  <KanbanColumn 
                    key={column.id} 
                    column={column}
                    columns={columns}
                    archivedColumns={archivedColumns}
                    onMoveLead={handleMoveLead}
                    onArchiveLead={handleArchiveLead}
                    onScheduleMeeting={handleScheduleMeeting}
                    onOpenCard={handleOpenCard}
                  />
                ))
              : filteredColumns.map((column) => (
                  <KanbanColumn 
                    key={column.id} 
                    column={column}
                    columns={columns}
                    archivedColumns={archivedColumns}
                    onMoveLead={handleMoveLead}
                    onArchiveLead={handleArchiveLead}
                    onScheduleMeeting={handleScheduleMeeting}
                    onOpenCard={handleOpenCard}
                  />
                ))
            }
          </div>
        </DndContext>
      </main>

      {/* Archive buttons in bottom right corner */}
      <div className="fixed bottom-6 right-6 space-y-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowArchived(!showArchived)}
          className="flex items-center gap-2 bg-background/80 backdrop-blur-sm border-border hover:bg-muted"
        >
          <Archive className="h-4 w-4" />
          {showArchived ? 'Voltar' : 'Arquivo'}
        </Button>
        
        {showArchived && (
          <div className="space-y-1">
            {archivedColumns.map((column) => (
              <Button
                key={column.id}
                variant="ghost"
                size="sm"
                className="w-full justify-start text-xs bg-background/80 backdrop-blur-sm"
                style={{ color: column.color }}
              >
                {column.title} ({column.leads.length})
              </Button>
            ))}
          </div>
        )}
      </div>

      <NewLeadModal
        isOpen={isNewLeadModalOpen}
        onClose={() => setIsNewLeadModalOpen(false)}
        onSave={addLead}
      />

      <LeadCardDialog
        lead={selectedLead}
        isOpen={isLeadDialogOpen}
        onClose={() => setIsLeadDialogOpen(false)}
        onUpdateLead={handleUpdateLead}
      />
    </div>
  );
}