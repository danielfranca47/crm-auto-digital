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
  lastMovement: Date;
  createdAt: Date;
  nextScheduledAction?: {
    date: Date;
    description: string;
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
  | 'to-prospect'
  | 'in-progress'        
  | 'prospected' 
  | 'prospect-refused'
  | 'disqualified'
  | 'follow-up'
  | 'meeting-scheduled'
  | 'no-show'
  | 'in-negotiation'
  | 'closed-sale'
  | 'client-list';

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