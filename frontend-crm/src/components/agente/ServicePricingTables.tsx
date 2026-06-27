import { useState } from 'react';
import { SuggestInput, SuggestTextarea } from './SuggestField';
import { api, type KnowledgeItem } from '@/services/api';
import { KNOWLEDGE_IMPORTANCE_LABELS, type KnowledgeCategory } from '@/types/agente';
import { ModalBase, PhaseTag, FunnelToggle } from './CamadaConhecimento';

// ─── Tipos e (de)serialização ──────────────────────────────────

export type ServicePricingRow = {
  id: string;
  nome: string;
  duracaoMinutos: number | null;
  preco: string;
  descricao: string;
};

export type ServicePricingTableContent = {
  format: 'structured_v1';
  rows: ServicePricingRow[];
};

function makeEmptyRow(): ServicePricingRow {
  return { id: Math.random().toString(36).slice(2), nome: '', duracaoMinutos: null, preco: '', descricao: '' };
}

/** Tenta interpretar content_text como tabela estruturada. Retorna null se for texto livre (legado ou inválido). */
export function parseServicePricingContent(contentText: string): ServicePricingTableContent | null {
  try {
    const parsed = JSON.parse(contentText);
    if (
      parsed && typeof parsed === 'object' &&
      parsed.format === 'structured_v1' &&
      Array.isArray(parsed.rows)
    ) {
      const rows: ServicePricingRow[] = (parsed.rows as unknown[]).map((raw) => {
        const r = raw as Record<string, unknown>;
        return {
          id: Math.random().toString(36).slice(2),
          nome: typeof r?.nome === 'string' ? r.nome : '',
          duracaoMinutos: typeof r?.duracaoMinutos === 'number' ? r.duracaoMinutos : null,
          preco: typeof r?.preco === 'string' ? r.preco : '',
          descricao: typeof r?.descricao === 'string' ? r.descricao : '',
        };
      });
      return { format: 'structured_v1', rows };
    }
  } catch {
    // não é JSON — texto livre legado
  }
  return null;
}

export function serializeServicePricingRows(rows: ServicePricingRow[]): string {
  return JSON.stringify({
    format: 'structured_v1',
    rows: rows
      .filter(r => r.nome.trim())
      .map(r => ({
        nome: r.nome.trim(),
        duracaoMinutos: r.duracaoMinutos,
        preco: r.preco.trim(),
        descricao: r.descricao.trim() || undefined,
      })),
  });
}

function previewText(item: KnowledgeItem): string {
  const parsed = parseServicePricingContent(item.content_text);
  if (!parsed) {
    return item.content_text.slice(0, 70) + (item.content_text.length > 70 ? '…' : '');
  }
  const n = parsed.rows.length;
  if (n === 0) return 'Nenhum serviço cadastrado ainda';
  const durations = parsed.rows.map(r => r.duracaoMinutos).filter((d): d is number => !!d);
  const range = durations.length
    ? (Math.min(...durations) === Math.max(...durations)
        ? `${Math.min(...durations)} min`
        : `${Math.min(...durations)}–${Math.max(...durations)} min`)
    : null;
  return `${n} serviço${n > 1 ? 's' : ''}${range ? ` · ${range}` : ''}`;
}

// ─── Editor de linha estruturada ────────────────────────────────

function ServiceRowEditor({ row, onChange, onRemove }: {
  row: ServicePricingRow;
  onChange: (next: ServicePricingRow) => void;
  onRemove: () => void;
}) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '2fr 90px 110px 2fr auto', gap: 8,
      alignItems: 'start', padding: '8px 10px', background: 'var(--o-bg)',
      border: '1px solid var(--o-b1)', borderRadius: 5, marginBottom: 8,
    }}>
      <div>
        <SuggestInput
          className="o-input"
          value={row.nome}
          onChange={e => onChange({ ...row, nome: e.target.value })}
          placeholder="Nome do serviço"
          maxLength={120}
        />
      </div>
      <div>
        <input
          type="number"
          className="o-input"
          value={row.duracaoMinutos ?? ''}
          onChange={e => onChange({ ...row, duracaoMinutos: e.target.value ? Number(e.target.value) : null })}
          placeholder="Min"
          min={1}
        />
      </div>
      <div>
        <SuggestInput
          className="o-input"
          value={row.preco}
          onChange={e => onChange({ ...row, preco: e.target.value })}
          placeholder="Preço"
          maxLength={40}
        />
      </div>
      <div>
        <SuggestInput
          className="o-input"
          value={row.descricao}
          onChange={e => onChange({ ...row, descricao: e.target.value })}
          placeholder="Descrição (opcional)"
          maxLength={200}
        />
      </div>
      <button
        className="o-btn"
        style={{ fontSize: 11, padding: '3px 8px', color: 'var(--o-hot)' }}
        onClick={onRemove}
        title="Remover serviço"
      >
        ✕
      </button>
    </div>
  );
}

