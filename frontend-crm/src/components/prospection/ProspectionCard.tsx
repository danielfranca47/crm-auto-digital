import React, { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { TaskChecklist } from './TaskChecklist';
import { ProspectionActions } from './ProspectionActions';
import { ProspectionCardDialog } from './ProspectionCardDialog';
import { ProspectionLead, ProspectionMethod } from '@/types/prospection';
import { Phone, Mail, MapPin, Calendar, ChevronDown, ChevronUp, Eye } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { leadDisplayName } from '@/utils/leadDisplayName';
import { formatLeadOriginLabel } from '@/lib/lead-origin';

interface ProspectionCardProps {
  lead: ProspectionLead;
  columnId: 'to-prospect' | 'in-progress' | 'qualification';
  onUpdateLead: (leadId: string, updates: Partial<ProspectionLead>) => void;
  onMoveToNext: (leadId: string) => void;
  isSelected?: boolean;
  onSelect?: (leadId: string, selected: boolean) => void;
  showSelection?: boolean;
}

export function ProspectionCard({ 
  lead, 
  columnId, 
  onUpdateLead, 
  onMoveToNext, 
  isSelected = false,
  onSelect,
  showSelection = false 
}: ProspectionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const handleMethodSelect = (methods: ProspectionMethod[]) => {
    const tasks = methods.map(method => ({
      id: `${lead.id}-${method}`,
      method,
      completed: false,
      automatedTask: method === 'email' || method === 'whatsapp'
    }));

    onUpdateLead(lead.id, {
      prospectionTasks: tasks,
      prospectionStatus: 'in-progress',
      prospectionStartedAt: new Date()
    });
    onMoveToNext(lead.id);
  };

  const handleTaskComplete = (taskId: string, completed: boolean) => {
    const updatedTasks = lead.prospectionTasks.map(task =>
      task.id === taskId 
        ? { ...task, completed, completedAt: completed ? new Date() : undefined }
        : task
    );

    const allCompleted = updatedTasks.every(task => task.completed);
    
    onUpdateLead(lead.id, {
      prospectionTasks: updatedTasks,
      prospectionStatus: allCompleted ? 'qualification' : 'in-progress',
      prospectionCompletedAt: allCompleted ? new Date() : undefined
    });

    if (allCompleted) {
      onMoveToNext(lead.id);
    }
  };

  return (
    <Card className="lead-card border-lead-card-border hover:shadow-elegant transition-smooth">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3 flex-1">
            {showSelection && onSelect && columnId === 'to-prospect' && (
              <Checkbox
                checked={isSelected}
                onCheckedChange={(checked) => onSelect(lead.id, checked as boolean)}
                className="mt-1"
              />
            )}
            <div className="space-y-1">
              <h4 className="font-medium text-foreground">{leadDisplayName(lead)}</h4>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Phone className="h-3 w-3" />
                {lead.phone}
              </div>
            </div>
          </div>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsDialogOpen(true)}
              className="h-8 w-8 p-0"
              title="Ver detalhes"
            >
              <Eye className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">
            <MapPin className="h-3 w-3 mr-1" />
            {formatLeadOriginLabel(lead.origin)}
          </Badge>
          <span className="text-xs text-muted-foreground">
            <Calendar className="h-3 w-3 inline mr-1" />
            {formatDistanceToNow(lead.createdAt, { addSuffix: true, locale: ptBR })}
          </span>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent className="pt-0 space-y-4">
          {lead.observations && (
            <p className="text-sm text-muted-foreground">{lead.observations}</p>
          )}

          {columnId === 'to-prospect' && (
            <ProspectionActions onMethodSelect={handleMethodSelect} />
          )}

          {columnId === 'in-progress' && lead.prospectionTasks.length > 0 && (
            <TaskChecklist
              tasks={lead.prospectionTasks}
              onTaskComplete={handleTaskComplete}
            />
          )}

          {columnId === 'qualification' && (
            <div className="text-center py-2">
              <Badge variant="default" className="bg-green-500">
                ✓ Prospecção Concluída
              </Badge>
              {lead.prospectionCompletedAt && (
                <p className="text-xs text-muted-foreground mt-1">
                  Finalizada {formatDistanceToNow(lead.prospectionCompletedAt, { addSuffix: true, locale: ptBR })}
                </p>
              )}
            </div>
          )}
        </CardContent>
      )}
      
      <ProspectionCardDialog
        lead={lead}
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        onUpdateLead={onUpdateLead}
      />
    </Card>
  );
}