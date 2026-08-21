import { Lead, KanbanColumn } from "../types/crm";
import { MessageCircle, Calendar, Phone, Zap } from "lucide-react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { LeadActionsMenu } from "./LeadActionsMenu";
import { useNavigate } from "react-router-dom";
import { leadDisplayName } from "@/utils/leadDisplayName";
import type { SalesFlowPhaseId } from "@/types/agente";
import { SALES_FLOW_PHASE_ID_LABELS, SALES_FLOW_PHASE_COLORS } from "@/types/agente";

// Mapeia lead.category (estado persistido no Kanban) para o phase_id do Fluxo de Venda —
// espelha _ROUTE_TO_PHASE_ID em backend-executors/app/services/decision_engine.py.
const CATEGORY_TO_PHASE_ID: Record<string, SalesFlowPhaseId> = {
  "qualification":    "p1",
  "apresentation":    "p2",
  "pre-agendamento":  "p3a",
  "pre_agendamento":  "p3a",
  "agendamento":      "p3b",
  "follow-up":        "p4",
  "follow_up":        "p4",
  "closing":          "p5",
};

// Funil resumido do Fluxo de Venda — mostra, de forma compacta, por onde o lead já
// passou (leads.phases_triggered) e em qual fase está agora (lead.category), sem
// detalhar os gatilhos individuais (isso fica para uma futura iteração no modal do lead).
function SalesFlowFunnel({ lead, phaseSequence }: { lead: Lead; phaseSequence: SalesFlowPhaseId[] }) {
  if (!phaseSequence.length) return null;

  const currentPhaseId = CATEGORY_TO_PHASE_ID[lead.category];
  const currentIndex = currentPhaseId ? phaseSequence.indexOf(currentPhaseId) : -1;
  const triggered = new Set(lead.phasesTriggered ?? []);

  return (
    <div className="flex items-center gap-1 pt-1" title="Progresso no Fluxo de Venda">
      {phaseSequence.map((phaseId, i) => {
        const color = SALES_FLOW_PHASE_COLORS[phaseId];
        const isCurrent = i === currentIndex;
        const isDone = triggered.has(phaseId) || (currentIndex >= 0 && i < currentIndex);
        return (
          <span
            key={phaseId}
            title={`${SALES_FLOW_PHASE_ID_LABELS[phaseId]}${isCurrent ? " (atual)" : ""}`}
            className="inline-block rounded-full"
            style={{
              width: isCurrent ? 8 : 6,
              height: isCurrent ? 8 : 6,
              background: isDone || isCurrent ? color : color + "33",
              boxShadow: isCurrent ? `0 0 0 2px ${color}55` : "none",
            }}
          />
        );
      })}
    </div>
  );
}

const FOLLOWUP_VARIANT_CONFIG: Record<string, { label: string; color: string }> = {
  cart_recovery:    { label: "Carrinho",  color: "#52C4A0" },
  hybrid_scheduler: { label: "Híbrido",   color: "#A78BFA" },
  sdr_scheduler:    { label: "SDR",       color: "#60A5FA" },
};

function FollowUpStatusBar({ contract }: { contract: Record<string, any> }) {
  const variant = contract?.followup_variant as string | undefined;
  const attempts = Number(contract?.attempts ?? 0);
  const maxAttempts = Number(contract?.max_attempts ?? 3);
  const cfg = (variant && FOLLOWUP_VARIANT_CONFIG[variant]) ?? { label: "Follow-up", color: "#94A3B8" };
  return (
    <div className="flex items-center gap-2 pt-1">
      <span
        className="text-[10px] font-medium px-1.5 py-0.5 rounded"
        style={{ background: cfg.color + "22", color: cfg.color, border: `1px solid ${cfg.color}55` }}
      >
        {cfg.label}
      </span>
      <div className="flex gap-1">
        {Array.from({ length: maxAttempts }).map((_, i) => (
          <span
            key={i}
            className="inline-block rounded-full"
            style={{
              width: 6,
              height: 6,
              background: i < attempts ? cfg.color : cfg.color + "33",
            }}
          />
        ))}
      </div>
    </div>
  );
}

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
  onDeleteLead: (leadId: string) => Promise<void>;
  hasReplyNotification?: boolean;
  phaseSequence?: SalesFlowPhaseId[];
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
  onOpenCard,
  onDeleteLead,
  hasReplyNotification = false,
  phaseSequence = [],
}: LeadCardProps) {
  const navigate = useNavigate();
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
    opacity: isDragging ? 0 : 1,
  };

  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    }).format(date);
  };

  const formatDateTime = (date: Date) => {
    return new Intl.DateTimeFormat('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
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
        <div className="flex items-center gap-1.5 min-w-0">
          <h4 className="font-semibold text-foreground text-sm truncate">{leadDisplayName(lead)}</h4>
          {hasReplyNotification && (
            <button
              title="Lead respondeu ao follow-up — ver na Central de Follow-ups"
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/follow-ups?leadId=${lead.id}`);
              }}
              onPointerDown={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
              onTouchStart={(e) => e.stopPropagation()}
              className="shrink-0 flex items-center justify-center w-5 h-5 rounded-full bg-amber-400/20 border border-amber-400/50 hover:bg-amber-400/40 transition-colors"
            >
              <Zap className="w-3 h-3 text-amber-400" />
            </button>
          )}
        </div>
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
            onDeleteLead={onDeleteLead}
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

        <SalesFlowFunnel lead={lead} phaseSequence={phaseSequence} />

        {lead.observations && (
          <div className="text-muted-foreground">
            <span className="text-xs font-medium">Obs:</span> 
            <p className="text-xs mt-1 line-clamp-2">{lead.observations}</p>
          </div>
        )}

        {lead.nextScheduledAction?.date && (
          <div className="flex items-center text-muted-foreground">
            <Calendar className="w-3 h-3 mr-2" />
            <span className="text-xs">
              Próximo compromisso: {formatDateTime(lead.nextScheduledAction.date)}
            </span>
          </div>
        )}

        {lead.category === "follow-up" && lead.followup_contract && (
          <FollowUpStatusBar contract={lead.followup_contract} />
        )}

        <div className="flex items-center text-muted-foreground pt-2 border-t border-border">
          <Calendar className="w-3 h-3 mr-2" />
          <span className="text-xs">{formatDate(lead.lastMovement)}</span>
        </div>
      </div>
    </div>
  );
}
