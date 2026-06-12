import React from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { ProspectionTask } from '@/types/prospection';
import { Mail, MessageCircle, Phone, Clock, CheckCircle } from 'lucide-react';

interface TaskChecklistProps {
  tasks: ProspectionTask[];
  onTaskComplete: (taskId: string, completed: boolean) => void;
}

export function TaskChecklist({ tasks, onTaskComplete }: TaskChecklistProps) {
  const getMethodIcon = (method: string) => {
    switch (method) {
      case 'email': return <Mail className="h-4 w-4" />;
      case 'whatsapp': return <MessageCircle className="h-4 w-4" />;
      case 'call': return <Phone className="h-4 w-4" />;
      default: return null;
    }
  };

  const getMethodLabel = (method: string) => {
    switch (method) {
      case 'email': return 'E-mail';
      case 'whatsapp': return 'WhatsApp';
      case 'call': return 'Ligação';
      default: return method;
    }
  };

  const getTaskStatus = (task: ProspectionTask) => {
    if (task.completed) {
      return <Badge variant="default" className="bg-green-500"><CheckCircle className="h-3 w-3 mr-1" />Concluído</Badge>;
    }
    if (task.automatedTask && !task.completed) {
      return <Badge variant="secondary"><Clock className="h-3 w-3 mr-1" />Automático</Badge>;
    }
    return <Badge variant="outline">Manual</Badge>;
  };

  return (
    <div className="space-y-3">
      <h5 className="text-sm font-medium text-foreground">Tarefas de Prospecção</h5>
      
      {tasks.map((task) => (
        <div key={task.id} className="flex items-center justify-between space-x-3 p-2 rounded-lg bg-muted/30">
          <div className="flex items-center space-x-3">
            <Checkbox
              id={task.id}
              checked={task.completed}
              onCheckedChange={(checked) => onTaskComplete(task.id, !!checked)}
              disabled={task.automatedTask && !task.completed}
            />
            <div className="flex items-center space-x-2">
              {getMethodIcon(task.method)}
              <span className="text-sm">{getMethodLabel(task.method)}</span>
            </div>
          </div>
          
          {getTaskStatus(task)}
        </div>
      ))}

      <div className="text-xs text-muted-foreground">
        * Tarefas automáticas são processadas automaticamente
      </div>
    </div>
  );
}