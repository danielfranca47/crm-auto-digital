import { Lead, KanbanColumn, DashboardMetrics } from '../types/crm';

export const KANBAN_COLUMNS: KanbanColumn[] = [
  {
    id: 'to-prospect',
    title: 'À Prospectar',
    leads: [],
    color: '#6366f1'
  },
  {
    id: 'qualification',
    title: 'Qualificação',
    leads: [],
    color: '#3b82f6'
  },
  {
    id: 'apresentation',
    title: 'Apresentação',
    leads: [],
    color: '#f59e0b'
  },
  {
    id: 'follow-up',
    title: 'Acompanhamento',
    leads: [],
    color: '#06b6d4'
  },
  {
    id: 'closing',
    title: 'Fechamento',
    leads: [],
    color: '#f97316'
  },
  {
    id: 'client-list',
    title: 'Lista de Clientes',
    leads: [],
    color: '#10b981'
  }
];

export const ARCHIVED_COLUMNS: KanbanColumn[] = [
  {
    id: 'prospect-refused',
    title: 'Prospecção Recusada',
    leads: [],
    color: '#ef4444'
  },
  {
    id: 'disqualified',
    title: 'Desqualificados',
    leads: [],
    color: '#64748b'
  }
];


export const MOCK_DASHBOARD_METRICS: DashboardMetrics = {
  totalLeads: 156,
  conversionRate: 23.5,
  monthlyLeads: 42,
  salesClosed: 18,
  funnelData: [
    { stage: 'À Prospectar', count: 25, percentage: 16.0 },
    { stage: 'Prospectados', count: 20, percentage: 12.8 },
    { stage: 'Follow-up', count: 18, percentage: 11.5 },
    { stage: 'Reunião Agendada', count: 15, percentage: 9.6 },
    { stage: 'Em Negociação', count: 12, percentage: 7.7 },
    { stage: 'Fechou a Venda', count: 18, percentage: 11.5 },
  ],
  categoryData: [
    { name: 'Em Progresso', value: 65, color: '#3b82f6' },
    { name: 'Vendas Fechadas', value: 18, color: '#22c55e' },
    { name: 'Desqualificados', value: 8, color: '#ef4444' },
    { name: 'Recusados', value: 5, color: '#64748b' },
  ],
  monthlyData: [
    { month: 'Out', leads: 28 },
    { month: 'Nov', leads: 35 },
    { month: 'Dez', leads: 41 },
    { month: 'Jan', leads: 42 },
  ]
};