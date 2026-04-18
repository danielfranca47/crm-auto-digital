export interface VariableDef {
  key: string;
  label: string;
  category: 'system' | 'custom';
  description?: string;
  example?: string;
}

export const SYSTEM_VARIABLES: VariableDef[] = [
  {
    key: 'lead.nome',
    label: 'Nome do lead',
    category: 'system',
    description: 'Primeiro nome do lead no CRM',
    example: 'João Silva',
  },
  {
    key: 'lead.empresa',
    label: 'Empresa do lead',
    category: 'system',
    description: 'Nome da empresa do lead',
    example: 'Acme Corp',
  },
  {
    key: 'saudacao',
    label: 'Saudação temporal',
    category: 'system',
    description: 'Bom dia / Boa tarde / Boa noite conforme o horário',
    example: 'Boa tarde',
  },
  {
    key: 'agente.nome',
    label: 'Nome do agente',
    category: 'system',
    description: 'Nome configurado no perfil de IA',
    example: 'Sofia',
  },
  {
    key: 'negocio.nome',
    label: 'Nome do negócio',
    category: 'system',
    description: 'Nome da marca/negócio no perfil',
    example: 'Clínica Vida',
  },
  {
    key: 'negocio.local',
    label: 'Local de atendimento',
    category: 'system',
    description: 'Endereço nas informações do negócio',
    example: 'Rua das Flores, 100 – SP',
  },
  {
    key: 'negocio.horario',
    label: 'Horário de funcionamento',
    category: 'system',
    description: 'Horário nas informações do negócio',
    example: 'Seg–Sex 8h–18h',
  },
  {
    key: 'negocio.telefone',
    label: 'Telefone do negócio',
    category: 'system',
    description: 'Telefone nas informações do negócio',
    example: '(11) 99999-9999',
  },
  {
    key: 'reuniao.horario',
    label: 'Horário da reunião',
    category: 'system',
    description: 'Data e hora do próximo agendamento pendente',
    example: '15/06 às 14:00',
  },
  {
    key: 'reuniao.titulo',
    label: 'Título da reunião',
    category: 'system',
    description: 'Título do próximo agendamento pendente',
    example: 'Consulta inicial',
  },
];

export function buildVariableList(
  customVars: Record<string, string> = {}
): VariableDef[] {
  const custom: VariableDef[] = Object.entries(customVars).map(([key, value]) => ({
    key,
    label: key,
    category: 'custom' as const,
    description: value || undefined,
    example: value || undefined,
  }));
  return [...SYSTEM_VARIABLES, ...custom];
}
