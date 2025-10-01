import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Lead, KanbanColumn, NewLeadForm, LeadStatus, LeadAppointment } from '@/types/crm';
import { ProspectionLead, ProspectionColumn, ProspectionMethod } from '@/types/prospection';
import { KANBAN_COLUMNS, ARCHIVED_COLUMNS } from '@/data/mockData';
import { api } from '../services/api';

interface LeadsContextType {
  columns: KanbanColumn[];
  archivedColumns: KanbanColumn[];
  prospectionColumns: ProspectionColumn[];
  appointmentsByLead: Record<string, LeadAppointment[]>;

  updateLead: (leadId: string, updates: Partial<Lead>) => void;
  moveLead: (leadId: string, newCategory: LeadStatus) => void;
  archiveLead: (leadId: string, archiveCategory: LeadStatus) => void;
  addLead: (leadData: NewLeadForm) => void;

  loadAppointments: (leadId: string) => Promise<LeadAppointment[]>;
  createAppointment: (leadId: string, payload: { description: string; startAt: Date; endAt?: Date | null }) => Promise<LeadAppointment>;
  updateAppointment: (
    leadId: string,
    appointmentId: string,
    payload: { description?: string; startAt?: Date; endAt?: Date | null }
  ) => Promise<LeadAppointment>;
  deleteAppointment: (leadId: string, appointmentId: string) => Promise<void>;

  moveProspectionLead: (leadId: string, newStatus: 'to-prospect' | 'in-progress' | 'prospected') => void;
  bulkProspection: (leadIds: string[], methods: ProspectionMethod[]) => void;
  updateProspectionLead: (leadId: string, patch: Partial<Lead>) => Promise<void>;
  reloadAllLeads: () => Promise<void>;
}

const LeadsContext = createContext<LeadsContextType | undefined>(undefined);

export function useLeads() {
  const context = useContext(LeadsContext);
  if (context === undefined) {
    throw new Error('useLeads must be used within a LeadsProvider');
  }
  return context;
}

interface LeadsProviderProps {
  children: ReactNode;
}

// ---------- helpers ----------
function mapRawLead(raw: any): Lead {
  const nextRaw = raw?.nextScheduledAction;
  const nextScheduledAction = nextRaw && nextRaw.date
    ? {
        date: nextRaw.date instanceof Date ? nextRaw.date : new Date(nextRaw.date),
        description: nextRaw.description ?? '',
      }
    : undefined;

  return {
    id: String(raw.id),
    companyName: raw.companyName || 'Empresa sem nome',
    contactName: raw.contactName || '',
    phone: raw.phone || '',
    email: raw.email || '',
    origin: raw.origin || '',
    category: raw.category || 'to-prospect',
    customMessage: raw.customMessage || '',
    observations: raw.observations || '',
    createdAt: raw.createdAt ? new Date(raw.createdAt) : new Date(),
    lastMovement: raw.lastMovement ? new Date(raw.lastMovement) : new Date(),
    nextScheduledAction,
  };
}

function mapRawAppointment(raw: any): LeadAppointment {
  return {
    id: String(raw.id),
    leadId: String(
      raw.lead_id ?? raw.leadId ?? raw.leadID ?? raw.lead?.id ?? raw.lead ?? ''
    ),
    description: raw.description ?? '',
    startAt: raw.start_at
      ? new Date(raw.start_at)
      : raw.startAt instanceof Date
        ? raw.startAt
        : raw.startAt
          ? new Date(raw.startAt)
          : new Date(),
    endAt: raw.end_at
      ? new Date(raw.end_at)
      : raw.endAt instanceof Date
        ? raw.endAt
        : raw.endAt
          ? new Date(raw.endAt)
          : raw.end_at ?? raw.endAt ?? null,
    createdAt: raw.created_at
      ? new Date(raw.created_at)
      : raw.createdAt instanceof Date
        ? raw.createdAt
        : raw.createdAt
          ? new Date(raw.createdAt)
          : raw.created_at ?? raw.createdAt ?? null,
    updatedAt: raw.updated_at
      ? new Date(raw.updated_at)
      : raw.updatedAt instanceof Date
        ? raw.updatedAt
        : raw.updatedAt
          ? new Date(raw.updatedAt)
          : raw.updated_at ?? raw.updatedAt ?? null,
  };
}

