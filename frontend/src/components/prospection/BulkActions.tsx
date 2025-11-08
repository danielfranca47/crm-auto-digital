import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { ProspectionMethod } from '@/types/prospection';
import {
  Mail,
  MessageCircle,
  Phone,
  Play,
  X,
  Loader2,
  PauseCircle
} from 'lucide-react';

interface BulkActionsProps {
  selectedCount: number;
  onBulkProspection: (methods: ProspectionMethod[]) => void;
  onClearSelection: () => void;

  // Automação baseada em jobs + agente local
  workerRunning?: boolean; // indica se há jobs em andamento
  agentOnline?: boolean | null; // status do agente local
  pendingCount?: number;
  onStopWorker?: () => void; // reaproveitado como "atualizar status"
}

export function BulkActions({
  selectedCount,
  onBulkProspection,
  onClearSelection,
  workerRunning = false,
  agentOnline = null,
  pendingCount = 0,
  onStopWorker
}: BulkActionsProps) {
  const [selectedMethods, setSelectedMethods] = useState<ProspectionMethod[]>([]);

  const methods = [
    { id: 'email' as ProspectionMethod, label: 'E-mail', icon: Mail, automated: true },
    { id: 'whatsapp' as ProspectionMethod, label: 'WhatsApp', icon: MessageCircle, automated: true },
    { id: 'call' as ProspectionMethod, label: 'Ligação', icon: Phone, automated: false }
  ];

  const handleMethodToggle = (method: ProspectionMethod) => {
    setSelectedMethods(prev =>
      prev.includes(method) ? prev.filter(m => m !== method) : [...prev, method]
    );
  };

  const handleStart = () => {
    if (selectedMethods.length === 0 || selectedCount === 0) return;
    onBulkProspection(selectedMethods);
    setSelectedMethods([]);
  };

  // Mantém o retângulo visível se o worker estiver rodando
  if (selectedCount === 0 && !workerRunning) return null;

  const AgentChip = () => (
    <span
      className={
        'px-2 py-1 rounded-full text-xs ' +
        (agentOnline === true
          ? 'bg-emerald-100 text-emerald-700'
          : agentOnline === false
          ? 'bg-rose-100 text-rose-700'
          : 'bg-slate-100 text-slate-600')
      }
      title={
        agentOnline === true
          ? 'Agente Local ativo'
          : agentOnline === false
          ? 'Agente Local desconectado'
          : 'Status do agente indisponível'
      }
    >
      {agentOnline === true
        ? 'Agente Online'
        : agentOnline === false
        ? 'Agente Offline'
        : 'Agente —'}
    </span>
  );

  const WorkerChip = () => (
    <span
      className={
        'px-2 py-1 rounded-full text-xs ' +
        (workerRunning ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700')
      }
      title={workerRunning ? 'Jobs em processamento pelo agente' : 'Nenhum job em execução'}
    >
      {workerRunning ? 'Jobs em andamento' : 'Sem jobs em andamento'}
    </span>
  );

  const PendingChip = () => (
    <span className="px-2 py-1 rounded-full text-xs bg-slate-100 text-slate-700">
      Pendentes: {pendingCount}
    </span>
  );

  const startDisabled = selectedMethods.length === 0 || selectedCount === 0;

  return (
    <Card className="gradient-card border-accent p-4 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {workerRunning ? (
            <h4 className="font-medium text-foreground flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Envio em andamento
            </h4>
          ) : (
            <h4 className="font-medium text-foreground">
              {selectedCount} lead{selectedCount > 1 ? 's' : ''} selecionado{selectedCount > 1 ? 's' : ''}
            </h4>
          )}
        </div>

        {/* chips de status */}
        <div className="flex items-center gap-2">
          <AgentChip />
          <WorkerChip />
          <PendingChip />
          {!workerRunning && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearSelection}
              className="h-8 w-8 p-0"
              title="Fechar painel"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {!workerRunning && (
        <>
          <div className="space-y-4">
            <div>
              <h5 className="text-sm font-medium text-foreground mb-3">Métodos de Prospecção</h5>
              <div className="flex flex-wrap gap-4">
                {methods.map((method) => (
                  <label key={method.id} className="flex items-center space-x-2 cursor-pointer">
                    <Checkbox
                      id={`bulk-${method.id}`}
                      checked={selectedMethods.includes(method.id)}
                      onCheckedChange={() => handleMethodToggle(method.id)}
                    />
                    <div className="flex items-center space-x-1">
                      <method.icon className="h-4 w-4" />
                      <span className="text-sm">{method.label}</span>
                      {method.automated && (
                        <span className="text-xs text-muted-foreground">(Auto)</span>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div className="flex gap-2">
              <Button
                onClick={handleStart}
                disabled={startDisabled}
                className="gradient-primary text-primary-foreground"
                size="sm"
              >
                <Play className="h-4 w-4 mr-2" />
                Iniciar Prospecção em Massa
              </Button>
              <Button variant="outline" size="sm" onClick={onClearSelection}>
                Cancelar
              </Button>
            </div>

            {/* dicas contextuais */}
            {selectedMethods.includes('whatsapp') && agentOnline === false && (
              <p className="text-xs text-amber-600">
                Agente Local offline: enfileire normalmente e inicie o agente em seu computador para processar os envios.
              </p>
            )}
            {selectedMethods.includes('whatsapp') && agentOnline === null && (
              <p className="text-xs text-slate-500">
                Status do Agente Local indisponível. Os envios serão realizados assim que o agente conectar.
              </p>
            )}
          </div>
        </>
      )}

      {workerRunning && (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onStopWorker}
            className="flex items-center gap-2"
            aria-disabled={!onStopWorker}
          >
            <PauseCircle className="h-4 w-4" />
            Atualizar status da fila
          </Button>
        </div>
      )}
    </Card>
  );
}
