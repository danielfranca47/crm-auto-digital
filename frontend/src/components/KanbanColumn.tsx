import { KanbanColumn as KanbanColumnType, Lead } from "../types/crm";
import { LeadCard } from "./LeadCard";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";

interface KanbanColumnProps {
  column: KanbanColumnType;
  columns: KanbanColumnType[];
  archivedColumns: KanbanColumnType[];
  onMoveLead: (leadId: string, newCategory: string) => void;
  onArchiveLead: (leadId: string, archiveCategory: string) => void;
  onScheduleMeeting: (leadId: string) => void;
  onRescheduleMeeting: (lead: Lead) => void;
  onCancelMeeting: (lead: Lead) => void;
  onOpenCard: (leadId: string) => void;
}

export function KanbanColumn({
  column,
  columns,
  archivedColumns,
  onMoveLead,
  onArchiveLead,
  onScheduleMeeting,
  onRescheduleMeeting,
  onCancelMeeting,
  onOpenCard
}: KanbanColumnProps) {
  const { setNodeRef } = useDroppable({
    id: column.id,
  });

  return (
    <div className="kanban-column min-h-[600px] w-72 flex-shrink-0">
      <div className="kanban-column-header p-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-foreground text-sm">{column.title}</h3>
          <span 
            className="text-xs px-2 py-1 rounded-full text-white font-medium"
            style={{ backgroundColor: column.color }}
          >
            {column.leads.length}
          </span>
        </div>
      </div>

      <div 
        ref={setNodeRef}
        className="p-4 pt-0 custom-scrollbar"
        style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}
      >
        <SortableContext items={column.leads.map(lead => lead.id)} strategy={verticalListSortingStrategy}>
          {column.leads.map((lead) => (
            <LeadCard
              key={lead.id}
              lead={lead}
              columns={columns}
              archivedColumns={archivedColumns}
              onMoveLead={onMoveLead}
              onArchiveLead={onArchiveLead}
              onScheduleMeeting={onScheduleMeeting}
              onRescheduleMeeting={onRescheduleMeeting}
              onCancelMeeting={onCancelMeeting}
              onOpenCard={onOpenCard}
            />
          ))}
        </SortableContext>
        
        {column.leads.length === 0 && (
          <div className="text-center text-muted-foreground py-8">
            <p className="text-sm">Nenhum lead</p>
          </div>
        )}
      </div>
    </div>
  );
}