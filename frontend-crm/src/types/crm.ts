export type AppointmentType = 'meeting' | 'call' | 'follow-up' | 'presentation';

export type AppointmentStatus = 'pending' | 'completed' | 'canceled';

export interface Appointment {
  id: string;
  leadId: string | null;
  title: string;
  description?: string;
  type: AppointmentType;
  status: AppointmentStatus;
  outcome?: 'completed' | 'no_show' | 'rescheduled';
  outcome_note?: string | null;
  outcome_at?: string | null;
  startTime: string;
  endTime?: string | null;
  leadName?: string | null;
  leadCompany?: string | null;
}

export interface CreateAppointmentPayload {
  leadId?: string | null;
  title: string;
  description?: string;
  type: AppointmentType;
  status?: AppointmentStatus;
  startTime: string;
  endTime?: string | null;
}

export type UpdateAppointmentPayload = Partial<CreateAppointmentPayload> & {
  status?: AppointmentStatus;
};

export interface Lead {
  id: string;
  companyName: string;
  contactName: string;
  phone: string;
  email: string;
  origin: string;
  category: LeadStatus;
  customMessage: string;
  observations: string;
  bot_disabled?: boolean;
  lastMovement: Date;
  createdAt: Date;
  nextScheduledAction?: {
    id?: string;
    date: Date;
    description: string;
    type?: AppointmentType;
  };
}

export interface LeadAppointment {
  id: string;
  leadId: string;
  description: string;
  startAt: Date;
  endAt?: Date | null;
  createdAt?: Date | null;
  updatedAt?: Date | null;
}

export type LeadStatus =
  | 'to-prospect'       // Prospecção
  | 'in-progress'       // (apenas na página de Prospecção)
  | 'qualification'     // Qualificação (substitui "prospected")
  | 'apresentation'     // Apresentação
  | 'follow-up'         // Acompanhamento
  | 'closing'           // Fechamento
  | 'client-list'       // lista de cliente
  | 'prospect-refused'  // Recusada (arquivados)
  | 'disqualified';     // Desqualificado (arquivados)

export interface KanbanColumn {
  id: LeadStatus;
  title: string;
  leads: Lead[];
  color: string;
}

export interface DashboardMetrics {
  totalLeads: number;
  conversionRate: number;
  monthlyLeads: number;
  salesClosed: number;
  funnelData: {
    stage: string;
    count: number;
    percentage: number;
  }[];
  categoryData: {
    name: string;
    value: number;
    color: string;
  }[];
  monthlyData: {
    month: string;
    leads: number;
  }[];
}

export interface NewLeadForm {
  companyName: string;
  contactName: string;
  phone: string;
  email?: string;
  origin: string;
  category: LeadStatus;
  customMessage?: string;
  observations: string;
}