// ─── Modal: criar/editar uma tabela ─────────────────────────────

export function ModalServiceTable({
  category, existingItem, onClose, onSaved,
}: {
  category: KnowledgeCategory;
  existingItem: KnowledgeItem | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const parsedExisting = existingItem ? parseServicePricingContent(existingItem.content_text) : null;

  const [title, setTitle] = useState(existingItem?.title ?? '');
  const [mode, setMode] = useState<'structured' | 'freeform'>(
    existingItem ? (parsedExisting ? 'structured' : 'freeform') : 'structured'
  );
  const [rows, setRows] = useState<ServicePricingRow[]>(
    parsedExisting?.rows.length ? parsedExisting.rows : [makeEmptyRow()]
  );
  const [freeformContent, setFreeformContent] = useState(
    !parsedExisting ? (existingItem?.content_text ?? '') : ''
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateRow(id: string, next: ServicePricingRow) {
    setRows(prev => prev.map(r => (r.id === id ? next : r)));
  }
  function removeRow(id: string) {
    setRows(prev => prev.filter(r => r.id !== id));
  }
  function addRow() {
    setRows(prev => [...prev, makeEmptyRow()]);
  }

  async function handleSave() {
    if (!title.trim()) {
      setError('Dê um nome a esta tabela (ex.: "Ana — Hipnoterapia").');
      return;
    }
    let contentText: string;
    if (mode === 'structured') {
      if (!rows.some(r => r.nome.trim())) {
        setError('Adicione pelo menos um serviço com nome.');
        return;
      }
      contentText = serializeServicePricingRows(rows);
    } else {
      if (!freeformContent.trim() || freeformContent.trim().length < 20) {
        setError('O conteúdo deve ter pelo menos 20 caracteres.');
        return;
      }
      contentText = freeformContent.trim();
    }

    setSaving(true);
    setError(null);
    try {
      if (existingItem) {
        await api.crm.updateKnowledge(existingItem.id, {
          title: title.trim(),
          content_text: contentText,
          category: category.key,
        });
      } else {
        await api.crm.createKnowledgeManual({
          title: title.trim(),
          content_text: contentText,
          category: category.key,
        });
      }
      onSaved();
    } catch {
      setError('Erro ao salvar. Tente novamente.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <ModalBase
      title={existingItem ? `Editar tabela: ${existingItem.title}` : 'Nova tabela de serviços'}
      sub={category.description}
      onClose={onClose}
      onSave={handleSave}
      saveLabel={saving ? 'Salvando…' : existingItem ? 'Salvar alterações' : 'Adicionar tabela'}
      wide
    >
      <div className="o-field">
        <label className="o-field-label">Nome da tabela</label>
        <SuggestInput
          className="o-input"
          value={title}
          onChange={e => setTitle(e.target.value)}
          maxLength={120}
          placeholder='Ex.: "Ana — Hipnoterapia", "Pacotes de massagem"…'
        />
        <div className="o-char-count">{title.length}/120</div>
      </div>

      <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid var(--o-b1)' }}>
        {[
          { key: 'structured' as const, label: 'Tabela estruturada' },
          { key: 'freeform' as const, label: 'Texto livre' },
        ].map(t => (
          <button
            key={t.key}
            className={`o-btn${mode === t.key ? ' o-btn-primary' : ''}`}
            style={{ borderRadius: 0, borderBottom: mode === t.key ? '2px solid var(--o-active)' : '2px solid transparent', marginBottom: -1 }}
            onClick={() => setMode(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {mode === 'structured' ? (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 90px 110px 2fr auto', gap: 8, padding: '0 10px', marginBottom: 4 }}>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 1.5, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Serviço</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 1.5, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Duração</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 1.5, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Preço</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 1.5, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Descrição</span>
            <span />
          </div>
          {rows.map(row => (
            <ServiceRowEditor
              key={row.id}
              row={row}
              onChange={next => updateRow(row.id, next)}
              onRemove={() => removeRow(row.id)}
            />
          ))}
          <button className="o-btn" style={{ fontSize: 11, padding: '4px 10px' }} onClick={addRow}>
            + Adicionar serviço
          </button>
        </div>
      ) : (
        <div className="o-field">
          <label className="o-field-label">Conteúdo</label>
          <SuggestTextarea
            className="o-textarea"
            style={{ minHeight: 200 }}
            value={freeformContent}
            onChange={e => setFreeformContent(e.target.value)}
            placeholder={category.placeholder}
          />
        </div>
      )}

      {error && <div style={{ fontSize: 12, color: 'var(--o-hot)', marginTop: 8 }}>{error}</div>}
    </ModalBase>
  );
}

// ─── Secção: cabeçalho da categoria + lista de tabelas ──────────

export function GuidedMultiTableSection({
  category, items, onAdd, onEdit, onDelete, onToggleActive, activeOverrides, deletingId, togglingId,
}: {
  category: KnowledgeCategory;
  items: KnowledgeItem[];
  onAdd: () => void;
  onEdit: (item: KnowledgeItem) => void;
  onDelete: (item: KnowledgeItem) => void;
  onToggleActive: (item: KnowledgeItem) => void;
  activeOverrides: Map<number, boolean>;
  deletingId: number | null;
  togglingId: number | null;
}) {
  const isCritical = category.importance === 'critical';
  const hasTables = items.length > 0;
  const importanceColor = isCritical ? (hasTables ? 'var(--o-active)' : 'var(--o-hot)') : 'var(--o-dim)';
  const importanceBorder = isCritical ? (hasTables ? 'var(--o-active-b)' : 'var(--o-hot-b)') : 'var(--o-b1)';

  return (
    <div style={{
      padding: '12px 14px', background: 'var(--o-b0)', borderRadius: 4,
      border: `1px solid ${hasTables ? 'var(--o-b1)' : (isCritical ? 'var(--o-hot-b)' : 'var(--o-b1)')}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: hasTables ? 10 : 0 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, color: 'var(--o-text)', fontWeight: 500 }}>{category.label}</span>
            <span
              className="font-mono-orion"
              style={{
                fontSize: 7, letterSpacing: 1.5, textTransform: 'uppercase', padding: '1px 5px',
                borderRadius: 2, border: `1px solid ${importanceBorder}`, color: importanceColor, flexShrink: 0,
              }}
            >
              {KNOWLEDGE_IMPORTANCE_LABELS[category.importance]}
            </span>
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--o-sub)', fontWeight: 300 }}>
            {hasTables ? `${items.length} tabela${items.length > 1 ? 's' : ''} cadastrada${items.length > 1 ? 's' : ''}` : category.description}
          </div>
          {!hasTables && category.when_used && (
            <div style={{ marginTop: 5 }}>
              <PhaseTag phase={category.when_used} />
            </div>
          )}
        </div>
        <button className="o-btn o-btn-primary" style={{ fontSize: 11, padding: '3px 10px', flexShrink: 0 }} onClick={onAdd}>
          + Adicionar tabela
        </button>
      </div>

      {hasTables && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {items.map(item => {
            const isActive = activeOverrides.has(item.id) ? activeOverrides.get(item.id)! : item.active_in_funnel !== 0;
            return (
              <div
                key={item.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px',
                  background: 'var(--o-bg)', border: '1px solid var(--o-b1)', borderRadius: 5,
                  opacity: isActive ? 1 : 0.6, transition: 'opacity 0.2s',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, color: 'var(--o-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {item.title}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {previewText(item)}
                  </div>
                </div>
                <FunnelToggle active={isActive} onChange={() => onToggleActive(item)} disabled={togglingId === item.id} />
                <button className="o-btn" style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => onEdit(item)}>Editar</button>
                <button
                  className="o-btn"
                  style={{ fontSize: 11, padding: '3px 8px', color: 'var(--o-hot)' }}
                  onClick={() => onDelete(item)}
                  disabled={deletingId === item.id}
                >
                  {deletingId === item.id ? '…' : '✕'}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
