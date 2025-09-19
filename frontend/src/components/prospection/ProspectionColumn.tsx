import React from 'react';
import { ProspectionCard } from './ProspectionCard';
import { ProspectionColumn as ProspectionColumnType, ProspectionLead } from '@/types/prospection';
import { Card } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';

interface ProspectionColumnProps {
  column: ProspectionColumnType;
  onUpdateLead: (leadId: string, updates: Partial<ProspectionLead>) => void;
  onMoveToNext: (leadId: string) => void;
  selectedLeads?: Set<string>;
  onSelectLead?: (leadId: string, selected: boolean) => void;
  onSelectAll?: (columnId: string, selected: boolean) => void;
  showSelection?: boolean;
}

export function ProspectionColumn({
  column,
  onUpdateLead,
  onMoveToNext,
  selectedLeads,
  onSelectLead,
  onSelectAll,
  showSelection
}: ProspectionColumnProps) {
  const columnLeadIds = column.leads.map(lead => lead.id);
  const selectedInColumn = columnLeadIds.filter(id => selectedLeads?.has(id) || false);
  const isAllSelected = columnLeadIds.length > 0 && selectedInColumn.length === columnLeadIds.length;
  const isPartialSelected = selectedInColumn.length > 0 && selectedInColumn.length < columnLeadIds.length;

  // Estado do checkbox de "Selecionar todos" (true | false | "indeterminate")
  const checkedState: boolean | 'indeterminate' =
    isAllSelected ? true : isPartialSelected ? 'indeterminate' : false;

  return (
    <Card className="gradient-card border-lead-card-border min-h-[600px] w-80 flex-shrink-0">
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {showSelection && column.leads.length > 0 && column.id === 'to-prospect' && (
              <Checkbox
                id={`col-${column.id}`}
                aria-label={`Selecionar todos em ${column.title}`}
                checked={checkedState}
                onCheckedChange={(checked) => onSelectAll?.(column.id, !!checked)}
              />
            )}
            <h3 className="font-semibold text-foreground">{column.title}</h3>
          </div>
          <span
            className="text-xs px-2 py-1 rounded-full text-white font-medium"
            style={{ backgroundColor: column.color }}
          >
            {column.leads.length}
          </span>
        </div>
      </div>

      <div className="p-4 space-y-4 max-h-[500px] overflow-y-auto custom-scrollbar">
        {column.leads.map((lead) => (
          <ProspectionCard
            key={lead.id}
            lead={lead}
            columnId={column.id}
            onUpdateLead={onUpdateLead}
            onMoveToNext={onMoveToNext}
            isSelected={selectedLeads?.has(lead.id) || false}
            onSelect={onSelectLead}
            showSelection={showSelection}
          />
        ))}

        {column.leads.length === 0 && (
          <div className="text-center text-muted-foreground py-8">
            <p className="text-sm">Nenhum lead</p>
          </div>
        )}
      </div>
    </Card>
  );
}
