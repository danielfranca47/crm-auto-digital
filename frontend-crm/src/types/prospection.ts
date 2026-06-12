import { Lead, LeadStatus } from './crm';

export type ProspectionMethod = 'email' | 'whatsapp' | 'call';

export interface ProspectionTask {
  id: string;
  method: ProspectionMethod;
  completed: boolean;
  completedAt?: Date;
  automatedTask: boolean; // true for email/whatsapp, false for calls
}

export interface ProspectionLead extends Lead {
  prospectionTasks: ProspectionTask[];
  prospectionStatus: 'to-prospect' | 'in-progress' | 'qualification';
  prospectionStartedAt?: Date;
  prospectionCompletedAt?: Date;
}

export interface ProspectionColumn {
  id: 'to-prospect' | 'in-progress' | 'qualification';
  title: string;
  leads: ProspectionLead[];
  color: string;
}

export interface ProspectionBoardData {
  columns: ProspectionColumn[];
}