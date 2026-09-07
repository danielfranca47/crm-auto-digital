import { KanbanColumn as KanbanColumnType, Lead } from "../types/crm";
import { LeadCard } from "./LeadCard";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { SalesFlowPhaseId } from "@/types/agente";
import { ChevronDown, ChevronRight } from "lucide-react";

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
  onDeleteLead: (leadId: string) => Promise<void>;
  notifiedLeadIds?: Set<string>;
  phaseSequence?: SalesFlowPhaseId[];
  fullWidth?: boolean;
  collapsible?: boolean;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
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
  onOpenCard,
  onDeleteLead,
  notifiedLeadIds,
  phaseSequence,
  fullWidth,
  collapsible,
  isCollapsed,
  onToggleCollapse,
}: KanbanColumnProps) {
  const { setNodeRef } = useDroppable({
    id: column.id,
  });
  const collapsed = collapsible && isCollapsed;

  return (
    <div ref={setNodeRef} className={`kanban-column ${collapsed ? "" : "min-h-[600px]"} ${fullWidth ? "w-full" : "w-72 flex-shrink-0"}`}>
      <div className="kanban-column-header p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1 min-w-0">
            {collapsible && (
              <button
                type="button"
                onClick={onToggleCollapse}
                aria-expanded={!collapsed}
                aria-label={collapsed ? "Expandir coluna" : "Colapsar coluna"}
                className="text-muted-foreground hover:text-foreground shrink-0"
              >
                {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
            )}
            <h3 className="font-semibold text-foreground text-sm truncate">{column.title}</h3>
          </div>
          <span
            className="text-xs px-2 py-1 rounded-full text-white font-medium shrink-0"
            style={{ backgroundColor: column.color }}
          >
            {column.leads.length}
          </span>
        </div>
      </div>

      {!collapsed && (
        <div
          className="p-4 pt-0 custom-scrollbar overflow-y-auto overflow-x-hidden min-w-0"
          style={{ maxHeight: 'calc(100vh - 200px)' }}
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
                onDeleteLead={onDeleteLead}
                hasReplyNotification={notifiedLeadIds?.has(lead.id) ?? false}
                phaseSequence={phaseSequence}
              />
            ))}
          </SortableContext>

          {column.leads.length === 0 && (
            <div className="text-center text-muted-foreground py-8">
              <p className="text-sm">Nenhum lead</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
