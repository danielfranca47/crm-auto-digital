import { useState, useEffect } from 'react';
import { api, type BusinessInfoField } from '@/services/api';

// ─── Ícones por field_key ─────────────────────────────────────
const FIELD_ICONS: Record<string, string> = {
  horario:   '🕐',
  telefone:  '📞',
  website:   '🌐',
  endereco:  '📍',
  instagram: '📸',
  facebook:  '👥',
  youtube:   '▶️',
  whatsapp:  '💬',
};

// ─── Helpers ──────────────────────────────────────────────────
function slugify(str: string): string {
  return str
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 64) || `custom_${Date.now()}`;
}

// ─── Row de edição inline ─────────────────────────────────────
function FieldRow({
  field,
  onUpdate,
  onClear,
  onDelete,
  isCustom,
}: {
  field: BusinessInfoField;
  onUpdate: (id: number, patch: { label?: string; value?: string | null; enabled?: number }) => Promise<void>;
  onClear: (id: number) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  isCustom: boolean;
}) {
  const [editingValue, setEditingValue] = useState(false);
  const [draft, setDraft] = useState(field.value ?? '');
  const [saving, setSaving] = useState(false);

  // sincroniza draft se field.value mudar externamente
  useEffect(() => { setDraft(field.value ?? ''); }, [field.value]);

  const icon = FIELD_ICONS[field.field_key] || '📌';
  const hasValue = field.value && field.value.trim() !== '';

  async function handleToggleEnabled() {
    await onUpdate(field.id, { enabled: field.enabled ? 0 : 1 });
  }

  async function handleSaveValue() {
    setSaving(true);
    try {
      const trimmed = draft.trim();
      if (trimmed === '') {
        await onClear(field.id);
      } else {
        await onUpdate(field.id, { value: trimmed });
      }
      setEditingValue(false);
    } finally {
      setSaving(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSaveValue(); }
    if (e.key === 'Escape') { setDraft(field.value ?? ''); setEditingValue(false); }
  }

  return (
    <div
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 10,
        padding: '10px 0',
        borderBottom: '1px solid var(--o-border)',
        opacity: field.enabled ? 1 : 0.45,
        transition: 'opacity 0.15s',
      }}
    >
      {/* Checkbox de enabled */}
      <button
        title={field.enabled ? 'Desativar campo' : 'Ativar campo'}
        onClick={handleToggleEnabled}
        style={{
          flexShrink: 0,
          width: 18, height: 18, borderRadius: 3,
          border: `1.5px solid ${field.enabled ? 'var(--o-green)' : 'var(--o-border)'}`,
          background: field.enabled ? 'var(--o-green)' : 'transparent',
          cursor: 'pointer', marginTop: 2,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        {field.enabled ? (
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M1.5 5L4 7.5L8.5 2.5" stroke="#000" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        ) : null}
      </button>

      {/* Ícone + label */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4 }}>
          <span style={{ fontSize: 13 }}>{icon}</span>
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--o-sub)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
            {field.label}
          </span>
        </div>

        {editingValue ? (
          <div style={{ display: 'flex', gap: 6, alignItems: 'flex-end' }}>
            <textarea
              autoFocus
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              placeholder="Digite o valor..."
              style={{
                flex: 1, background: 'var(--o-b1)', border: '1px solid var(--o-green)',
                borderRadius: 4, color: 'var(--o-text)', fontSize: 13,
                padding: '6px 8px', resize: 'vertical', outline: 'none',
                fontFamily: 'inherit',
              }}
            />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <button
                onClick={handleSaveValue}
                disabled={saving}
                style={{
                  padding: '5px 10px', borderRadius: 4, fontSize: 11,
                  background: 'var(--o-green)', color: '#000', border: 'none',
                  cursor: saving ? 'wait' : 'pointer', fontWeight: 600,
                }}
              >
                {saving ? '...' : 'OK'}
              </button>
              <button
                onClick={() => { setDraft(field.value ?? ''); setEditingValue(false); }}
                style={{
                  padding: '5px 10px', borderRadius: 4, fontSize: 11,
                  background: 'var(--o-b1)', color: 'var(--o-sub)', border: '1px solid var(--o-border)',
                  cursor: 'pointer',
                }}
              >
                ✕
              </button>
            </div>
          </div>
        ) : (
          <div
            onClick={() => setEditingValue(true)}
            style={{
              fontSize: 13, color: hasValue ? 'var(--o-text)' : 'var(--o-sub)',
              cursor: 'pointer', minHeight: 22,
              borderRadius: 4,
              padding: '4px 6px',
              background: 'var(--o-b1)',
              border: '1px solid transparent',
              transition: 'border-color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--o-border)')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'transparent')}
            title="Clique para editar"
          >
            {hasValue ? field.value : <span style={{ fontStyle: 'italic', opacity: 0.5 }}>não preenchido — clique para adicionar</span>}
          </div>
        )}
      </div>

      {/* Ações */}
      <div style={{ display: 'flex', gap: 4, flexShrink: 0, marginTop: 2 }}>
        {hasValue && !editingValue && (
          <button
            title="Limpar valor"
            onClick={() => onClear(field.id)}
            style={{
              background: 'none', border: 'none', color: 'var(--o-sub)',
              cursor: 'pointer', fontSize: 12, padding: '2px 4px', borderRadius: 3,
            }}
          >
            ✕
          </button>
        )}
        {isCustom && (
          <button
            title="Remover campo personalizado"
            onClick={() => onDelete(field.id)}
            style={{
              background: 'none', border: 'none', color: '#ef4444',
              cursor: 'pointer', fontSize: 12, padding: '2px 4px', borderRadius: 3,
            }}
          >
            🗑
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Modal de novo campo customizado ─────────────────────────
function AddCustomFieldModal({
  onClose,
  onAdd,
}: {
  onClose: () => void;
  onAdd: (label: string, value: string) => Promise<void>;
}) {
  const [label, setLabel] = useState('');
  const [value, setValue] = useState('');
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!label.trim()) return;
    setSaving(true);
    try {
      await onAdd(label.trim(), value.trim());
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="o-modal-overlay open"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="o-modal" style={{ maxWidth: 460 }}>
        <div className="o-modal-header">
          <div>
            <div className="font-display" style={{ fontSize: 20, fontWeight: 400, color: 'var(--o-text)' }}>
              Novo campo personalizado
            </div>
            <div style={{ fontSize: 12, color: 'var(--o-sub)', marginTop: 3 }}>
              Adicione qualquer informação relevante do seu negócio
            </div>
          </div>
          <button className="o-close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="o-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ fontSize: 11, color: 'var(--o-sub)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', marginBottom: 6 }}>
              Nome do campo *
            </label>
            <input
              autoFocus
              value={label}
              onChange={e => setLabel(e.target.value)}
              placeholder="Ex: Link do Calendly, Grupo WhatsApp, Cupom..."
              style={{
                width: '100%', boxSizing: 'border-box',
                background: 'var(--o-b1)', border: '1px solid var(--o-border)',
                borderRadius: 4, color: 'var(--o-text)', fontSize: 13, padding: '8px 10px',
                outline: 'none',
              }}
              onKeyDown={e => e.key === 'Enter' && handleSave()}
            />
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--o-sub)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', marginBottom: 6 }}>
              Valor (opcional)
            </label>
            <input
              value={value}
              onChange={e => setValue(e.target.value)}
              placeholder="Preencha agora ou depois"
              style={{
                width: '100%', boxSizing: 'border-box',
                background: 'var(--o-b1)', border: '1px solid var(--o-border)',
                borderRadius: 4, color: 'var(--o-text)', fontSize: 13, padding: '8px 10px',
                outline: 'none',
              }}
              onKeyDown={e => e.key === 'Enter' && handleSave()}
            />
          </div>
        </div>
        <div className="o-modal-footer">
          <button
            className="o-btn o-btn-primary"
            onClick={handleSave}
            disabled={!label.trim() || saving}
          >
            {saving ? 'Salvando...' : 'Adicionar campo'}
          </button>
          <button className="o-btn" onClick={onClose}>Cancelar</button>
        </div>
      </div>
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────
const DEFAULT_FIELD_KEYS = new Set([
  'horario', 'telefone', 'website', 'endereco',
  'instagram', 'facebook', 'youtube', 'whatsapp',
]);

export function BusinessInfo() {
  const [fields, setFields] = useState<BusinessInfoField[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  useEffect(() => {
    api.crm.getBusinessInfo()
      .then(setFields)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleUpdate(id: number, patch: { label?: string; value?: string | null; enabled?: number }) {
    const updated = await api.crm.updateBusinessInfoField(id, patch);
    setFields(f => f.map(x => x.id === id ? updated : x));
  }

  async function handleClear(id: number) {
    const updated = await api.crm.clearBusinessInfoField(id);
    setFields(f => f.map(x => x.id === id ? updated : x));
  }

  async function handleDelete(id: number) {
    await api.crm.deleteBusinessInfoField(id);
    setFields(f => f.filter(x => x.id !== id));
  }

  async function handleAddCustom(label: string, value: string) {
    const field_key = slugify(label);
    const created = await api.crm.createBusinessInfoField({ field_key, label, value: value || null });
    setFields(f => [...f, created]);
  }

  const filledCount = fields.filter(f => f.enabled && f.value && f.value.trim() !== '').length;

  if (loading) {
    return (
      <div style={{ padding: '20px 0', color: 'var(--o-sub)', fontSize: 13, textAlign: 'center' }}>
        Carregando...
      </div>
    );
  }

  return (
    <div>
      {/* Cabeçalho da seção */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 13, color: 'var(--o-sub)', marginTop: 4 }}>
            Informações disponíveis para o agente em qualquer fase do funil.
            Apenas campos preenchidos são injetados no prompt.
          </div>
          {filledCount > 0 && (
            <div style={{
              marginTop: 6, display: 'inline-flex', alignItems: 'center', gap: 5,
              fontSize: 11, color: 'var(--o-green)',
              background: 'rgba(74,222,128,0.08)', borderRadius: 4, padding: '2px 8px',
            }}>
              ✓ {filledCount} campo{filledCount !== 1 ? 's' : ''} ativo{filledCount !== 1 ? 's' : ''} no prompt
            </div>
          )}
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '7px 14px', borderRadius: 5,
            background: 'var(--o-b1)', border: '1px solid var(--o-border)',
            color: 'var(--o-sub)', cursor: 'pointer', fontSize: 12, flexShrink: 0,
          }}
        >
          + Campo personalizado
        </button>
      </div>

      {/* Lista de campos */}
      <div>
        {fields.map(field => (
          <FieldRow
            key={field.id}
            field={field}
            onUpdate={handleUpdate}
            onClear={handleClear}
            onDelete={handleDelete}
            isCustom={!DEFAULT_FIELD_KEYS.has(field.field_key)}
          />
        ))}
        {fields.length === 0 && (
          <div style={{ padding: '20px 0', color: 'var(--o-sub)', fontSize: 13, textAlign: 'center' }}>
            Nenhum campo encontrado.
          </div>
        )}
      </div>

      {showAddModal && (
        <AddCustomFieldModal
          onClose={() => setShowAddModal(false)}
          onAdd={handleAddCustom}
        />
      )}
    </div>
  );
}
