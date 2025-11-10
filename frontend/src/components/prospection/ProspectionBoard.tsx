import React, { useEffect, useMemo, useRef, useState } from 'react';
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
import { useLeads } from '@/contexts/LeadsContext';

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
  const { reloadAllLeads } = useLeads();

  // ---- estados de automação ----
  const [agentOnline, setAgentOnline] = useState<boolean | null>(null);
  const [workerRunning, setWorkerRunning] = useState(false); // indica se há jobs em andamento
  const [pendingCount, setPendingCount] = useState(0);
  const [seenQueueIds, setSeenQueueIds] = useState<Set<number>>(new Set());
  const prevWorkerRunning = useRef<boolean>(false);
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

        // atualiza visão geral da fila baseada em jobs
        await refreshOverview();

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
    if (!workerRunning) setShowSelection(false);
  };

  const handleClearSelection = () => setSelectedLeads(new Set());

  // Enquanto o worker estiver rodando, manter o banner visível e travar o toggle
  useEffect(() => {
    if (workerRunning) setShowSelection(true);
  }, [workerRunning]);

  const toggleSelectionMode = () => {
    if (workerRunning) return; // evita fechar enquanto roda
    setShowSelection(prev => !prev);
    if (showSelection) setSelectedLeads(new Set());
  };

  // ---- status WA e Worker ----
  const refreshOverview = async () => {
    try {
      const overview = await api.agents.overview();
      const jobs = overview?.jobs ?? { pending: 0, in_progress: 0 };
      setPendingCount(jobs.pending ?? 0);
      setWorkerRunning((jobs.in_progress ?? 0) > 0);

      const now = Date.now();
      const agentList = overview?.agents ?? [];
      const anyOnline = agentList.some((agent) => {
        if (agent?.status === 'active') return true;
        if (!agent?.last_seen) return false;
        const last = new Date(agent.last_seen).getTime();
        return now - last < 2 * 60 * 1000; // 2 minutos de tolerância
      });
      setAgentOnline(anyOnline ? true : agentList.length ? false : null);
    } catch (err) {
      console.warn('Não foi possível obter overview dos agentes', err);
      setAgentOnline(null);
      setPendingCount(0);
      setWorkerRunning(false);
    }
  };

// aplica resultados processados (sent/failed) recentes com gate + throttling
  const refreshResults = async () => {
    // Só consulta /recent se fizer sentido:
    // - worker rodando, OU
    // - ainda há pendências na fila.
    if (!workerRunning && pendingCount === 0) return;

    // Quando o worker está PARADO, limite a chamada a cada 15s
    const now = Date.now();
    if (!workerRunning && now - lastResultsAt < 15_000) return;

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
            onUpdateLead(leadIdStr, { category: 'prospected' } as any);
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
    refreshOverview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // polling leve: fila, worker e resultados
  useEffect(() => {
    let t: number | null = null;

    const tick = async () => {
      await refreshOverview();
      await refreshResults();
      // jobs em andamento => polling rápido; caso contrário, mais lento
      const next = workerRunning ? 1500 : 6000;
      t = window.setTimeout(tick, next);
    };

    t = window.setTimeout(tick, workerRunning ? 1000 : 3000);
    return () => {
      if (t) window.clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workerRunning]);

  // quando o worker parar (true -> false), sincroniza tudo do backend
  useEffect(() => {
    if (prevWorkerRunning.current && !workerRunning) {
      reloadAllLeads(); // sincroniza colunas/cards com DB depois do auto-stop
    }
    prevWorkerRunning.current = workerRunning;
  }, [workerRunning, reloadAllLeads]);

  const stopWorker = async () => {
    // No novo fluxo não é possível parar o agente remotamente; apenas atualizamos o snapshot.
    await refreshOverview();
    await reloadAllLeads();
  };

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
              disabled={workerRunning} // evita fechar/abrir enquanto envia
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
            workerRunning={workerRunning}
            agentOnline={agentOnline}
            pendingCount={pendingCount}
            onStopWorker={stopWorker}
          />

          <div className="flex gap-6 overflow-x-auto pb-4">
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
