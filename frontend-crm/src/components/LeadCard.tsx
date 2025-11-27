import { Lead, KanbanColumn } from "../types/crm";
import { MessageCircle, Calendar, Phone } from "lucide-react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { LeadActionsMenu } from "./LeadActionsMenu";

interface LeadCardProps {
  lead: Lead;
  columns: KanbanColumn[];
  archivedColumns: KanbanColumn[];
  onMoveLead: (leadId: string, newCategory: string) => void;
  onArchiveLead: (leadId: string, archiveCategory: string) => void;
  onScheduleMeeting: (leadId: string) => void;
  onRescheduleMeeting: (lead: Lead) => void;
  onCancelMeeting: (lead: Lead) => void;
  onOpenCard: (leadId: string) => void;
}

export function LeadCard({
  lead,
  columns,
  archivedColumns,
  onMoveLead,
  onArchiveLead,
  onScheduleMeeting,
  onRescheduleMeeting,
  onCancelMeeting,
  onOpenCard
}: LeadCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: lead.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.7 : 1,
  };

  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    }).format(date);
  };

  const handleWhatsAppClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    const phoneNumber = lead.phone.replace(/\D/g, '');
    const message = `Olá ${lead.contactName}, tudo bem? Entrando em contato pelo CRM.`;
    window.open(`https://wa.me/${phoneNumber}?text=${encodeURIComponent(message)}`, '_blank');
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={() => !isDragging && onOpenCard(lead.id)}
      className="lead-card p-4 mb-3 cursor-grab active:cursor-grabbing"
    >
      <div className="flex justify-between items-start mb-3">
        <h4 className="font-semibold text-foreground text-sm">{lead.companyName} - {lead.contactName}</h4>
        <div className="flex items-center gap-1">
          <button
            onClick={handleWhatsAppClick}
            onPointerDown={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
            onTouchStart={(e) => e.stopPropagation()}
            className="text-success hover:text-success/80 transition-colors p-1 hover:bg-success/10 rounded"
            title="Enviar WhatsApp"
          >
            <MessageCircle className="w-4 h-4" />
          </button>
          <LeadActionsMenu
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
        </div>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex items-center text-muted-foreground">
          <Phone className="w-3 h-3 mr-2" />
          <span className="font-mono text-xs">{lead.phone}</span>
        </div>

        <div className="text-muted-foreground">
          <span className="text-xs font-medium">Origem:</span> {lead.origin}
        </div>

        {lead.observations && (
          <div className="text-muted-foreground">
            <span className="text-xs font-medium">Obs:</span> 
            <p className="text-xs mt-1 line-clamp-2">{lead.observations}</p>
          </div>
        )}

        <div className="flex items-center text-muted-foreground pt-2 border-t border-border">
          <Calendar className="w-3 h-3 mr-2" />
          <span className="text-xs">{formatDate(lead.lastMovement)}</span>
        </div>
      </div>
    </div>
  );
}