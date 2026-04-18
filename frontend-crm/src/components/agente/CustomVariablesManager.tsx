import React, { useState } from 'react';

interface CustomVariablesManagerProps {
  variables: Record<string, string>;
  onChange: (vars: Record<string, string>) => void;
}

/** Normaliza a chave: minúsculas, permite letras/dígitos/ponto/hífen/underscore */
function normalizeKey(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9._-]/g, '')
    .replace(/_{2,}/g, '_')
    .slice(0, 40);
}

export function CustomVariablesManager({
  variables,
  onChange,
}: CustomVariablesManagerProps) {
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [error, setError] = useState('');

  const entries = Object.entries(variables);

  function handleAdd() {
    const key = normalizeKey(newKey);
    if (!key) {
      setError('A chave não pode ser vazia.');
      return;
    }
    if (key in variables) {
      setError('Já existe uma variável com essa chave.');
      return;
    }
    setError('');
    onChange({ ...variables, [key]: newValue.trim() });
    setNewKey('');
    setNewValue('');
  }

  function handleUpdate(key: string) {
    onChange({ ...variables, [key]: editValue.trim() });
    setEditingKey(null);
    setEditValue('');
  }

  function handleDelete(key: string) {
    const updated = { ...variables };
    delete updated[key];
    onChange(updated);
    if (editingKey === key) {
      setEditingKey(null);
    }
  }

  function startEdit(key: string, currentValue: string) {
    setEditingKey(key);
    setEditValue(currentValue);
    setError('');
  }

  return (
    <div>
      {/* Lista de variáveis existentes */}
      {entries.length > 0 && (
        <div style={{ marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {entries.map(([key, val]) => (
            <div
              key={key}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 10px',
                background: 'var(--o-b1, rgba(255,255,255,0.04))',
                borderRadius: 6,
                border: '1px solid var(--o-b2, rgba(255,255,255,0.06))',
              }}
            >
              <code
                style={{
                  fontSize: 11,
                  padding: '2px 7px',
                  background: 'rgba(167,139,250,0.12)',
                  borderRadius: 4,
                  color: 'var(--o-purple, #a78bfa)',
                  flexShrink: 0,
                  fontFamily: 'monospace',
                  whiteSpace: 'nowrap',
                }}
              >
                {`{{${key}}}`}
              </code>

              {editingKey === key ? (
                <>
                  <input
                    className="o-input"
                    style={{ flex: 1, fontSize: 12, minWidth: 0 }}
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleUpdate(key);
                      if (e.key === 'Escape') setEditingKey(null);
                    }}
                    autoFocus
                  />
                  <button
                    className="o-btn-sm"
                    onClick={() => handleUpdate(key)}
                    style={{ flexShrink: 0 }}
                  >
                    Salvar
                  </button>
                  <button
                    className="o-btn-sm o-btn-ghost"
                    onClick={() => setEditingKey(null)}
                    style={{ flexShrink: 0 }}
                  >
                    ✕
                  </button>
                </>
              ) : (
                <>
                  <span
                    style={{
                      flex: 1,
                      fontSize: 12,
                      color: val ? 'var(--o-text, #e2e8f0)' : 'var(--o-sub, #888)',
                      fontStyle: val ? 'normal' : 'italic',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      minWidth: 0,
                    }}
                    title={val || '(vazio)'}
                  >
                    {val || '(vazio)'}
                  </span>
                  <button
                    className="o-btn-sm o-btn-ghost"
                    onClick={() => startEdit(key, val)}
                    style={{ flexShrink: 0, fontSize: 11 }}
                  >
                    Editar
                  </button>
                  <button
                    className="o-btn-sm o-btn-ghost"
                    onClick={() => handleDelete(key)}
                    style={{ flexShrink: 0, fontSize: 11, color: 'var(--o-red, #f87171)' }}
                  >
                    Remover
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {entries.length === 0 && (
        <p style={{ fontSize: 12, color: 'var(--o-sub, #888)', marginBottom: 12 }}>
          Nenhuma variável personalizada ainda. Adicione abaixo.
        </p>
      )}

      {/* Formulário de adição */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <div style={{ flex: '0 0 140px' }}>
            <input
              className="o-input"
              style={{ width: '100%', fontSize: 12 }}
              placeholder="chave (ex: link.cal)"
              value={newKey}
              onChange={(e) => {
                setNewKey(e.target.value);
                setError('');
              }}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <input
              className="o-input"
              style={{ width: '100%', fontSize: 12 }}
              placeholder="valor (ex: https://cal.com/...)"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            />
          </div>
          <button
            className="o-btn-sm"
            onClick={handleAdd}
            disabled={!newKey.trim()}
            style={{ flexShrink: 0 }}
          >
            Adicionar
          </button>
        </div>
        {error && (
          <p style={{ fontSize: 11, color: 'var(--o-red, #f87171)', margin: 0 }}>
            {error}
          </p>
        )}
        <p style={{ fontSize: 11, color: 'var(--o-sub, #888)', margin: 0 }}>
          Use a chave nos seus textos como{' '}
          <code
            style={{
              fontFamily: 'monospace',
              fontSize: 11,
              background: 'rgba(167,139,250,0.1)',
              padding: '0 4px',
              borderRadius: 3,
              color: 'var(--o-purple, #a78bfa)',
            }}
          >
            {newKey ? `{{${normalizeKey(newKey)}}}` : '{{sua.chave}}'}
          </code>
          . Digite{' '}
          <kbd
            style={{
              fontFamily: 'monospace',
              fontSize: 10,
              padding: '0 3px',
              borderRadius: 2,
              background: 'var(--o-b1)',
            }}
          >
            /
          </kbd>{' '}
          em qualquer campo de mensagem para inserir.
        </p>
      </div>
    </div>
  );
}
