import { useState, useEffect, useCallback } from 'react';
import { api, type BusinessInfoField } from '@/services/api';

// ─── Tipos ────────────────────────────────────────────────────
type HoursDay = {
  day: string;
  label: string;
  open: string;
  close: string;
  closed: boolean;
};

const DAYS_TEMPLATE: HoursDay[] = [
  { day: 'seg', label: 'Segunda',  open: '09:00', close: '18:00', closed: false },
  { day: 'ter', label: 'Terça',    open: '09:00', close: '18:00', closed: false },
  { day: 'qua', label: 'Quarta',   open: '09:00', close: '18:00', closed: false },
  { day: 'qui', label: 'Quinta',   open: '09:00', close: '18:00', closed: false },
  { day: 'sex', label: 'Sexta',    open: '09:00', close: '18:00', closed: false },
  { day: 'sab', label: 'Sábado',   open: '09:00', close: '13:00', closed: false },
  { day: 'dom', label: 'Domingo',  open: '09:00', close: '13:00', closed: true  },
];

function formatHoursPreview(days: HoursDay[]): string {
  const parts = days.map(d =>
    d.closed
      ? `${d.label}: Fechado`
      : `${d.label}: ${d.open.replace(':', 'h')}-${d.close.replace(':', 'h')}`
  );
  return parts.join(' · ');
}

function slugify(str: string): string {
  return str
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 64) || `custom_${Date.now()}`;
}

// ─── Estilos base ─────────────────────────────────────────────
const sectionStyle: React.CSSProperties = {
  marginBottom: 24,
};

const sectionHeaderStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: 1,
  textTransform: 'uppercase' as const,
  color: 'var(--o-sub)',
  marginBottom: 10,
  paddingBottom: 6,
  borderBottom: '1px solid var(--o-border)',
};

const fieldRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  marginBottom: 8,
};

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--o-sub)',
  width: 80,
  flexShrink: 0,
};

const inputStyle: React.CSSProperties = {
  flex: 1,
  background: 'var(--o-b1)',
  border: '1px solid var(--o-border)',
  borderRadius: 4,
  color: 'var(--o-text)',
  fontSize: 13,
  padding: '7px 10px',
  outline: 'none',
};

// ─── Campo simples com auto-save ──────────────────────────────
function SimpleField({
  label,
  value,
  inputType = 'text',
  placeholder,
  onSave,
  multiline = false,
}: {
  label: string;
  value: string;
  inputType?: string;
  placeholder?: string;
  onSave: (v: string) => Promise<void>;
  multiline?: boolean;
}) {
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);

  useEffect(() => { setDraft(value); }, [value]);

  async function commit() {
    if (draft === value) return;
    setSaving(true);
    try { await onSave(draft.trim()); } finally { setSaving(false); }
  }

  return (
    <div style={fieldRowStyle}>
      <span style={labelStyle}>{label}</span>
      {multiline ? (
        <textarea
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onBlur={commit}
          placeholder={placeholder}
          rows={2}
          style={{ ...inputStyle, resize: 'vertical' as const, fontFamily: 'inherit' }}
        />
      ) : (
        <input
          type={inputType}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); commit(); } }}
          placeholder={placeholder}
          style={{
            ...inputStyle,
            borderColor: saving ? 'var(--o-green)' : 'var(--o-border)',
          }}
        />
      )}
    </div>
  );
}

