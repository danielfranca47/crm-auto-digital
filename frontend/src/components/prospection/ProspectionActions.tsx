import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { ProspectionMethod } from '@/types/prospection';
import { Mail, MessageCircle, Phone, Play } from 'lucide-react';

interface ProspectionActionsProps {
  onMethodSelect: (methods: ProspectionMethod[]) => void;
}

export function ProspectionActions({ onMethodSelect }: ProspectionActionsProps) {
  const [selectedMethods, setSelectedMethods] = useState<ProspectionMethod[]>([]);

  const methods = [
    { id: 'email' as ProspectionMethod, label: 'E-mail', icon: Mail, automated: true },
    { id: 'whatsapp' as ProspectionMethod, label: 'WhatsApp', icon: MessageCircle, automated: true },
    { id: 'call' as ProspectionMethod, label: 'Ligação', icon: Phone, automated: false }
  ];

  const handleMethodToggle = (method: ProspectionMethod) => {
    setSelectedMethods(prev => 
      prev.includes(method)
        ? prev.filter(m => m !== method)
        : [...prev, method]
    );
  };

  const handleStartProspection = () => {
    if (selectedMethods.length > 0) {
      onMethodSelect(selectedMethods);
    }
  };

  return (
    <div className="space-y-4">
      <h5 className="text-sm font-medium text-foreground">Métodos de Prospecção</h5>
      
      <div className="space-y-3">
        {methods.map((method) => (
          <div key={method.id} className="flex items-center space-x-3 p-2 rounded-lg hover:bg-muted/50 transition-smooth">
            <Checkbox
              id={method.id}
              checked={selectedMethods.includes(method.id)}
              onCheckedChange={() => handleMethodToggle(method.id)}
            />
            <div className="flex items-center space-x-2 flex-1">
              <method.icon className="h-4 w-4" />
              <span className="text-sm">{method.label}</span>
              {method.automated && (
                <span className="text-xs text-muted-foreground">(Automático)</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <Button
        onClick={handleStartProspection}
        disabled={selectedMethods.length === 0}
        className="w-full gradient-primary text-primary-foreground"
        size="sm"
      >
        <Play className="h-4 w-4 mr-2" />
        Iniciar Prospecção
      </Button>

      <div className="text-xs text-muted-foreground">
        Selecione os métodos desejados para iniciar a prospecção
      </div>
    </div>
  );
}