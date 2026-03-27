import { useState, useEffect, useRef } from 'react';
import { api, type KnowledgeItem } from '@/services/api';
import {
  KNOWLEDGE_CATEGORIES_BY_TEMPLATE,
  KNOWLEDGE_IMPORTANCE_LABELS,
  type KnowledgeCategory,
  type AgentConfig,
} from '@/types/agente';

// ─── Modal base (shared) ──────────────────────────────────────
function ModalBase({ title, sub, onClose, onSave, children, saveLabel = 'Salvar' }: {
  title: string; sub: string; onClose: () => void; onSave?: () => void; children: React.ReactNode; saveLabel?: string;
}) {
  return (
    <div className="o-modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="o-modal" style={{ maxWidth: 620 }}>
        <div className="o-modal-header">
          <div>
            <div className="font-display" style={{ fontSize: 22, fontWeight: 400, color: 'var(--o-text)' }}>{title}</div>
            <div style={{ fontSize: 12, color: 'var(--o-sub)', fontWeight: 300, marginTop: 3 }}>{sub}</div>
          </div>
          <button className="o-close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="o-modal-body">{children}</div>
        <div className="o-modal-footer">
          {onSave && <button className="o-btn o-btn-primary" onClick={onSave}>{saveLabel}</button>}
          <button className="o-btn" onClick={onClose}>{onSave ? 'Cancelar' : 'Fechar'}</button>
        </div>
      </div>
    </div>
  );
}

