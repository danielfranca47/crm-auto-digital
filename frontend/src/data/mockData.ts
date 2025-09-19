import { Lead, KanbanColumn, DashboardMetrics } from '../types/crm';

export const KANBAN_COLUMNS: KanbanColumn[] = [
  {
    id: 'to-prospect',
    title: 'À Prospectar',
    leads: [],
    color: '#6366f1'
  },
  {
    id: 'prospected',
    title: 'Prospectados',
    leads: [],
    color: '#3b82f6'
  },
  {
    id: 'follow-up',
    title: 'Follow-up',
    leads: [],
    color: '#f59e0b'
  },
  {
    id: 'meeting-scheduled',
    title: 'Reunião Agendada',
    leads: [],
    color: '#06b6d4'
  },
  {
    id: 'no-show',
    title: 'Não Compareceu',
    leads: [],
    color: '#ef4444'
  },
  {
    id: 'in-negotiation',
    title: 'Em Negociação',
    leads: [],
    color: '#f97316'
  },
  {
    id: 'closed-sale',
    title: 'Fechou a Venda',
    leads: [],
    color: '#22c55e'
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

export const MOCK_LEADS: Lead[] = [
  {
    id: '1',
    companyName: 'TechSolutions Lda',
    contactName: 'João Silva',
    phone: '+351 912 345 678',
    email: 'joao@techsolutions.pt',
    origin: 'Website',
    category: 'to-prospect',
    customMessage: 'Olá João, vimos seu interesse em nossos serviços premium.',
    observations: 'Interessado em serviços premium',
    lastMovement: new Date('2024-01-15'),
    createdAt: new Date('2024-01-10'),
    nextScheduledAction: {
      date: new Date('2024-01-20'),
      description: 'Ligar para apresentar proposta'
    }
  },
  {
    id: '2',
    companyName: 'Digital Consulting',
    contactName: 'Maria Santos',
    phone: '+351 923 456 789',
    email: 'maria@digitalconsulting.pt',
    origin: 'Indicação',
    category: 'prospected',
    customMessage: 'Oi Maria, fomos indicados pelo Pedro para conversar sobre consultoria.',
    observations: 'Empresa de tecnologia, busca consultoria',
    lastMovement: new Date('2024-01-14'),
    createdAt: new Date('2024-01-08')
  },
  {
    id: '3',
    companyName: 'InnovaCorp',
    contactName: 'Pedro Costa',
    phone: '+351 934 567 890',
    email: 'pedro@innovacorp.pt',
    origin: 'LinkedIn',
    category: 'meeting-scheduled',
    customMessage: 'Pedro, obrigado por aceitar nossa conexão no LinkedIn.',
    observations: 'Reunião marcada para próxima terça',
    lastMovement: new Date('2024-01-13'),
    createdAt: new Date('2024-01-05'),
    nextScheduledAction: {
      date: new Date('2024-01-16'),
      description: 'Reunião de apresentação às 14h'
    }
  },
  {
    id: '4',
    companyName: 'StartupX',
    contactName: 'Ana Oliveira',
    phone: '+351 945 678 901',
    email: 'ana@startupx.pt',
    origin: 'Facebook Ads',
    category: 'in-negotiation',
    customMessage: 'Ana, preparamos uma proposta especial para a StartupX.',
    observations: 'Negociando contrato anual',
    lastMovement: new Date('2024-01-12'),
    createdAt: new Date('2024-01-03')
  },
  {
    id: '5',
    companyName: 'GlobalTech',
    contactName: 'Carlos Pereira',
    phone: '+351 956 789 012',
    email: 'carlos@globaltech.pt',
    origin: 'Google Ads',
    category: 'closed-sale',
    customMessage: 'Carlos, parabéns pela decisão! Vamos começar na próxima semana.',
    observations: 'Venda fechada - contrato de 12 meses',
    lastMovement: new Date('2024-01-11'),
    createdAt: new Date('2024-01-01')
  },
  {
    id: '6',
    companyName: 'Future Systems',
    contactName: 'Sofia Rodrigues',
    phone: '+351 967 890 123',
    email: 'sofia@futuresystems.pt',
    origin: 'Website',
    category: 'follow-up',
    customMessage: 'Sofia, vamos agendar uma conversa para a próxima semana?',
    observations: 'Agendar nova conversa na próxima semana',
    lastMovement: new Date('2024-01-10'),
    createdAt: new Date('2023-12-28'),
    nextScheduledAction: {
      date: new Date('2024-01-18'),
      description: 'Follow-up por email'
    }
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