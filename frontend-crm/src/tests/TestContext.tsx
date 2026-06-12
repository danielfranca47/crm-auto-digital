import React from 'react';
import { useLeads } from '@/contexts/LeadsContext';

const TestContext = () => {
  const {
    columns,
    archivedColumns,
    prospectionColumns
  } = useLeads();

  return (
    <div style={{ padding: '1rem' }}>
      <h2>🔍 Testando LeadsContext</h2>
      <p><strong>Colunas Kanban:</strong> {columns.length}</p>
      <p><strong>Colunas Arquivadas:</strong> {archivedColumns.length}</p>
      <p><strong>Colunas de Prospecção:</strong> {prospectionColumns.length}</p>
    </div>
  );
};

export default TestContext;
