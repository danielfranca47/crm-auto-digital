import { Lead, KanbanColumn } from "../types/crm";
import { MoreVertical, Calendar, Eye, Move, Archive, Trash2 } from "lucide-react";
import { Button } from "./ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "./ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { useState } from "react";

interface LeadActionsMenuProps {
  lead: Lead;
  columns: KanbanColumn[];
  archivedColumns: KanbanColumn[];
  onMoveLead: (leadId: string, newCategory: string) => void;
  onArchiveLead: (leadId: string, archiveCategory: string) => void;
  onScheduleMeeting: (leadId: string) => void;
  onOpenCard: (leadId: string) => void;
}

export function LeadActionsMenu({ 
  lead, 
  columns, 
  archivedColumns, 
  onMoveLead, 
  onArchiveLead, 
  onScheduleMeeting, 
  onOpenCard 
}: LeadActionsMenuProps) {
  const [showMoveSelect, setShowMoveSelect] = useState(false);
  const [showArchiveSelect, setShowArchiveSelect] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  const handleMoveLead = (newCategory: string) => {
    onMoveLead(lead.id, newCategory);
    setShowMoveSelect(false);
    setIsOpen(false);
  };

  const handleArchiveLead = (archiveCategory: string) => {
    onArchiveLead(lead.id, archiveCategory);
    setShowArchiveSelect(false);
    setIsOpen(false);
  };

  const handleScheduleMeeting = () => {
    onScheduleMeeting(lead.id);
    setIsOpen(false);
  };

  const handleOpenCard = () => {
    onOpenCard(lead.id);
    setIsOpen(false);
  };

  const handleOpenChange = (open: boolean) => {
    setIsOpen(open);
    if (!open) {
      setShowMoveSelect(false);
      setShowArchiveSelect(false);
    }
  };

  const availableColumns = columns.filter(col => col.id !== lead.category);

  return (
    <Popover open={isOpen} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 hover:bg-muted"
          onClick={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          onTouchStart={(e) => e.stopPropagation()}
        >
          <MoreVertical className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56" align="end">
        <div className="space-y-1">
          {!showMoveSelect && !showArchiveSelect && (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-start"
                onClick={(e) => {
                  e.stopPropagation();
                  handleScheduleMeeting();
                }}
              >
                <Calendar className="h-4 w-4 mr-2" />
                Agendar Reunião
              </Button>
              
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-start"
                onClick={(e) => {
                  e.stopPropagation();
                  handleOpenCard();
                }}
              >
                <Eye className="h-4 w-4 mr-2" />
                Abrir card
              </Button>
              
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-start"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowMoveSelect(true);
                }}
              >
                <Move className="h-4 w-4 mr-2" />
                Mover
              </Button>
              
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-start"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowArchiveSelect(true);
                }}
              >
                <Archive className="h-4 w-4 mr-2" />
                Arquivar
              </Button>
              
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-start"
                onClick={(e) => {
                  e.stopPropagation();
                  // Funcionalidade será adicionada depois
                }}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Excluir
              </Button>
            </>
          )}

          {showMoveSelect && (
            <div className="space-y-2">
              <div className="text-sm font-medium">Mover para:</div>
              <Select onValueChange={handleMoveLead}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecione uma coluna" />
                </SelectTrigger>
                <SelectContent>
                  {availableColumns.map((column) => (
                    <SelectItem key={column.id} value={column.id}>
                      {column.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="sm"
                className="w-full"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowMoveSelect(false);
                }}
              >
                Voltar
              </Button>
            </div>
          )}

          {showArchiveSelect && (
            <div className="space-y-2">
              <div className="text-sm font-medium">Arquivar em:</div>
              <Select onValueChange={handleArchiveLead}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecione arquivo" />
                </SelectTrigger>
                <SelectContent>
                  {archivedColumns.map((column) => (
                    <SelectItem key={column.id} value={column.id}>
                      {column.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="sm"
                className="w-full"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowArchiveSelect(false);
                }}
              >
                Voltar
              </Button>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}