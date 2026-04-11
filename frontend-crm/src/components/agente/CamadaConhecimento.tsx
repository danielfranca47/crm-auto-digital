import { useState, useEffect, useRef } from 'react';
import { api, type KnowledgeItem } from '@/services/api';
import {
  KNOWLEDGE_CATEGORIES_BY_TEMPLATE,
  KNOWLEDGE_CATEGORIES_HYBRID_COMMERCIAL,
  KNOWLEDGE_IMPORTANCE_LABELS,
  type KnowledgeCategory,
  type AgentConfig,
} from '@/types/agente';
import { CamadaConhecimentoWizard } from './CamadaConhecimentoWizard';

// ─── Cores de fase do funil ───────────────────────────────────
const PHASE_COLORS: Record<string, { bg: string; text: string }> = {
  'Qualificação':            { bg: '#1e3a2f', text: '#4ade80' },
  'Aquecimento':             { bg: '#2d2a1a', text: '#fbbf24' },
  'Aquecimento · Follow-up': { bg: '#2d2a1a', text: '#fbbf24' },
  'Apresentação':            { bg: '#1a2640', text: '#60a5fa' },
  'Apresentação · Follow-up':{ bg: '#1a2640', text: '#60a5fa' },
  'Apresentação comercial':  { bg: '#2a1a35', text: '#c084fc' },
  'Follow-up':               { bg: '#2a1f1a', text: '#fb923c' },
  'Agendamento':             { bg: '#1a2e2e', text: '#2dd4bf' },
  'Handoff ao vendedor':     { bg: '#252520', text: '#a3a3a3' },
  'Pós-venda':               { bg: '#1a2020', text: '#34d399' },
  'Pós-atendimento':         { bg: '#1a2020', text: '#34d399' },
  'Qualificação · Apresentação': { bg: '#1a2640', text: '#60a5fa' },
};

function PhaseTag({ phase }: { phase: string }) {
  const colors = PHASE_COLORS[phase] || { bg: 'var(--o-b1)', text: 'var(--o-sub)' };
  return (
    <span
      className="font-mono-orion"
      style={{
        fontSize: 7, letterSpacing: 1, textTransform: 'uppercase', padding: '2px 6px',
        borderRadius: 3, background: colors.bg, color: colors.text, flexShrink: 0,
        whiteSpace: 'nowrap',
      }}
    >
      {phase}
    </span>
  );
}