function toProspectionLead(l: Lead): ProspectionLead {
  const prospectionStatus: 'to-prospect' | 'in-progress' | 'prospected' =
    l.category === 'in-progress' ? 'in-progress'
    : l.category === 'prospected' ? 'prospected'
    : 'to-prospect';

  return {
    ...l,
    prospectionTasks: [],
    prospectionStatus,
  };
}

export function LeadsProvider({ children }: LeadsProviderProps) {
  const [columns, setColumns] = useState<KanbanColumn[]>([]);
  const [archivedColumns, setArchivedColumns] = useState<KanbanColumn[]>([]);
  const [prospectionColumns, setProspectionColumns] = useState<ProspectionColumn[]>([
    { id: 'to-prospect', title: 'À Prospectar', leads: [], color: '#6366f1' },
    { id: 'in-progress', title: 'Em Andamento', leads: [], color: '#f59e0b' },
    { id: 'prospected', title: 'Prospectados', leads: [], color: '#22c55e' },
  ]);
  const [appointmentsByLead, setAppointmentsByLead] = useState<Record<string, LeadAppointment[]>>({});

  // --------- persistência de cópia no lead e atualização visual do card ----------
  const updateProspectionLead = async (leadId: string, patch: Partial<Lead>) => {
    const { nextScheduledAction: _ignore, ...payload } = patch as Partial<Lead> & {
      nextScheduledAction?: Lead['nextScheduledAction'];
    };
    await api.updateLead(leadId, payload);
    setProspectionColumns((cols) =>
      cols.map((col) => ({
        ...col,
        leads: col.leads.map((l) => (l.id === leadId ? { ...l, ...patch } : l)),
      }))
    );
  };

  // --------- recarregar tudo do backend e reconstruir quadros ----------
  const reloadAllLeads = async (): Promise<void> => {
    try {
      const response = await api.getLeads();
      const rawLeads = response?.data ?? response;
      const allLeads: Lead[] = (Array.isArray(rawLeads) ? rawLeads : []).map(mapRawLead);

      // CRM: colunas principais e arquivadas (o board principal NÃO tem 'in-progress' mesmo que exista no DB)
      const nextColumns: KanbanColumn[] = KANBAN_COLUMNS.map((column) => ({
        ...column,
        leads: allLeads.filter((lead) => lead.category === column.id),
      }));

      const nextArchived: KanbanColumn[] = ARCHIVED_COLUMNS.map((column) => ({
        ...column,
        leads: allLeads.filter((lead) => lead.category === column.id),
      }));

      setColumns(nextColumns);
      setArchivedColumns(nextArchived);

      // Prospecção: derivado do status do CRM (inclui 'in-progress')
      const toProspectLeads = allLeads.filter((l) => l.category === 'to-prospect').map(toProspectionLead);
      const inProgressLeads = allLeads.filter((l) => l.category === 'in-progress').map(toProspectionLead);
      const prospectedLeads = allLeads.filter((l) => l.category === 'prospected').map(toProspectionLead);

      setProspectionColumns((prev) =>
        prev.map((col) => {
          if (col.id === 'to-prospect') return { ...col, leads: toProspectLeads };
          if (col.id === 'in-progress') return { ...col, leads: inProgressLeads };
          if (col.id === 'prospected') return { ...col, leads: prospectedLeads };
          return col;
        })
      );
    } catch (error) {
      console.error('Erro ao recarregar leads:', error);
    }
  };

  // carregamento inicial
  useEffect(() => {
    reloadAllLeads();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --------- operações no CRM (columns) ----------
  const updateLead = async (leadId: string, updates: Partial<Lead>) => {
    // Atualiza no front (CRM)
    setColumns((prev) =>
      prev.map((column) => ({
        ...column,
        leads: column.leads.map((lead) => (lead.id === leadId ? { ...lead, ...updates } : lead)),
      }))
    );

    // Atualiza no back
    try {
      const { nextScheduledAction: _ignore, ...payload } = updates as Partial<Lead> & {
        nextScheduledAction?: Lead['nextScheduledAction'];
      };
      await api.updateLead(leadId, payload);
    } catch (error) {
      console.error('Erro ao atualizar lead no backend:', error);
    }

    // Sincroniza quadro de prospecção quando category mudar
    if (updates.category) {
      syncProspectionStatus(leadId, updates.category as LeadStatus);
    }
  };

  const moveLead = async (leadId: string, newCategory: LeadStatus) => {
    const allLeads = [...columns, ...archivedColumns].flatMap((col) => col.leads);
    const lead = allLeads.find((l) => l.id === leadId);
    if (!lead) return;

    const lastMovement = new Date();
    const updatedLead = { ...lead, category: newCategory, lastMovement };

    // Atualiza colunas principais (CRM)
    setColumns((prev) =>
      prev.map((column) => {
        const filtered = column.leads.filter((l) => l.id !== leadId);
        if (column.id === newCategory) {
          return { ...column, leads: [...filtered, updatedLead] };
        }
        return { ...column, leads: filtered };
      })
    );

    // Remove dos arquivados (se existir lá)
    setArchivedColumns((prev) =>
      prev.map((column) => ({ ...column, leads: column.leads.filter((l) => l.id !== leadId) }))
    );

    // Backend
    try {
      await api.updateLead(leadId, { category: newCategory, lastMovement });
    } catch (error) {
      console.error('Erro ao mover lead no backend:', error);
    }

    // Sincroniza prospecção
    syncProspectionStatus(leadId, newCategory);
  };

  const archiveLead = async (leadId: string, archiveCategory: LeadStatus) => {
    const allLeads = [...columns, ...archivedColumns].flatMap((col) => col.leads);
    const lead = allLeads.find((l) => l.id === leadId);
    if (!lead) return;

    const lastMovement = new Date();
    const updatedLead = { ...lead, category: archiveCategory, lastMovement };

    // Tira das colunas normais
    setColumns((prev) =>
      prev.map((column) => ({ ...column, leads: column.leads.filter((l) => l.id !== leadId) }))
    );

    // Coloca na coluna arquivada correspondente
    setArchivedColumns((prev) =>
      prev.map((column) => {
        if (column.id === archiveCategory) {
          return { ...column, leads: [...column.leads, updatedLead] };
        }
        return column;
      })
    );

    // Backend
    try {
      await api.updateLead(leadId, { category: archiveCategory, lastMovement });
    } catch (error) {
      console.error('Erro ao arquivar lead no backend:', error);
    }

    // Sincroniza prospecção
    syncProspectionStatus(leadId, archiveCategory);
  };

  const addLead = async (leadData: NewLeadForm) => {
    try {
      const response = await api.createLead({
        companyName: leadData.companyName,
        contactName: leadData.contactName,
        phone: leadData.phone,
        email: leadData.email || '',
        origin: leadData.origin,
        category: leadData.category,
        customMessage: leadData.customMessage || '',
        observations: leadData.observations,
        prioridade: 'Média',
      });

      const newLead: Lead = {
        id: response.id.toString(),
        companyName: leadData.companyName,
        contactName: leadData.contactName,
        phone: leadData.phone,
        email: leadData.email || '',
        origin: leadData.origin,
        category: leadData.category,
        customMessage: leadData.customMessage || '',
        observations: leadData.observations,
        lastMovement: new Date(),
        createdAt: new Date(),
        nextScheduledAction: undefined,
      };

      setColumns((prev) =>
        prev.map((column) => {
          if (column.id === newLead.category) {
            return { ...column, leads: [...column.leads, newLead] };
          }
          return column;
        })
      );
    } catch (error) {
      console.error('Erro ao criar lead:', error);
    }
  };

  // --------- Appointments (CRUD) ----------
  const loadAppointments = async (leadId: string): Promise<LeadAppointment[]> => {
    const data = await api.getAppointments(leadId);
    const appointments = (Array.isArray(data) ? data : [])
      .map(mapRawAppointment)
      .sort((a, b) => a.startAt.getTime() - b.startAt.getTime());
    setAppointmentsByLead((prev) => ({ ...prev, [leadId]: appointments }));
    return appointments;
  };

  const createAppointment = async (
    leadId: string,
    payload: { description: string; startAt: Date; endAt?: Date | null }
  ): Promise<LeadAppointment> => {
    const appointment = await api.createAppointment(leadId, payload);
    const mapped = mapRawAppointment(appointment);
    setAppointmentsByLead((prev) => ({
      ...prev,
      [leadId]: [...(prev[leadId] ?? []), mapped].sort((a, b) => a.startAt.getTime() - b.startAt.getTime()),
    }));
    await reloadAllLeads();
    return mapped;
  };

  const updateAppointment = async (
    leadId: string,
    appointmentId: string,
    payload: { description?: string; startAt?: Date; endAt?: Date | null }
  ): Promise<LeadAppointment> => {
    const appointment = await api.updateAppointment(leadId, appointmentId, payload);
    const mapped = mapRawAppointment(appointment);
    setAppointmentsByLead((prev) => ({
      ...prev,
      [leadId]: (prev[leadId] ?? [])
        .map((item) => (item.id === mapped.id ? mapped : item))
        .sort((a, b) => a.startAt.getTime() - b.startAt.getTime()),
    }));
    await reloadAllLeads();
    return mapped;
  };

  const deleteAppointment = async (leadId: string, appointmentId: string): Promise<void> => {
    await api.deleteAppointment(leadId, appointmentId);
    setAppointmentsByLead((prev) => ({
      ...prev,
      [leadId]: (prev[leadId] ?? []).filter((item) => item.id !== appointmentId),
    }));
    await reloadAllLeads();
  };

  // --------- prospecção (UI + persistência) ----------
  const moveProspectionLead = (leadId: string, newStatus: 'to-prospect' | 'in-progress' | 'prospected') => {
    // 1) Atualiza quadro de prospecção (UI)
    setProspectionColumns((prev) => {
      const allLeads = prev.flatMap((col) => col.leads);
      const lead = allLeads.find((l) => l.id === leadId);
      if (!lead) return prev;

      const updatedLead = { ...lead, prospectionStatus: newStatus };
      return prev.map((column) => {
        const filtered = column.leads.filter((l) => l.id !== leadId);
        if (column.id === newStatus) {
          return { ...column, leads: [...filtered, updatedLead] };
        }
        return { ...column, leads: filtered };
      });
    });

    // 2) Persistir no CRM (DB): agora 1:1 com o status de prospecção
    updateLead(leadId, { category: newStatus } as Partial<Lead>);
  };

  const bulkProspection = (leadIds: string[], methods: ProspectionMethod[]) => {
    try {
      if (methods.includes('whatsapp')) {
        // mover para “Em andamento” (persistido no DB) assim que entrar no fluxo
        leadIds.forEach((id) => {
          moveProspectionLead(id, 'in-progress');
        });
      }
      // (Futuro) e-mail/ligação – apenas UI também.
    } catch (err) {
      console.error('Erro na prospecção em massa (UI):', err);
    }
  };

  // Mantém a visão de prospecção sincronizada com o CRM (inclui 'in-progress')
  const syncProspectionStatus = (leadId: string, crmCategory: LeadStatus) => {
    if (
      crmCategory === 'to-prospect' ||
      crmCategory === 'in-progress' ||
      crmCategory === 'prospected'
    ) {
      const prospectionStatus = crmCategory as 'to-prospect' | 'in-progress' | 'prospected';

      setProspectionColumns((prev) => {
        const allLeads = prev.flatMap((col) => col.leads);
        const existing = allLeads.find((l) => l.id === leadId);

        if (!existing) {
          // injeta a partir do CRM
          const crmLead = [...columns, ...archivedColumns].flatMap((c) => c.leads).find((l) => l.id === leadId);
          if (crmLead) {
            const pLead: ProspectionLead = { ...crmLead, prospectionTasks: [], prospectionStatus: prospectionStatus };
            return prev.map((col) => (col.id === prospectionStatus ? { ...col, leads: [...col.leads, pLead] } : col));
          }
          return prev;
        }

        // já existe: move de coluna
        return prev.map((col) => {
          const filtered = col.leads.filter((l) => l.id !== leadId);
          if (col.id === prospectionStatus) {
            const updated = { ...existing, prospectionStatus };
            return { ...col, leads: [...filtered, updated] };
          }
          return { ...col, leads: filtered };
        });
      });
    } else {
      // Outras categorias tiram o lead do quadro de prospecção
      setProspectionColumns((prev) =>
        prev.map((col) => ({ ...col, leads: col.leads.filter((l) => l.id !== leadId) }))
      );
    }
  };

  const value: LeadsContextType = {
    columns,
    archivedColumns,
    prospectionColumns,
    appointmentsByLead,
    updateLead,
    moveLead,
    archiveLead,
    addLead,
    loadAppointments,
    createAppointment,
    updateAppointment,
    deleteAppointment,
    moveProspectionLead,
    bulkProspection,
    updateProspectionLead,
    reloadAllLeads,
  };

  return <LeadsContext.Provider value={value}>{children}</LeadsContext.Provider>;
}