// ─── Modal: Preencher seção guiada ───────────────────────────
function ModalGuided({
  category, existingItem, onClose, onSaved,
}: {
  category: KnowledgeCategory;
  existingItem: KnowledgeItem | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle]     = useState(existingItem?.title ?? category.label);
  const [content, setContent] = useState(existingItem?.content_text ?? '');
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function handleSave() {
    if (!content.trim() || content.trim().length < 20) {
      setError('O conteúdo deve ter pelo menos 20 caracteres.');
      return;
    }
    setSaving(true);
    try {
      if (existingItem) {
        await api.crm.updateKnowledge(existingItem.id, {
          title: title.trim(),
          content_text: content.trim(),
          category: category.key,
        });
      } else {
        await api.crm.createKnowledgeManual({
          title: title.trim(),
          content_text: content.trim(),
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
      title={existingItem ? `Editar: ${category.label}` : category.label}
      sub={category.description}
      onClose={onClose}
      onSave={handleSave}
      saveLabel={saving ? 'Salvando…' : existingItem ? 'Salvar alterações' : 'Adicionar'}
    >
      {/* Hint */}
      <div style={{
        background: 'var(--o-b0)', border: '1px solid var(--o-b1)', borderRadius: 4,
        padding: '10px 14px', marginBottom: 16, fontSize: 12.5, color: 'var(--o-sub)',
        lineHeight: 1.6,
      }}>
        <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', display: 'block', marginBottom: 4 }}>
          O que preencher
        </span>
        {category.hint}
      </div>

      <div className="o-field">
        <label className="o-field-label">Título</label>
        <input
          className="o-input"
          value={title}
          onChange={e => setTitle(e.target.value)}
          maxLength={120}
        />
        <div className="o-char-count">{title.length}/120</div>
      </div>

      <div className="o-field">
        <label className="o-field-label">Conteúdo</label>
        <textarea
          className="o-textarea"
          style={{ minHeight: 220 }}
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder={category.placeholder}
        />
      </div>

      {error && <div style={{ fontSize: 12, color: 'var(--o-hot)', marginTop: 4 }}>{error}</div>}
    </ModalBase>
  );
}

// ─── Modal: Adicionar conteúdo extra (livre / upload) ────────
function ModalAddExtra({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [tab, setTab]         = useState<'text' | 'file'>('text');
  const [title, setTitle]     = useState('');
  const [content, setContent] = useState('');
  const [file, setFile]       = useState<File | null>(null);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleSave() {
    if (tab === 'text') {
      if (!title.trim() || !content.trim()) { setError('Título e conteúdo são obrigatórios.'); return; }
      setSaving(true);
      try {
        await api.crm.createKnowledgeManual({ title: title.trim(), content_text: content.trim() });
        onAdded();
      } catch {
        setError('Erro ao salvar. Tente novamente.');
      } finally { setSaving(false); }
    } else {
      if (!file) { setError('Selecione um arquivo.'); return; }
      setSaving(true);
      try {
        await api.crm.uploadKnowledgeFile(file);
        onAdded();
      } catch {
        setError('Erro ao enviar arquivo. Tente novamente.');
      } finally { setSaving(false); }
    }
  }

  return (
    <ModalBase
      title="Adicionar conteúdo extra"
      sub="Texto livre ou upload de arquivo para complementar a base de conhecimento"
      onClose={onClose}
      onSave={handleSave}
      saveLabel={saving ? 'Salvando…' : 'Adicionar'}
    >
      <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid var(--o-b1)' }}>
        {(['text', 'file'] as const).map(t => (
          <button
            key={t}
            className={`o-btn${tab === t ? ' o-btn-primary' : ''}`}
            style={{ borderRadius: 0, borderBottom: tab === t ? '2px solid var(--o-active)' : '2px solid transparent', marginBottom: -1 }}
            onClick={() => setTab(t)}
          >
            {t === 'text' ? 'Texto livre' : 'Upload (.txt/.csv/.xlsx)'}
          </button>
        ))}
      </div>

      {tab === 'text' && (
        <>
          <div className="o-field">
            <label className="o-field-label">Título</label>
            <input className="o-input" value={title} onChange={e => setTitle(e.target.value)} maxLength={120}
              placeholder="Ex: Política de preços, FAQ, Script de vendas…" />
            <div className="o-char-count">{title.length}/120</div>
          </div>
          <div className="o-field">
            <label className="o-field-label">Conteúdo</label>
            <textarea className="o-textarea" style={{ minHeight: 180 }} value={content}
              onChange={e => setContent(e.target.value)}
              placeholder="Cole ou escreva o conteúdo que o agente deve saber…" />
          </div>
        </>
      )}

      {tab === 'file' && (
        <div className="o-field">
          <label className="o-field-label">Arquivo</label>
          <div className="o-field-hint">Formatos aceitos: .txt, .csv, .xlsx. Tamanho máximo: 5 MB.</div>
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.csv,.xlsx"
            style={{ display: 'none' }}
            onChange={e => setFile(e.target.files?.[0] ?? null)}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
            <button className="o-btn" onClick={() => fileRef.current?.click()}>Selecionar arquivo</button>
            {file && <span style={{ fontSize: 12, color: 'var(--o-sub)' }}>{file.name}</span>}
          </div>
        </div>
      )}

      {error && <div style={{ fontSize: 12, color: 'var(--o-hot)', marginTop: 8 }}>{error}</div>}
    </ModalBase>
  );
}

// ─── Modal: Ver conteúdo ──────────────────────────────────────
function ModalView({ item, onClose }: { item: KnowledgeItem; onClose: () => void }) {
  return (
    <ModalBase
      title={item.title}
      sub={`Tipo: ${item.source_type === 'manual' ? 'Texto' : 'Arquivo'} · Atualizado: ${new Date(item.updated_at).toLocaleDateString('pt-BR')}`}
      onClose={onClose}
    >
      <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: 'var(--o-text)', lineHeight: 1.6, maxHeight: 400, overflowY: 'auto', padding: '0 4px' }}>
        {item.content_text || 'Sem conteúdo.'}
      </div>
    </ModalBase>
  );
}

// ─── Modal: Editar item extra (sem categoria guiada) ──────────
function ModalEditExtra({ item, onClose, onSaved }: { item: KnowledgeItem; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle]     = useState(item.title);
  const [content, setContent] = useState(item.content_text);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function handleSave() {
    if (!title.trim()) { setError('Título é obrigatório.'); return; }
    setSaving(true);
    try {
      await api.crm.updateKnowledge(item.id, { title: title.trim(), content_text: content.trim() });
      onSaved();
    } catch {
      setError('Erro ao salvar. Tente novamente.');
    } finally { setSaving(false); }
  }

  return (
    <ModalBase title="Editar conteúdo" sub={`Editando: ${item.title}`} onClose={onClose} onSave={handleSave}
      saveLabel={saving ? 'Salvando…' : 'Salvar'}>
      <div className="o-field">
        <label className="o-field-label">Título</label>
        <input className="o-input" value={title} onChange={e => setTitle(e.target.value)} maxLength={120} />
        <div className="o-char-count">{title.length}/120</div>
      </div>
      <div className="o-field">
        <label className="o-field-label">Conteúdo</label>
        <textarea className="o-textarea" style={{ minHeight: 200 }} value={content} onChange={e => setContent(e.target.value)} />
      </div>
      {error && <div style={{ fontSize: 12, color: 'var(--o-hot)', marginTop: 8 }}>{error}</div>}
    </ModalBase>
  );
}

// ─── Funções utilitárias ──────────────────────────────────────

function getPersonalizedCategory(
  cat: KnowledgeCategory,
  config: Partial<AgentConfig>,
): KnowledgeCategory {
  const niche    = config.niche            || '[nicho do negócio]';
  const audience = config.target_audience  || '[público-alvo]';
  const offer    = config.offer_description || '[descrição da oferta]';
  return {
    ...cat,
    hint: cat.hint
      .replace(/\[NICHO\]/g, niche)
      .replace(/\[PÚBLICO\]/g, audience)
      .replace(/\[OFERTA\]/g, offer),
    placeholder: cat.placeholder
      .replace(/\[NICHO\]/g, niche)
      .replace(/\[PÚBLICO\]/g, audience)
      .replace(/\[OFERTA\]/g, offer),
  };
}

const STALE_KEYS = new Set(['urgency_offer', 'cart_recovery_scripts']);

function isStale(item: KnowledgeItem, days = 30): boolean {
  const updated = new Date(item.updated_at);
  const now = new Date();
  return (now.getTime() - updated.getTime()) / (1000 * 60 * 60 * 24) > days;
}

function getReadinessLevel(
  guidedCategories: KnowledgeCategory[],
  itemByCategory: Map<string, KnowledgeItem>,
): 'none' | 'basic' | 'optimized' {
  const critical = guidedCategories.filter(c => c.importance === 'critical');
  const recommended = guidedCategories.filter(c => c.importance === 'recommended');
  const criticalFilled = critical.filter(c => itemByCategory.has(c.key)).length;
  const recommendedFilled = recommended.filter(c => itemByCategory.has(c.key)).length;

  if (criticalFilled < 2) return 'none';
  if (criticalFilled < critical.length) return 'basic';
  if (recommendedFilled >= 2) return 'optimized';
  return 'basic';
}

const READINESS_CONFIG = {
  none: {
    color: 'var(--o-hot)',
    borderColor: 'var(--o-hot-b)',
    dot: 'var(--o-hot)',
    label: 'Não funcional',
    message: 'O agente não tem informações suficientes para responder bem.',
  },
  basic: {
    color: '#d97706',
    borderColor: '#92400e44',
    dot: '#d97706',
    label: 'Funcional básico',
    message: 'O agente consegue operar, mas sem diferenciação.',
  },
  optimized: {
    color: 'var(--o-active)',
    borderColor: 'var(--o-active-b)',
    dot: 'var(--o-active)',
    label: 'Otimizado',
    message: 'O agente está pronto para operar com alta performance.',
  },
} as const;

// ─── Card de seção guiada ─────────────────────────────────────
function GuidedSectionCard({
  category,
  item,
  onFill,
  onView,
  onDelete,
  deleting,
}: {
  category: KnowledgeCategory;
  item: KnowledgeItem | null;
  onFill: () => void;
  onView: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  const filled = !!item;
  const isCritical = category.importance === 'critical';
  const importanceColor = isCritical
    ? (filled ? 'var(--o-active)' : 'var(--o-hot)')
    : 'var(--o-dim)';
  const importanceBorder = isCritical
    ? (filled ? 'var(--o-active-b)' : 'var(--o-hot-b)')
    : 'var(--o-b1)';

  const showStaleBadge = filled && item && STALE_KEYS.has(category.key) && isStale(item);

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr auto',
      gap: 12,
      padding: '12px 14px',
      background: 'var(--o-b0)',
      borderRadius: 4,
      border: `1px solid ${filled ? 'var(--o-b1)' : (isCritical ? 'var(--o-hot-b)' : 'var(--o-b1)')}`,
      alignItems: 'center',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
        {/* Status dot */}
        <div style={{
          width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
          background: filled ? 'var(--o-active)' : (isCritical ? 'var(--o-hot)' : 'var(--o-b2)'),
        }} />
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
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
            {showStaleBadge && (
              <span
                className="font-mono-orion"
                style={{
                  fontSize: 7, letterSpacing: 1.5, textTransform: 'uppercase', padding: '1px 5px',
                  borderRadius: 2, border: '1px solid var(--o-hot-b)', color: 'var(--o-hot)',
                  flexShrink: 0,
                }}
                title="Este conteúdo tem mais de 30 dias sem atualização"
              >
                Atualizar
              </span>
            )}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--o-sub)', fontWeight: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {filled
              ? item!.content_text.slice(0, 80) + (item!.content_text.length > 80 ? '…' : '')
              : category.description}
          </div>
        </div>
      </div>

      {/* Ações */}
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        {filled ? (
          <>
            <button className="o-btn" style={{ fontSize: 11, padding: '3px 8px' }} onClick={onView}>Ver</button>
            <button className="o-btn" style={{ fontSize: 11, padding: '3px 8px' }} onClick={onFill}>Editar</button>
            <button
              className="o-btn"
              style={{ fontSize: 11, padding: '3px 8px', color: 'var(--o-hot)' }}
              onClick={onDelete}
              disabled={deleting}
            >
              {deleting ? '…' : '✕'}
            </button>
          </>
        ) : (
          <button className="o-btn o-btn-primary" style={{ fontSize: 11, padding: '3px 10px' }} onClick={onFill}>
            Preencher →
          </button>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────

export function CamadaConhecimento({
  templateKey,
  agentConfig,
}: {
  templateKey?: string;
  agentConfig?: Partial<AgentConfig>;
}) {
  const [items, setItems]             = useState<KnowledgeItem[]>([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [deleting, setDeleting]       = useState<number | null>(null);

  // Modais
  const [guidedModal, setGuidedModal] = useState<KnowledgeCategory | null>(null);
  const [modalAddExtra, setModalAddExtra] = useState(false);
  const [viewItem, setViewItem]       = useState<KnowledgeItem | null>(null);
  const [editExtra, setEditExtra]     = useState<KnowledgeItem | null>(null);

  // Categorias guiadas baseadas no template do agente, com hints/placeholders personalizados
  const guidedCategories: KnowledgeCategory[] = (
    (templateKey && KNOWLEDGE_CATEGORIES_BY_TEMPLATE[templateKey]) || []
  ).map(cat => getPersonalizedCategory(cat, agentConfig ?? {}));

  // Mapa de category → item existente
  const itemByCategory = new Map<string, KnowledgeItem>();
  for (const item of items) {
    if (item.category) itemByCategory.set(item.category, item);
  }

  // Itens "extras" — sem categoria guiada (ou com categoria desconhecida)
  const guidedCategoryKeys = new Set(guidedCategories.map(c => c.key));
  const extraItems = items.filter(i => !i.category || !guidedCategoryKeys.has(i.category));

  // Score de prontidão
  const readinessLevel = getReadinessLevel(guidedCategories, itemByCategory);
  const readiness = READINESS_CONFIG[readinessLevel];

  async function load() {
    setLoading(true);
    try {
      const data = await api.crm.getKnowledgeList();
      setItems(data);
      setError(null);
    } catch {
      setError('Não foi possível carregar a base de conhecimento.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleDelete(id: number) {
    if (!window.confirm('Remover este item da base de conhecimento?')) return;
    setDeleting(id);
    try {
      await api.crm.deleteKnowledge(id);
      setItems(prev => prev.filter(i => i.id !== id));
    } catch {
      alert('Erro ao remover. Tente novamente.');
    } finally {
      setDeleting(null);
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <span className="font-mono-orion" style={{ fontSize: 10, color: 'var(--o-dim)' }}>Carregando…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="o-alert o-alert-danger">
        <span>⚠</span>
        <span>{error}</span>
      </div>
    );
  }

  return (
    <>
      {/* ── Seções guiadas ───────────────────────────────────── */}
      {guidedCategories.length > 0 && (
        <>
          {/* Score de prontidão */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 14px', marginBottom: 16,
            background: 'var(--o-b0)', borderRadius: 4,
            border: `1px solid ${readiness.borderColor}`,
          }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: readiness.dot }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 1.5, textTransform: 'uppercase', color: readiness.color }}>
                {readiness.label}
              </span>
              <div style={{ fontSize: 11.5, color: 'var(--o-sub)', fontWeight: 300, marginTop: 2 }}>
                {readiness.message}
              </div>
            </div>
          </div>

          <div className="o-section-hdr" style={{ marginBottom: 12 }}>
            <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
              Seções sugeridas para este agente
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 32 }}>
            {guidedCategories.map(cat => (
              <GuidedSectionCard
                key={cat.key}
                category={cat}
                item={itemByCategory.get(cat.key) ?? null}
                onFill={() => setGuidedModal(cat)}
                onView={() => setViewItem(itemByCategory.get(cat.key) ?? null)}
                onDelete={() => {
                  const it = itemByCategory.get(cat.key);
                  if (it) handleDelete(it.id);
                }}
                deleting={deleting === (itemByCategory.get(cat.key)?.id ?? -1)}
              />
            ))}
          </div>
        </>
      )}

      {/* ── Conteúdo adicional ───────────────────────────────── */}
      <div className="o-section-hdr" style={{ marginBottom: 12 }}>
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Conteúdo adicional
        </span>
        <span className="font-mono-orion" style={{ fontSize: 8, color: 'var(--o-dim)', border: '1px solid var(--o-b1)', padding: '1px 6px', borderRadius: 2 }}>
          {extraItems.length} item(s)
        </span>
      </div>

      <div style={{ fontSize: 12.5, color: 'var(--o-sub)', marginBottom: 14, fontWeight: 300 }}>
        FAQs, scripts, políticas ou catálogos adicionais que o agente pode consultar.
      </div>

      <button className="o-btn o-btn-primary" style={{ marginBottom: 16 }} onClick={() => setModalAddExtra(true)}>
        + Adicionar conteúdo extra
      </button>

      {extraItems.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px 120px 130px', gap: 12, padding: '4px 12px' }}>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Título</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Tipo</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Atualizado</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Ações</span>
          </div>
          {extraItems.map(item => (
            <div
              key={item.id}
              style={{
                display: 'grid', gridTemplateColumns: '1fr 100px 120px 130px', gap: 12,
                padding: '10px 12px', background: 'var(--o-b0)', borderRadius: 4,
                border: '1px solid var(--o-b1)', alignItems: 'center',
              }}
            >
              <div style={{ fontSize: 13, color: 'var(--o-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {item.title}
              </div>
              <span className="o-badge o-badge-ok" style={{ justifySelf: 'start' }}>
                {item.source_type === 'manual' ? 'Texto' : 'Arquivo'}
              </span>
              <span style={{ fontSize: 11, color: 'var(--o-sub)' }}>
                {new Date(item.updated_at).toLocaleDateString('pt-BR')}
              </span>
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="o-btn" style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => setViewItem(item)}>Ver</button>
                <button className="o-btn" style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => setEditExtra(item)}>Editar</button>
                <button
                  className="o-btn"
                  style={{ fontSize: 11, padding: '3px 8px', color: 'var(--o-hot)' }}
                  onClick={() => handleDelete(item.id)}
                  disabled={deleting === item.id}
                >
                  {deleting === item.id ? '…' : 'Remover'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Modais ───────────────────────────────────────────── */}
      {guidedModal && (
        <ModalGuided
          category={guidedModal}
          existingItem={itemByCategory.get(guidedModal.key) ?? null}
          onClose={() => setGuidedModal(null)}
          onSaved={() => { setGuidedModal(null); load(); }}
        />
      )}
      {modalAddExtra && (
        <ModalAddExtra
          onClose={() => setModalAddExtra(false)}
          onAdded={() => { setModalAddExtra(false); load(); }}
        />
      )}
      {viewItem && (
        <ModalView item={viewItem} onClose={() => setViewItem(null)} />
      )}
      {editExtra && (
        <ModalEditExtra
          item={editExtra}
          onClose={() => setEditExtra(null)}
          onSaved={() => { setEditExtra(null); load(); }}
        />
      )}
    </>
  );
}