// ─── Modal base (shared) ──────────────────────────────────────
function ModalBase({ title, sub, onClose, onSave, children, saveLabel = 'Salvar', wide = false }: {
  title: string; sub: string; onClose: () => void; onSave?: () => void; children: React.ReactNode; saveLabel?: string; wide?: boolean;
}) {
  return (
    <div className="o-modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="o-modal" style={{ maxWidth: wide ? 720 : 620 }}>
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

// ─── Seção de upload de mídia (dentro do modal) ───────────────
function MediaUploadSection({
  item,
  onMediaChanged,
}: {
  item: KnowledgeItem | null;
  onMediaChanged: (updated: KnowledgeItem) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [removing, setRemoving]   = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const currentMedia = item?.media_url || null;

  async function handleFile(file: File) {
    if (!item) return;
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    const allowed = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'mp4', 'pdf'];
    if (!allowed.includes(ext)) {
      setError('Formato não suportado. Use: jpg, png, webp, gif, mp4 ou pdf.');
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const updated = await api.crm.uploadKnowledgeMedia(item.id, file);
      onMediaChanged(updated);
    } catch {
      setError('Erro ao enviar mídia. Tente novamente.');
    } finally {
      setUploading(false);
    }
  }

  async function handleRemove() {
    if (!item || !currentMedia) return;
    setRemoving(true);
    setError(null);
    try {
      const updated = await api.crm.deleteKnowledgeMedia(item.id);
      onMediaChanged(updated);
    } catch {
      setError('Erro ao remover mídia. Tente novamente.');
    } finally {
      setRemoving(false);
    }
  }

  const isImage = currentMedia && /\.(jpg|jpeg|png|webp|gif)$/i.test(currentMedia);
  const isPdf   = currentMedia && /\.pdf$/i.test(currentMedia);
  const isVideo = currentMedia && /\.mp4$/i.test(currentMedia);

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10,
      }}>
        <span style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 400 }}>
          MÍDIA PARA ENVIAR AO LEAD
        </span>
        <span className="font-mono-orion" style={{ fontSize: 7, letterSpacing: 1, color: 'var(--o-dim)', border: '1px solid var(--o-b1)', padding: '1px 5px', borderRadius: 2 }}>
          OPCIONAL
        </span>
      </div>

      <div style={{
        background: 'var(--o-b0)', border: '1px solid var(--o-b1)', borderRadius: 6,
        padding: '14px 16px',
      }}>
        {!currentMedia ? (
          <>
            <div style={{ fontSize: 12, color: 'var(--o-sub)', marginBottom: 10, lineHeight: 1.5 }}>
              Imagem, PDF ou vídeo enviado automaticamente ao lead antes da mensagem do agente.
              <br/>
              <span style={{ color: 'var(--o-dim)', fontSize: 11 }}>
                Ex: foto do espaço, tabela de preços visual, card de apresentação.
              </span>
            </div>
            {!item ? (
              <div style={{ fontSize: 11, color: 'var(--o-dim)', fontStyle: 'italic' }}>
                Salve o conteúdo primeiro para poder adicionar mídia.
              </div>
            ) : (
              <>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp,.gif,.mp4,.pdf"
                  style={{ display: 'none' }}
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
                />
                <button
                  className="o-btn"
                  style={{ fontSize: 11, padding: '4px 12px' }}
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                >
                  {uploading ? 'Enviando…' : '+ Selecionar imagem / PDF / vídeo'}
                </button>
                <div style={{ fontSize: 10, color: 'var(--o-dim)', marginTop: 6 }}>
                  Aceita: .jpg .png .webp .gif .mp4 .pdf
                </div>
              </>
            )}
          </>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            {/* Preview */}
            <div style={{
              width: 72, height: 72, borderRadius: 4, overflow: 'hidden', flexShrink: 0,
              background: 'var(--o-b1)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              border: '1px solid var(--o-b2)',
            }}>
              {isImage ? (
                <img src={currentMedia} alt="mídia" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              ) : (
                <span style={{ fontSize: 22 }}>{isPdf ? '📄' : isVideo ? '🎬' : '📎'}</span>
              )}
            </div>

            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, color: 'var(--o-text)', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {currentMedia.split('/').pop()}
              </div>
              <div style={{ fontSize: 11, color: 'var(--o-active)', marginBottom: 8 }}>
                Enviada automaticamente ao lead na fase de apresentação
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="o-btn"
                  style={{ fontSize: 10, padding: '2px 8px' }}
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading || removing}
                >
                  {uploading ? 'Enviando…' : 'Trocar'}
                </button>
                <button
                  className="o-btn"
                  style={{ fontSize: 10, padding: '2px 8px', color: 'var(--o-hot)' }}
                  onClick={handleRemove}
                  disabled={uploading || removing}
                >
                  {removing ? 'Removendo…' : 'Remover'}
                </button>
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.gif,.mp4,.pdf"
                style={{ display: 'none' }}
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
              />
            </div>
          </div>
        )}

        {error && <div style={{ fontSize: 11, color: 'var(--o-hot)', marginTop: 8 }}>{error}</div>}
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
  onSaved: (item?: KnowledgeItem) => void;
}) {
  const [title, setTitle]     = useState(existingItem?.title ?? category.label);
  const [content, setContent] = useState(existingItem?.content_text ?? '');
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState<string | null>(null);
  const [savedItem, setSavedItem] = useState<KnowledgeItem | null>(existingItem);

  async function handleSave() {
    if (!content.trim() || content.trim().length < 20) {
      setError('O conteúdo deve ter pelo menos 20 caracteres.');
      return;
    }
    setSaving(true);
    try {
      let result: KnowledgeItem;
      if (savedItem) {
        result = await api.crm.updateKnowledge(savedItem.id, {
          title: title.trim(),
          content_text: content.trim(),
          category: category.key,
        });
      } else {
        result = await api.crm.createKnowledgeManual({
          title: title.trim(),
          content_text: content.trim(),
          category: category.key,
        });
      }
      setSavedItem(result);
      onSaved(result);
    } catch {
      setError('Erro ao salvar. Tente novamente.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <ModalBase
      title={savedItem ? `Editar: ${category.label}` : category.label}
      sub={category.description}
      onClose={onClose}
      onSave={handleSave}
      saveLabel={saving ? 'Salvando…' : savedItem ? 'Salvar alterações' : 'Adicionar'}
      wide
    >
      {/* Fase do funil */}
      {category.when_used && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <span style={{ fontSize: 11, color: 'var(--o-dim)' }}>Usado na fase:</span>
          <PhaseTag phase={category.when_used} />
        </div>
      )}

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
          style={{ minHeight: 200 }}
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder={category.placeholder}
        />
      </div>

      {error && <div style={{ fontSize: 12, color: 'var(--o-hot)', marginTop: 4 }}>{error}</div>}

      {/* Seção de mídia */}
      <MediaUploadSection
        item={savedItem}
        onMediaChanged={updated => { setSavedItem(updated); }}
      />
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
  const isImage = item.media_url && /\.(jpg|jpeg|png|webp|gif)$/i.test(item.media_url);
  const isPdf   = item.media_url && /\.pdf$/i.test(item.media_url);
  const isVideo = item.media_url && /\.mp4$/i.test(item.media_url);

  return (
    <ModalBase
      title={item.title}
      sub={`Tipo: ${item.source_type === 'manual' ? 'Texto' : 'Arquivo'} · Atualizado: ${new Date(item.updated_at).toLocaleDateString('pt-BR')}`}
      onClose={onClose}
      wide
    >
      {item.media_url && (
        <div style={{ marginBottom: 16 }}>
          <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 8 }}>
            Mídia para envio ao lead
          </div>
          {isImage ? (
            <img
              src={item.media_url}
              alt="mídia"
              style={{ maxWidth: '100%', maxHeight: 260, borderRadius: 6, border: '1px solid var(--o-b1)', objectFit: 'contain' }}
            />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: 'var(--o-b0)', borderRadius: 6, border: '1px solid var(--o-b1)' }}>
              <span style={{ fontSize: 20 }}>{isPdf ? '📄' : isVideo ? '🎬' : '📎'}</span>
              <span style={{ fontSize: 12, color: 'var(--o-sub)' }}>{item.media_url.split('/').pop()}</span>
              <a href={item.media_url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--o-active)', marginLeft: 'auto' }}>
                Abrir →
              </a>
            </div>
          )}
        </div>
      )}

      <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: 'var(--o-text)', lineHeight: 1.6, maxHeight: 360, overflowY: 'auto', padding: '0 4px' }}>
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
  const [liveItem, setLiveItem] = useState<KnowledgeItem>(item);

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
      saveLabel={saving ? 'Salvando…' : 'Salvar'} wide>
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
      <MediaUploadSection
        item={liveItem}
        onMediaChanged={updated => setLiveItem(updated)}
      />
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

