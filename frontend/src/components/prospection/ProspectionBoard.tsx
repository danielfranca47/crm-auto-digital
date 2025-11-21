import React, { useEffect, useMemo, useState } from 'react';
import { ProspectionColumn } from './ProspectionColumn';
import { BulkActions } from './BulkActions';
import {
  ProspectionLead,
  ProspectionColumn as ProspectionColumnType,
  ProspectionMethod
} from '@/types/prospection';
import { CrmHeader } from '@/components/CrmHeader';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';
import { CheckSquare, Square } from 'lucide-react';
import { api } from '@/services/api';

interface ProspectionBoardProps {
  columns: ProspectionColumnType[];
  onUpdateLead: (leadId: string, updates: Partial<ProspectionLead>) => void;
  onMoveToNext: (leadId: string) => void;
  onBulkProspection: (leadIds: string[], methods: ProspectionMethod[]) => void;
}

export function ProspectionBoard({
  columns,
  onUpdateLead,
  onMoveToNext,
  onBulkProspection
}: ProspectionBoardProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedLeads, setSelectedLeads] = useState<Set<string>>(new Set());
  const [showSelection, setShowSelection] = useState(false);

  // ---- estados de automação ----
  const [waLogged, setWaLogged] = useState<boolean | null>(null);
  const [agentOnline, setAgentOnline] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [seenQueueIds, setSeenQueueIds] = useState<Set<number>>(new Set());
  const [lastResultsAt, setLastResultsAt] = useState<number>(0);
  

  const navigate = useNavigate();

  // ---- filtros de busca ----
  const filteredColumns = useMemo(() => {
    const q = (searchTerm || "").toLowerCase();
    return columns.map(column => ({
      ...column,
      leads: column.leads.filter(lead =>
        lead.contactName.toLowerCase().includes(q) ||
        lead.phone.includes(searchTerm) ||
        lead.origin.toLowerCase().includes(q)
      )
    }));
  }, [columns, searchTerm]);

  // ---- seleção de cards ----
  const handleSelectLead = (leadId: string, selected: boolean) => {
    setSelectedLeads(prev => {
      const next = new Set(prev);
      if (selected) next.add(leadId);
      else next.delete(leadId);
      return next;
    });
  };

  const handleSelectAll = (columnId: string, selected: boolean) => {
    // só permite seleção em "À Prospectar"
    if (columnId !== 'to-prospect') return;
    const column = filteredColumns.find(col => col.id === columnId);
    if (!column) return;

    setSelectedLeads(prev => {
      const next = new Set(prev);
      column.leads.forEach(lead => {
        if (selected) next.add(lead.id);
        else next.delete(lead.id);
      });
      return next;
    });
  };

  // ---- único gatilho de prospecção em massa (retângulo) ----
  const handleBulkFromBanner = async (methods: ProspectionMethod[]) => {
    const leadIds = Array.from(selectedLeads);

    // 1) Se WhatsApp estiver marcado, enfileira no backend
    let queuedIdsStr: string[] = [];
    if (methods.includes('whatsapp') && leadIds.length > 0) {
      try {
        const idsNum = leadIds.map(id => parseInt(id, 10)).filter(n => !Number.isNaN(n));
        const resp = await api.prospeccao.whatsapp.enqueue(idsNum);
        // resp: { ok, queued: [{lead_id, message_id}], skipped: [{lead_id, reason}] }

        queuedIdsStr = (resp?.queued || []).map((q: any) => String(q.lead_id));

        const skipped = resp?.skipped || [];
        if (skipped.length) {
          console.warn("Itens pulados na fila:", skipped);
          // aqui você pode disparar um toast/snackbar se quiser
        }

        // ajusta contagem de pendentes local (não é obrigatório, mas ajuda)
        setPendingCount(prev => prev + queuedIdsStr.length);
        refreshAgentOverview();

      } catch (e) {
        console.error('Falha ao enfileirar WhatsApp:', e);
      }
    }

    // 2) Atualiza a UI movendo APENAS os que foram realmente enfileirados
    const idsToMove = methods.includes('whatsapp') ? queuedIdsStr : leadIds;
    if (idsToMove.length > 0) {
      onBulkProspection(idsToMove, methods);
    }

    // 3) Limpa seleção; mantém o retângulo aberto se o worker ficou ligado
    setSelectedLeads(new Set());
    if (!agentOnline) setShowSelection(false);
  };

  const handleClearSelection = () => setSelectedLeads(new Set());

  // Mantém o painel visível quando há agente online para acompanhar fila
  useEffect(() => {
    if (agentOnline && selectedLeads.size === 0) {
      setShowSelection(true);
    }
  }, [agentOnline, selectedLeads.size]);

  const toggleSelectionMode = () => {
    setShowSelection(prev => !prev);
    if (showSelection) setSelectedLeads(new Set());
  };

  // ---- status WA e Worker ----
  const refreshLogin = async () => {
    try {
      const r = await api.whatsapp.verificarLogin();
      setWaLogged(!!r?.logado);
    } catch {
      setWaLogged(null);
    }
  };

  const refreshAgentOverview = async () => {
    try {
      const overview = await api.agents.overview();
      const agents = Array.isArray(overview?.agents) ? overview.agents : [];
      const anyOnline = agents.some((agent: any) => agent?.online);
      setAgentOnline(anyOnline);
      if (overview?.summary?.pending !== undefined) {
        setPendingCount(Number(overview.summary.pending) || 0);
      }
    } catch {
      setAgentOnline(false);
    }
  };

  const refreshQueue = async () => {
    try {
      const items = await api.prospeccao.whatsapp.queue(25);
      setPendingCount(Array.isArray(items) ? items.length : 0);
    } catch {
      setPendingCount(0);
    }
  };