// ─── Horário estruturado ──────────────────────────────────────
function HoursEditor({
  value,
  onSave,
}: {
  value: string;
  onSave: (v: string) => Promise<void>;
}) {
  const [days, setDays] = useState<HoursDay[]>(() => {
    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed) && parsed.length === 7) return parsed;
    } catch { /* */ }
    return DAYS_TEMPLATE.map(d => ({ ...d }));
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed) && parsed.length === 7) setDays(parsed);
    } catch { /* */ }
  }, [value]);

  const save = useCallback(async (updated: HoursDay[]) => {
    setSaving(true);
    try { await onSave(JSON.stringify(updated)); } finally { setSaving(false); }
  }, [onSave]);

  function toggle(idx: number) {
    const next = days.map((d, i) => i === idx ? { ...d, closed: !d.closed } : d);
    setDays(next);
    save(next);
  }

  function setTime(idx: number, field: 'open' | 'close', v: string) {
    setDays(prev => prev.map((d, i) => i === idx ? { ...d, [field]: v } : d));
  }

  function commitTime() {
    save(days);
  }

  const preview = formatHoursPreview(days);

  return (
    <div>
      <div style={{ marginBottom: 10, overflowX: 'auto' as const }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' as const, fontSize: 13 }}>
          <tbody>
            {days.map((d, idx) => (
              <tr key={d.day} style={{ borderBottom: '1px solid var(--o-border)' }}>
                {/* Toggle dia */}
                <td style={{ padding: '7px 8px', width: 24 }}>
                  <button
                    onClick={() => toggle(idx)}
                    title={d.closed ? 'Marcar aberto' : 'Marcar fechado'}
                    style={{
                      width: 18, height: 18, borderRadius: 3, flexShrink: 0,
                      border: `1.5px solid ${!d.closed ? 'var(--o-green)' : 'var(--o-border)'}`,
                      background: !d.closed ? 'var(--o-green)' : 'transparent',
                      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >
                    {!d.closed && (
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                        <path d="M1.5 5L4 7.5L8.5 2.5" stroke="#000" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    )}
                  </button>
                </td>
                {/* Nome do dia */}
                <td style={{ padding: '7px 8px', width: 72, color: d.closed ? 'var(--o-sub)' : 'var(--o-text)', fontWeight: 500 }}>
                  {d.label}
                </td>
                {/* Status / horários */}
                {d.closed ? (
                  <td style={{ padding: '7px 8px', color: 'var(--o-sub)', fontStyle: 'italic', fontSize: 12 }} colSpan={3}>
                    Fechado
                  </td>
                ) : (
                  <>
                    <td style={{ padding: '7px 4px' }}>
                      <input
                        type="time"
                        value={d.open}
                        onChange={e => setTime(idx, 'open', e.target.value)}
                        onBlur={commitTime}
                        style={{ ...inputStyle, width: 90, padding: '5px 6px', flex: 'none' }}
                      />
                    </td>
                    <td style={{ padding: '7px 4px', color: 'var(--o-sub)', fontSize: 12, textAlign: 'center' as const }}>
                      até
                    </td>
                    <td style={{ padding: '7px 4px' }}>
                      <input
                        type="time"
                        value={d.close}
                        onChange={e => setTime(idx, 'close', e.target.value)}
                        onBlur={commitTime}
                        style={{ ...inputStyle, width: 90, padding: '5px 6px', flex: 'none' }}
                      />
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {saving && (
        <div style={{ fontSize: 11, color: 'var(--o-green)', marginBottom: 6 }}>Salvando...</div>
      )}
      <div style={{
        fontSize: 11, color: 'var(--o-sub)', background: 'var(--o-b1)',
        borderRadius: 4, padding: '5px 8px', lineHeight: 1.5,
      }}>
        {preview}
      </div>
    </div>
  );
}

// ─── Campo personalizado (row) ────────────────────────────────
function CustomFieldRow({
  field,
  onSave,
  onDelete,
}: {
  field: BusinessInfoField;
  onSave: (id: number, v: string) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}) {
  const [draft, setDraft] = useState(field.value ?? '');
  const [saving, setSaving] = useState(false);

  useEffect(() => { setDraft(field.value ?? ''); }, [field.value]);

  async function commit() {
    if (draft === (field.value ?? '')) return;
    setSaving(true);
    try { await onSave(field.id, draft.trim()); } finally { setSaving(false); }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <span style={{ ...labelStyle, width: 'auto', minWidth: 80, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
        {field.label}
      </span>
      <input
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); commit(); } }}
        placeholder="valor..."
        style={{ ...inputStyle, borderColor: saving ? 'var(--o-green)' : 'var(--o-border)' }}
      />
      <button
        onClick={() => onDelete(field.id)}
        title="Remover campo"
        style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: 13, padding: '2px 4px', flexShrink: 0 }}
      >
        ✕
      </button>
    </div>
  );
}

// ─── Modal de novo campo personalizado ───────────────────────
function AddCustomModal({ onClose, onAdd }: { onClose: () => void; onAdd: (label: string, value: string) => Promise<void> }) {
  const [label, setLabel] = useState('');
  const [value, setValue] = useState('');
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!label.trim()) return;
    setSaving(true);
    try { await onAdd(label.trim(), value.trim()); onClose(); } finally { setSaving(false); }
  }

  return (
    <div className="o-modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
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
            <label style={{ fontSize: 11, color: 'var(--o-sub)', textTransform: 'uppercase' as const, letterSpacing: 0.5, display: 'block', marginBottom: 6 }}>
              Nome do campo *
            </label>
            <input
              autoFocus
              value={label}
              onChange={e => setLabel(e.target.value)}
              placeholder="Ex: Link do Calendly, Cupom de desconto..."
              style={{ width: '100%', boxSizing: 'border-box' as const, ...inputStyle }}
              onKeyDown={e => e.key === 'Enter' && handleSave()}
            />
          </div>
          <div>
            <label style={{ fontSize: 11, color: 'var(--o-sub)', textTransform: 'uppercase' as const, letterSpacing: 0.5, display: 'block', marginBottom: 6 }}>
              Valor (opcional)
            </label>
            <input
              value={value}
              onChange={e => setValue(e.target.value)}
              placeholder="Preencha agora ou depois"
              style={{ width: '100%', boxSizing: 'border-box' as const, ...inputStyle }}
              onKeyDown={e => e.key === 'Enter' && handleSave()}
            />
          </div>
        </div>
        <div className="o-modal-footer">
          <button className="o-btn o-btn-primary" onClick={handleSave} disabled={!label.trim() || saving}>
            {saving ? 'Salvando...' : 'Adicionar campo'}
          </button>
          <button className="o-btn" onClick={onClose}>Cancelar</button>
        </div>
      </div>
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────
const DEFAULT_KEYS = new Set(['horario', 'telefone', 'email', 'website', 'endereco', 'instagram', 'facebook', 'youtube', 'whatsapp']);

export function BusinessInfo() {
  const [fields, setFields] = useState<BusinessInfoField[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showSocial, setShowSocial] = useState(false);

  useEffect(() => {
    api.crm.getBusinessInfo()
      .then(setFields)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  function getField(key: string): BusinessInfoField | undefined {
    return fields.find(f => f.field_key === key);
  }

  async function handleSaveField(key: string, value: string) {
    const f = getField(key);
    if (!f) return;
    const updated = await api.crm.updateBusinessInfoField(f.id, { value: value || null });
    setFields(prev => prev.map(x => x.id === f.id ? updated : x));
  }

  async function handleUpdateCustom(id: number, value: string) {
    const updated = await api.crm.updateBusinessInfoField(id, { value: value || null });
    setFields(prev => prev.map(x => x.id === id ? updated : x));
  }

  async function handleDeleteCustom(id: number) {
    await api.crm.deleteBusinessInfoField(id);
    setFields(prev => prev.filter(x => x.id !== id));
  }

  async function handleAddCustom(label: string, value: string) {
    const field_key = slugify(label);
    const created = await api.crm.createBusinessInfoField({ field_key, label, value: value || null });
    setFields(prev => [...prev, created]);
  }

  const customFields = fields.filter(f => !DEFAULT_KEYS.has(f.field_key));
  const filledCount = fields.filter(f => f.enabled && f.value && f.value.trim() !== '').length;

  const v = (key: string) => getField(key)?.value ?? '';

  if (loading) {
    return <div style={{ padding: '20px 0', color: 'var(--o-sub)', fontSize: 13, textAlign: 'center' }}>Carregando...</div>;
  }

  return (
    <div>
      {/* Cabeçalho */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 13, color: 'var(--o-sub)' }}>
          Informações disponíveis para o agente em qualquer fase do funil. Apenas campos preenchidos são injetados no prompt.
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

      {/* CONTATO */}
      <div style={sectionStyle}>
        <div style={sectionHeaderStyle}>Contato</div>
        <SimpleField
          label="Telefone"
          value={v('telefone')}
          inputType="tel"
          placeholder="+351 912 345 678"
          onSave={val => handleSaveField('telefone', val)}
        />
        <SimpleField
          label="E-mail"
          value={v('email')}
          inputType="email"
          placeholder="contato@exemplo.com"
          onSave={val => handleSaveField('email', val)}
        />
        <SimpleField
          label="Website"
          value={v('website')}
          inputType="url"
          placeholder="https://exemplo.com"
          onSave={val => handleSaveField('website', val)}
        />
        <SimpleField
          label="WhatsApp"
          value={v('whatsapp')}
          inputType="tel"
          placeholder="+351 912 345 678"
          onSave={val => handleSaveField('whatsapp', val)}
        />
      </div>

      {/* LOCALIZAÇÃO */}
      <div style={sectionStyle}>
        <div style={sectionHeaderStyle}>Localização</div>
        <SimpleField
          label="Endereço"
          value={v('endereco')}
          placeholder="Rua Exemplo, 123 — Cidade"
          onSave={val => handleSaveField('endereco', val)}
          multiline
        />
      </div>

      {/* HORÁRIO */}
      <div style={sectionStyle}>
        <div style={sectionHeaderStyle}>Horário de Funcionamento</div>
        <HoursEditor
          value={v('horario')}
          onSave={val => handleSaveField('horario', val)}
        />
      </div>

      {/* REDES SOCIAIS (colapsável) */}
      <div style={sectionStyle}>
        <button
          onClick={() => setShowSocial(s => !s)}
          style={{
            ...sectionHeaderStyle,
            background: 'none', border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 6,
            width: '100%', textAlign: 'left' as const, padding: 0,
          }}
        >
          <span style={{ fontSize: 10, opacity: 0.6 }}>{showSocial ? '▼' : '▶'}</span>
          Redes Sociais
        </button>
        {showSocial && (
          <div style={{ marginTop: 10 }}>
            <SimpleField label="Instagram" value={v('instagram')} placeholder="@usuario" onSave={val => handleSaveField('instagram', val)} />
            <SimpleField label="Facebook"  value={v('facebook')}  placeholder="facebook.com/pagina" onSave={val => handleSaveField('facebook', val)} />
            <SimpleField label="YouTube"   value={v('youtube')}   placeholder="youtube.com/@canal" onSave={val => handleSaveField('youtube', val)} />
          </div>
        )}
      </div>

      {/* CAMPOS PERSONALIZADOS */}
      <div style={sectionStyle}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', ...sectionHeaderStyle }}>
          <span>Campos Personalizados</span>
          <button
            onClick={() => setShowAddModal(true)}
            style={{
              fontSize: 11, padding: '3px 10px', borderRadius: 4,
              background: 'var(--o-b1)', border: '1px solid var(--o-border)',
              color: 'var(--o-sub)', cursor: 'pointer', textTransform: 'none' as const,
              letterSpacing: 0, fontWeight: 400,
            }}
          >
            + Adicionar
          </button>
        </div>
        {customFields.length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--o-sub)', fontStyle: 'italic', padding: '8px 0' }}>
            Nenhum campo personalizado.
          </div>
        ) : (
          customFields.map(f => (
            <CustomFieldRow
              key={f.id}
              field={f}
              onSave={handleUpdateCustom}
              onDelete={handleDeleteCustom}
            />
          ))
        )}
      </div>

      {showAddModal && (
        <AddCustomModal
          onClose={() => setShowAddModal(false)}
          onAdd={handleAddCustom}
        />
      )}
    </div>
  );
}