// ─── Barra de progresso por fase ─────────────────────────────
function FunnelProgressBar({
  guidedCategories,
  itemByCategory,
}: {
  guidedCategories: KnowledgeCategory[];
  itemByCategory: Map<string, KnowledgeItem>;
}) {
  // Agrupar por fase (when_used), ignorar undefined
  const phaseMap = new Map<string, { total: number; filled: number; active: number }>();
  for (const cat of guidedCategories) {
    const phase = cat.when_used;
    if (!phase) continue;
    // Normalizar fases compostas para a fase principal
    const mainPhase = phase.split(' · ')[0];
    if (!phaseMap.has(mainPhase)) phaseMap.set(mainPhase, { total: 0, filled: 0, active: 0 });
    const entry = phaseMap.get(mainPhase)!;
    entry.total++;
    const item = itemByCategory.get(cat.key);
    if (item) {
      entry.filled++;
      if (item.active_in_funnel !== 0) entry.active++;
    }
  }

  const phases = Array.from(phaseMap.entries());
  if (phases.length === 0) return null;

  return (
    <div style={{
      display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap',
    }}>
      {phases.map(([phase, { total, filled, active }]) => {
        const pct = total > 0 ? Math.round((filled / total) * 100) : 0;
        const colors = PHASE_COLORS[phase] || { bg: 'var(--o-b1)', text: 'var(--o-sub)' };
        const allActive = filled > 0 && active === filled;
        const someInactive = filled > 0 && active < filled;
        return (
          <div key={phase} style={{ flex: '1 1 120px', minWidth: 100 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
              <span style={{ fontSize: 9, color: colors.text, textTransform: 'uppercase', letterSpacing: 1, fontFamily: 'var(--font-mono)' }}>
                {phase}
              </span>
              <span style={{ fontSize: 9, color: 'var(--o-dim)', fontFamily: 'var(--font-mono)' }}>
                {filled}/{total}
              </span>
            </div>
            <div style={{ height: 4, background: 'var(--o-b1)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${pct}%`,
                background: pct === 100 ? colors.text : (pct > 0 ? '#d97706' : 'transparent'),
                borderRadius: 2,
                transition: 'width 0.3s',
                opacity: (someInactive && allActive === false) ? 0.5 : 1,
              }} />
            </div>
            {someInactive && (
              <div style={{ fontSize: 9, color: '#d97706', marginTop: 3, fontFamily: 'var(--font-mono)' }}>
                {filled - active} pausado{filled - active > 1 ? 's' : ''}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Toggle de ativo no funil ─────────────────────────────────
function FunnelToggle({
  active,
  onChange,
  disabled,
}: {
  active: boolean;
  onChange: (active: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={e => { e.stopPropagation(); onChange(!active); }}
      disabled={disabled}
      title={active ? 'Ativo no funil — clique para pausar' : 'Pausado — clique para ativar'}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        background: 'none', border: 'none', padding: '2px 4px', cursor: 'pointer',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {/* Track */}
      <div style={{
        width: 28, height: 14, borderRadius: 7,
        background: active ? 'var(--o-active)' : 'var(--o-b2)',
        position: 'relative', transition: 'background 0.2s',
        flexShrink: 0,
      }}>
        {/* Knob */}
        <div style={{
          width: 10, height: 10, borderRadius: '50%', background: '#fff',
          position: 'absolute', top: 2, left: active ? 16 : 2,
          transition: 'left 0.2s',
          boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
        }} />
      </div>
      <span style={{ fontSize: 10, color: active ? 'var(--o-active)' : 'var(--o-dim)', fontFamily: 'var(--font-mono)', letterSpacing: 0.5, whiteSpace: 'nowrap' }}>
        {active ? 'No funil' : 'Pausado'}
      </span>
    </button>
  );
}

// ─── Card de seção guiada ─────────────────────────────────────
function GuidedSectionCard({
  category,
  item,
  activeOverride,
  onFill,
  onView,
  onDelete,
  onToggleActive,
  deleting,
  togglingActive,
}: {
  category: KnowledgeCategory;
  item: KnowledgeItem | null;
  activeOverride: boolean | undefined;
  onFill: () => void;
  onView: () => void;
  onDelete: () => void;
  onToggleActive: (active: boolean) => void;
  deleting: boolean;
  togglingActive: boolean;
}) {
  const filled = !!item;
  const isActive = activeOverride !== undefined ? activeOverride : (item ? item.active_in_funnel !== 0 : true);
  const isCritical = category.importance === 'critical';
  const importanceColor = isCritical
    ? (filled ? 'var(--o-active)' : 'var(--o-hot)')
    : 'var(--o-dim)';
  const importanceBorder = isCritical
    ? (filled ? 'var(--o-active-b)' : 'var(--o-hot-b)')
    : 'var(--o-b1)';

  const showStaleBadge = filled && item && STALE_KEYS.has(category.key) && isStale(item);
  const dotColor = filled
    ? (isActive ? 'var(--o-active)' : 'var(--o-b2)')
    : (isCritical ? 'var(--o-hot)' : 'var(--o-b2)');

  return (
    <div style={{
      padding: '12px 14px',
      background: 'var(--o-b0)',
      borderRadius: 4,
      border: `1px solid ${filled && !isActive ? 'var(--o-b1)' : (filled ? 'var(--o-b1)' : (isCritical ? 'var(--o-hot-b)' : 'var(--o-b1)'))}`,
      opacity: filled && !isActive ? 0.65 : 1,
      transition: 'opacity 0.2s',
    }}>
      {/* Linha principal */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          {/* Status dot */}
          <div style={{
            width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
            background: dotColor,
          }} />
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
              {item?.media_url && (
                <span title="Tem mídia para envio ao lead" style={{ fontSize: 11, flexShrink: 0 }}>📷</span>
              )}
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
            {/* Tag de fase — visível apenas quando não preenchido */}
            {!filled && category.when_used && (
              <div style={{ marginTop: 5 }}>
                <PhaseTag phase={category.when_used} />
              </div>
            )}
          </div>
        </div>

        {/* Ações */}
        <div style={{ display: 'flex', gap: 6, flexShrink: 0, alignItems: 'center' }}>
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

      {/* Linha secundária: toggle de funil + fase (somente quando preenchido) */}
      {filled && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--o-b1)' }}>
          <FunnelToggle
            active={isActive}
            onChange={onToggleActive}
            disabled={togglingActive}
          />
          {category.when_used && (
            <div style={{ marginLeft: 'auto' }}>
              <PhaseTag phase={category.when_used} />
            </div>
          )}
        </div>
      )}
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
  const [wizardDismissed, setWizardDismissed] = useState(false);

  // Overrides optimistas para active_in_funnel
  const [activeOverrides, setActiveOverrides] = useState<Map<number, boolean>>(new Map());
  const [togglingId, setTogglingId]   = useState<number | null>(null);

  // Modais
  const [guidedModal, setGuidedModal] = useState<KnowledgeCategory | null>(null);
  const [modalAddExtra, setModalAddExtra] = useState(false);
  const [viewItem, setViewItem]       = useState<KnowledgeItem | null>(null);
  const [editExtra, setEditExtra]     = useState<KnowledgeItem | null>(null);

  // Categorias brutas (sem personalização) — usadas pelo wizard
  const rawBaseCategories: KnowledgeCategory[] =
    (templateKey && KNOWLEDGE_CATEGORIES_BY_TEMPLATE[templateKey]) || [];

  // Categorias comerciais extras (somente para hybrid_scheduler em modo commercial)
  const commercialCategories: KnowledgeCategory[] =
    templateKey === 'hybrid_scheduler' && agentConfig?.appointment_mode === 'commercial'
      ? KNOWLEDGE_CATEGORIES_HYBRID_COMMERCIAL
      : [];

  // Todas as categorias brutas (base + comercial, se aplicável) — usadas pelo wizard
  const rawGuidedCategories: KnowledgeCategory[] = [...rawBaseCategories, ...commercialCategories];

  // Categorias guiadas baseadas no template do agente, com hints/placeholders personalizados
  const guidedCategories: KnowledgeCategory[] = rawBaseCategories
    .map(cat => getPersonalizedCategory(cat, agentConfig ?? {}));

  const guidedCommercialCategories: KnowledgeCategory[] = commercialCategories
    .map(cat => getPersonalizedCategory(cat, agentConfig ?? {}));

  // Mapa de category → item existente
  const itemByCategory = new Map<string, KnowledgeItem>();
  for (const item of items) {
    if (item.category) itemByCategory.set(item.category, item);
  }

  // Itens "extras" — sem categoria guiada (ou com categoria desconhecida)
  const allGuidedKeys = new Set([
    ...guidedCategories.map(c => c.key),
    ...guidedCommercialCategories.map(c => c.key),
  ]);
  const extraItems = items.filter(i => !i.category || !allGuidedKeys.has(i.category));

  // Score de prontidão (considera todas as categorias guiadas incluindo as comerciais)
  const allGuidedForReadiness = [...guidedCategories, ...guidedCommercialCategories];
  const readinessLevel = getReadinessLevel(allGuidedForReadiness, itemByCategory);
  const readiness = READINESS_CONFIG[readinessLevel];

  async function load() {
    setLoading(true);
    try {
      const data = await api.crm.getKnowledgeList();
      setItems(data);
      setActiveOverrides(new Map()); // limpar overrides ao recarregar
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

  async function handleToggleActive(item: KnowledgeItem) {
    const currentActive = activeOverrides.has(item.id)
      ? activeOverrides.get(item.id)!
      : item.active_in_funnel !== 0;
    const newActive = !currentActive;

    // Optimistic update
    setActiveOverrides(prev => new Map(prev).set(item.id, newActive));
    setTogglingId(item.id);
    try {
      await api.crm.updateKnowledge(item.id, { active_in_funnel: newActive ? 1 : 0 });
      // Atualizar o item na lista local também
      setItems(prev => prev.map(i => i.id === item.id ? { ...i, active_in_funnel: newActive ? 1 : 0 } : i));
    } catch {
      // Reverter
      setActiveOverrides(prev => new Map(prev).set(item.id, currentActive));
    } finally {
      setTogglingId(null);
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

  // Wizard de onboarding — exibido na primeira vez (base vazia)
  const isFirstTime = items.length === 0 && rawGuidedCategories.length > 0 && !wizardDismissed;
  if (isFirstTime) {
    return (
      <CamadaConhecimentoWizard
        rawCategories={rawGuidedCategories}
        agentConfig={agentConfig ?? {}}
        onComplete={() => { setWizardDismissed(true); load(); }}
      />
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

          {/* Barra de progresso por fase */}
          <FunnelProgressBar
            guidedCategories={allGuidedForReadiness}
            itemByCategory={itemByCategory}
          />

          <div className="o-section-hdr" style={{ marginBottom: 12 }}>
            <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
              Seções sugeridas para este agente
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: guidedCommercialCategories.length > 0 ? 16 : 32 }}>
            {guidedCategories.map(cat => {
              const item = itemByCategory.get(cat.key) ?? null;
              return (
                <GuidedSectionCard
                  key={cat.key}
                  category={cat}
                  item={item}
                  activeOverride={item ? activeOverrides.get(item.id) : undefined}
                  onFill={() => setGuidedModal(cat)}
                  onView={() => setViewItem(item)}
                  onDelete={() => { if (item) handleDelete(item.id); }}
                  onToggleActive={() => { if (item) handleToggleActive(item); }}
                  deleting={deleting === (item?.id ?? -1)}
                  togglingActive={togglingId === (item?.id ?? -1)}
                />
              );
            })}
          </div>

          {/* Seção comercial — somente para hybrid_scheduler em modo commercial */}
          {guidedCommercialCategories.length > 0 && (
            <>
              <div className="o-section-hdr" style={{ marginBottom: 12 }}>
                <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
                  Compromisso comercial
                </span>
                <span style={{ fontSize: 11, color: 'var(--o-dim)', fontWeight: 300, marginLeft: 8 }}>
                  — preenchimento necessário para o modo comercial
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 32 }}>
                {guidedCommercialCategories.map(cat => {
                  const item = itemByCategory.get(cat.key) ?? null;
                  return (
                    <GuidedSectionCard
                      key={cat.key}
                      category={cat}
                      item={item}
                      activeOverride={item ? activeOverrides.get(item.id) : undefined}
                      onFill={() => setGuidedModal(cat)}
                      onView={() => setViewItem(item)}
                      onDelete={() => { if (item) handleDelete(item.id); }}
                      onToggleActive={() => { if (item) handleToggleActive(item); }}
                      deleting={deleting === (item?.id ?? -1)}
                      togglingActive={togglingId === (item?.id ?? -1)}
                    />
                  );
                })}
              </div>
            </>
          )}
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
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 90px 100px 80px 140px', gap: 12, padding: '4px 12px' }}>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Título</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Tipo</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Atualizado</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Funil</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Ações</span>
          </div>
          {extraItems.map(item => {
            const isActive = activeOverrides.has(item.id)
              ? activeOverrides.get(item.id)!
              : item.active_in_funnel !== 0;
            return (
              <div
                key={item.id}
                style={{
                  display: 'grid', gridTemplateColumns: '1fr 90px 100px 80px 140px', gap: 12,
                  padding: '10px 12px', background: 'var(--o-b0)', borderRadius: 4,
                  border: '1px solid var(--o-b1)', alignItems: 'center',
                  opacity: isActive ? 1 : 0.6, transition: 'opacity 0.2s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden' }}>
                  <span style={{ fontSize: 13, color: 'var(--o-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {item.title}
                  </span>
                  {item.media_url && <span title="Tem mídia para envio" style={{ fontSize: 11, flexShrink: 0 }}>📷</span>}
                </div>
                <span className="o-badge o-badge-ok" style={{ justifySelf: 'start' }}>
                  {item.source_type === 'manual' ? 'Texto' : 'Arquivo'}
                </span>
                <span style={{ fontSize: 11, color: 'var(--o-sub)' }}>
                  {new Date(item.updated_at).toLocaleDateString('pt-BR')}
                </span>
                <FunnelToggle
                  active={isActive}
                  onChange={() => handleToggleActive(item)}
                  disabled={togglingId === item.id}
                />
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
            );
          })}
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