// aplica resultados processados (sent/failed) recentes com gate + throttling
  const refreshResults = async () => {
    // Só consulta /recent se fizer sentido:
    // - worker rodando, OU
    // - ainda há pendências na fila.
    if (!agentOnline && pendingCount === 0) return;

    // Quando o worker está PARADO, limite a chamada a cada 15s
    const now = Date.now();
    if (!agentOnline && now - lastResultsAt < 15_000) return;

    try {
      const rows: any[] = await api.prospeccao.whatsapp.recent(180); // últimos 3 min
      if (!Array.isArray(rows) || rows.length === 0) {
        setLastResultsAt(now);
        return;
      }

      setSeenQueueIds(prev => {
        const next = new Set(prev);
        for (const r of rows) {
          if (next.has(r.id)) continue; // já aplicado nesta sessão
          next.add(r.id);

          const leadIdStr = String(r.lead_id);
          if (r.status === 'sent') {
            onUpdateLead(leadIdStr, { category: 'qualification' } as any);
          } else if (r.status === 'failed') {
            onUpdateLead(leadIdStr, { category: 'to-prospect' } as any);
          }
        }
        return next;
      });
    } catch {
      // silencioso
    } finally {
      setLastResultsAt(now);
    }
  };


  // boot: pega um snapshot de status
  useEffect(() => {
    refreshLogin();
    refreshAgentOverview();
    refreshQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // polling leve: fila, agente e resultados
  useEffect(() => {
    let t: number | null = null;

    const tick = async () => {
      await refreshAgentOverview();
      await refreshQueue();
      await refreshResults();
      const next = agentOnline ? 2000 : 7000;
      t = window.setTimeout(tick, next);
    };

    t = window.setTimeout(tick, agentOnline ? 1500 : 4000);
    return () => {
      if (t) window.clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentOnline]);

  return (
    <div className="min-h-screen bg-background">
      <CrmHeader
        onNewLead={() => navigate('/')}
        onDashboard={() => navigate('/dashboard')}
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
        allColumns={[]}
        onLeadSelect={() => navigate('/')}
      />

      <main className="container mx-auto px-6 py-8">
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold text-foreground">Prospecção Inteligente</h1>
            <p className="text-muted-foreground">
              Gerencie e automatize sua prospecção com leads do CRM
            </p>
          </div>

          <div className="flex justify-center">
            <Button
              variant={showSelection ? "default" : "outline"}
              onClick={toggleSelectionMode}
              className="flex items-center gap-2"
            >
              {showSelection ? <CheckSquare className="h-4 w-4" /> : <Square className="h-4 w-4" />}
              {showSelection ? 'Cancelar Seleção' : 'Seleção em Massa'}
            </Button>
          </div>

          {/* Retângulo: único ponto de controle */}
          <BulkActions
            selectedCount={selectedLeads.size}
            onBulkProspection={handleBulkFromBanner}
            onClearSelection={handleClearSelection}
            agentOnline={agentOnline}
            waLogged={waLogged}
            pendingCount={pendingCount}
          />

          <div className="flex gap-6 overflow-x-auto pb-4 justify-center">
            {filteredColumns.map((column) => (
              <ProspectionColumn
                key={column.id}
                column={column}
                onUpdateLead={onUpdateLead}
                onMoveToNext={onMoveToNext}
                selectedLeads={selectedLeads}
                onSelectLead={handleSelectLead}
                onSelectAll={handleSelectAll}
                showSelection={showSelection}
              />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
