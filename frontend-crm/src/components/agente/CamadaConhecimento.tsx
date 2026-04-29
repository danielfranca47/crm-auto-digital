import { useState, useEffect, useRef } from 'react';
import { SuggestInput, SuggestTextarea } from './SuggestField';
import { api, type KnowledgeItem, type KnowledgeMediaItem, type MediaLanguage } from '@/services/api';
import {
  KNOWLEDGE_CATEGORIES_BY_TEMPLATE,
  KNOWLEDGE_CATEGORIES_HYBRID_COMMERCIAL,
  KNOWLEDGE_IMPORTANCE_LABELS,
  type KnowledgeCategory,
  type AgentConfig,
} from '@/types/agente';
import { CamadaConhecimentoWizard } from './CamadaConhecimentoWizard';
import { BusinessInfo } from './BusinessInfo';

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

// ─── Helpers de mídia ────────────────────────────────────────
const LANG_LABELS: Record<MediaLanguage, string> = { all: 'TODOS', pt: 'PT', en: 'EN', es: 'ES' };
const LANG_COLORS: Record<MediaLanguage, { bg: string; text: string }> = {
  all: { bg: 'var(--o-b1)', text: 'var(--o-sub)' },
  pt:  { bg: '#1a2f1a', text: '#4ade80' },
  en:  { bg: '#1a2040', text: '#60a5fa' },
  es:  { bg: '#2a1a10', text: '#fb923c' },
};

function LangBadge({ lang }: { lang: MediaLanguage }) {
  const c = LANG_COLORS[lang] || LANG_COLORS.all;
  return (
    <span className="font-mono-orion" style={{
      fontSize: 7, letterSpacing: 1, padding: '2px 5px', borderRadius: 3,
      background: c.bg, color: c.text, flexShrink: 0,
    }}>
      {LANG_LABELS[lang]}
    </span>
  );
}

function MediaThumb({ url, type }: { url: string; type: string }) {
  const isImg = type === 'image' || /\.(jpg|jpeg|png|webp|gif)$/i.test(url);
  const icon = type === 'pdf' ? '📄' : type === 'video' ? '🎬' : type === 'audio' ? '🎵' : '📎';
  return (
    <div style={{
      width: 52, height: 52, borderRadius: 4, overflow: 'hidden', flexShrink: 0,
      background: 'var(--o-b1)', display: 'flex', alignItems: 'center', justifyContent: 'center',
      border: '1px solid var(--o-b2)',
    }}>
      {isImg
        ? <img src={url} alt="mídia" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        : <span style={{ fontSize: 20 }}>{icon}</span>
      }
    </div>
  );
}

// ─── Seção de upload de mídia — múltiplas mídias e idiomas ────
function MultiMediaSection({
  item,
  onItemChanged,
}: {
  item: KnowledgeItem | null;
  onItemChanged: (updated: KnowledgeItem) => void;
}) {
  const [mediaItems, setMediaItems] = useState<KnowledgeMediaItem[]>(item?.media_items ?? []);
  const [uploading, setUploading]   = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [selectedLang, setSelectedLang] = useState<MediaLanguage>('all');
  const fileRef = useRef<HTMLInputElement>(null);

  // Sync when parent item changes (e.g. after save)
  useEffect(() => {
    setMediaItems(item?.media_items ?? []);
  }, [item?.id, item?.media_items?.length]);

  const ALLOWED = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'mp4', 'pdf', 'mp3', 'ogg', 'opus'];

  async function handleFile(file: File) {
    if (!item) return;
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    if (!ALLOWED.includes(ext)) {
      setError('Formato não suportado. Use: jpg, png, gif, mp4, pdf, mp3, ogg.');
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const added = await api.crm.addKnowledgeMedia(item.id, file, selectedLang, mediaItems.length);
      const next = [...mediaItems, added];
      setMediaItems(next);
      onItemChanged({ ...item, media_items: next, media_url: next[0]?.media_url ?? item.media_url });
    } catch {
      setError('Erro ao enviar mídia. Tente novamente.');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function handleRemove(mediaId: number) {
    if (!item) return;
    try {
      await api.crm.deleteKnowledgeMediaItem(item.id, mediaId);
      const next = mediaItems.filter(m => m.id !== mediaId);
      setMediaItems(next);
      onItemChanged({ ...item, media_items: next, media_url: next[0]?.media_url ?? null });
    } catch {
      setError('Erro ao remover mídia.');
    }
  }

  async function handleLangChange(mediaId: number, lang: MediaLanguage) {
    if (!item) return;
    try {
      const updated = await api.crm.updateKnowledgeMediaMeta(item.id, mediaId, { language: lang });
      const next = mediaItems.map(m => m.id === mediaId ? updated : m);
      setMediaItems(next);
      onItemChanged({ ...item, media_items: next });
    } catch {
      setError('Erro ao atualizar idioma.');
    }
  }

  async function handleMove(index: number, dir: -1 | 1) {
    if (!item) return;
    const target = index + dir;
    if (target < 0 || target >= mediaItems.length) return;
    const next = [...mediaItems];
    [next[index], next[target]] = [next[target], next[index]];
    const reordered = next.map((m, i) => ({ ...m, send_order: i }));
    setMediaItems(reordered);
    onItemChanged({ ...item, media_items: reordered });
    try {
      await api.crm.reorderKnowledgeMedia(item.id, reordered.map(m => ({ id: m.id, send_order: m.send_order })));
    } catch {
      setError('Erro ao reordenar mídias.');
    }
  }

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 400 }}>MÍDIA PARA ENVIAR AO LEAD</span>
        <span className="font-mono-orion" style={{ fontSize: 7, letterSpacing: 1, color: 'var(--o-dim)', border: '1px solid var(--o-b1)', padding: '1px 5px', borderRadius: 2 }}>
          OPCIONAL
        </span>
      </div>

      <div style={{ background: 'var(--o-b0)', border: '1px solid var(--o-b1)', borderRadius: 6, padding: '14px 16px' }}>
        {/* Lista de mídias existentes */}
        {mediaItems.length > 0 && (
          <div style={{ marginBottom: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {mediaItems.map((m, i) => (
              <div key={m.id} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 10px', borderRadius: 5,
                background: 'var(--o-bg)', border: '1px solid var(--o-b1)',
              }}>
                <span style={{ fontSize: 10, color: 'var(--o-dim)', minWidth: 14, textAlign: 'center' }}>#{i + 1}</span>
                <MediaThumb url={m.media_url} type={m.media_type} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 11, color: 'var(--o-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: 4 }}>
                    {m.media_url.split('/').pop()}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <LangBadge lang={m.language as MediaLanguage} />
                    <select
                      value={m.language}
                      onChange={e => handleLangChange(m.id, e.target.value as MediaLanguage)}
                      style={{
                        fontSize: 10, background: 'var(--o-b1)', color: 'var(--o-sub)',
                        border: '1px solid var(--o-b2)', borderRadius: 3, padding: '1px 4px', cursor: 'pointer',
                      }}
                    >
                      <option value="all">Todos os idiomas</option>
                      <option value="pt">Português</option>
                      <option value="en">English</option>
                      <option value="es">Español</option>
                    </select>
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <button
                    className="o-btn" title="Mover para cima"
                    style={{ fontSize: 9, padding: '1px 6px', lineHeight: 1.4 }}
                    disabled={i === 0}
                    onClick={() => handleMove(i, -1)}
                  >▲</button>
                  <button
                    className="o-btn" title="Mover para baixo"
                    style={{ fontSize: 9, padding: '1px 6px', lineHeight: 1.4 }}
                    disabled={i === mediaItems.length - 1}
                    onClick={() => handleMove(i, 1)}
                  >▼</button>
                </div>
                <button
                  className="o-btn"
                  style={{ fontSize: 10, padding: '2px 8px', color: 'var(--o-hot)', flexShrink: 0 }}
                  onClick={() => handleRemove(m.id)}
                >
                  Remover
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Adicionar nova mídia */}
        {!item ? (
          <div style={{ fontSize: 11, color: 'var(--o-dim)', fontStyle: 'italic' }}>
            Salve o conteúdo primeiro para poder adicionar mídia.
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <select
              value={selectedLang}
              onChange={e => setSelectedLang(e.target.value as MediaLanguage)}
              style={{
                fontSize: 11, background: 'var(--o-b1)', color: 'var(--o-sub)',
                border: '1px solid var(--o-b2)', borderRadius: 4, padding: '4px 8px', cursor: 'pointer',
              }}
            >
              <option value="all">Todos os idiomas</option>
              <option value="pt">Português</option>
              <option value="en">English</option>
              <option value="es">Español</option>
            </select>
            <input
              ref={fileRef}
              type="file"
              accept=".jpg,.jpeg,.png,.webp,.gif,.mp4,.pdf,.mp3,.ogg,.opus"
              style={{ display: 'none' }}
              onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
            />
            <button
              className="o-btn"
              style={{ fontSize: 11, padding: '4px 12px' }}
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? 'Enviando…' : '+ Adicionar mídia'}
            </button>
            <span style={{ fontSize: 10, color: 'var(--o-dim)' }}>
              jpg · png · gif · mp4 · pdf · mp3 · ogg (áudio → mensagem de voz)
            </span>
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
        <SuggestInput
          className="o-input"
          value={title}
          onChange={e => setTitle(e.target.value)}
          maxLength={120}
          placeholder={category.title ? `Ex: ${category.title}` : undefined}
        />
        <div className="o-char-count">{title.length}/120</div>
      </div>

      <div className="o-field">
        <label className="o-field-label">Conteúdo</label>
        <SuggestTextarea
          className="o-textarea"
          style={{ minHeight: 200 }}
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder={category.placeholder}
        />
      </div>

      {error && <div style={{ fontSize: 12, color: 'var(--o-hot)', marginTop: 4 }}>{error}</div>}

      {/* Seção de mídia */}
      <MultiMediaSection
        item={savedItem}
        onItemChanged={updated => { setSavedItem(updated); }}
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
            <SuggestInput className="o-input" value={title} onChange={e => setTitle(e.target.value)} maxLength={120}
              placeholder="Ex: Política de preços, FAQ, Script de vendas…" />
            <div className="o-char-count">{title.length}/120</div>
          </div>
          <div className="o-field">
            <label className="o-field-label">Conteúdo</label>
            <SuggestTextarea className="o-textarea" style={{ minHeight: 180 }} value={content}
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
  const allMedia = item.media_items?.length ? item.media_items : (item.media_url ? [{
    id: 0, knowledge_item_id: item.id, media_url: item.media_url,
    media_type: /\.(mp4)$/i.test(item.media_url) ? 'video' : /\.pdf$/i.test(item.media_url) ? 'pdf' : 'image',
    language: 'all' as MediaLanguage, send_order: 0, created_at: '',
  }] : []);

  return (
    <ModalBase
      title={item.title}
      sub={`Tipo: ${item.source_type === 'manual' ? 'Texto' : 'Arquivo'} · Atualizado: ${new Date(item.updated_at).toLocaleDateString('pt-BR')}`}
      onClose={onClose}
      wide
    >
      {allMedia.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 8 }}>
            Mídia para envio ao lead
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {allMedia.map((m, i) => {
              const isImg = m.media_type === 'image' || /\.(jpg|jpeg|png|webp|gif)$/i.test(m.media_url);
              const icon = m.media_type === 'pdf' ? '📄' : m.media_type === 'video' ? '🎬' : m.media_type === 'myaudio' || m.media_type === 'ptt' ? '🎙️' : m.media_type === 'audio' ? '🎵' : '📎';
              return (
                <div key={m.id || i}>
                  {isImg && i === 0 ? (
                    <div>
                      <img
                        src={m.media_url}
                        alt="mídia"
                        style={{ maxWidth: '100%', maxHeight: 200, borderRadius: 6, border: '1px solid var(--o-b1)', objectFit: 'contain', display: 'block', marginBottom: 6 }}
                      />
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 10, color: 'var(--o-dim)' }}>#{i + 1}</span>
                        <LangBadge lang={m.language as MediaLanguage} />
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', background: 'var(--o-b0)', borderRadius: 5, border: '1px solid var(--o-b1)' }}>
                      <span style={{ fontSize: 10, color: 'var(--o-dim)' }}>#{i + 1}</span>
                      <span style={{ fontSize: 18 }}>{icon}</span>
                      <span style={{ fontSize: 12, color: 'var(--o-sub)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {m.media_url.split('/').pop()}
                      </span>
                      <LangBadge lang={m.language as MediaLanguage} />
                      <a href={m.media_url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--o-active)', flexShrink: 0 }}>
                        Abrir →
                      </a>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
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
        <SuggestInput className="o-input" value={title} onChange={e => setTitle(e.target.value)} maxLength={120} />
        <div className="o-char-count">{title.length}/120</div>
      </div>
      <div className="o-field">
        <label className="o-field-label">Conteúdo</label>
        <SuggestTextarea className="o-textarea" style={{ minHeight: 200 }} value={content} onChange={e => setContent(e.target.value)} />
      </div>
      {error && <div style={{ fontSize: 12, color: 'var(--o-hot)', marginTop: 8 }}>{error}</div>}
      <MultiMediaSection
        item={liveItem}
        onItemChanged={updated => setLiveItem(updated)}
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

// ─── Barra de progresso por fase (com filtro clicável) ───────
function FunnelProgressBar({
  guidedCategories,
  itemByCategory,
  selectedPhases,
  onTogglePhase,
}: {
  guidedCategories: KnowledgeCategory[];
  itemByCategory: Map<string, KnowledgeItem>;
  selectedPhases: Set<string>;
  onTogglePhase: (phase: string) => void;
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

  const hasFilter = selectedPhases.size > 0;

  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
      {phases.map(([phase, { total, filled, active }]) => {
        const pct = total > 0 ? Math.round((filled / total) * 100) : 0;
        const colors = PHASE_COLORS[phase] || { bg: 'var(--o-b1)', text: 'var(--o-sub)' };
        const someInactive = filled > 0 && active < filled;
        const isSelected = selectedPhases.has(phase);
        const isDimmed = hasFilter && !isSelected;

        return (
          <div
            key={phase}
            onClick={() => onTogglePhase(phase)}
            style={{
              flex: '1 1 120px', minWidth: 100, cursor: 'pointer',
              padding: '6px 8px', borderRadius: 4,
              border: `1px solid ${isSelected ? colors.text : 'var(--o-b1)'}`,
              background: isSelected ? colors.bg : 'transparent',
              opacity: isDimmed ? 0.4 : 1,
              transition: 'opacity 0.15s, border-color 0.15s, background 0.15s',
              userSelect: 'none',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
              <span style={{ fontSize: 9, color: isSelected ? colors.text : 'var(--o-sub)', textTransform: 'uppercase', letterSpacing: 1, fontFamily: 'var(--font-mono)', transition: 'color 0.15s' }}>
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
                opacity: (someInactive) ? 0.5 : 1,
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
  onDismiss,
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
  onDismiss: () => void;
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
              {(item?.media_items?.length > 0 || item?.media_url) && (
                <span title={`${item?.media_items?.length || 1} mídia(s) para envio`} style={{ fontSize: 11, flexShrink: 0 }}>
                  📷{(item?.media_items?.length ?? 0) > 1 ? <sup style={{ fontSize: 8 }}>{item!.media_items.length}</sup> : null}
                </span>
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
            <>
              <button className="o-btn o-btn-primary" style={{ fontSize: 11, padding: '3px 10px' }} onClick={onFill}>
                Preencher →
              </button>
              <button
                className="o-btn"
                style={{ fontSize: 11, padding: '3px 8px', color: 'var(--o-dim)' }}
                onClick={onDismiss}
                title="Ocultar esta seção da lista"
              >
                Ignorar
              </button>
            </>
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
  const [selectedPhases, setSelectedPhases]   = useState<Set<string>>(new Set());
  const [dismissedKeys, setDismissedKeys]     = useState<Set<string>>(new Set());
  const [showDismissed, setShowDismissed]     = useState(false);

  function handleTogglePhase(phase: string) {
    setSelectedPhases(prev => {
      const next = new Set(prev);
      if (next.has(phase)) {
        next.delete(phase);
      } else {
        next.add(phase);
      }
      return next;
    });
  }

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

  // Categorias filtradas por fase selecionada
  function matchesPhaseFilter(cat: KnowledgeCategory): boolean {
    if (selectedPhases.size === 0) return true;
    const parts = cat.when_used?.split(' · ') ?? [];
    return parts.some(p => selectedPhases.has(p));
  }
  const filteredGuidedCategories = guidedCategories.filter(
    cat => matchesPhaseFilter(cat) && !(dismissedKeys.has(cat.key) && !itemByCategory.has(cat.key))
  );
  const filteredCommercialCategories = guidedCommercialCategories.filter(
    cat => matchesPhaseFilter(cat) && !(dismissedKeys.has(cat.key) && !itemByCategory.has(cat.key))
  );

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

  // Ler seções ignoradas do localStorage após carregar items
  useEffect(() => {
    if (items.length === 0) return;
    const uid = items[0].user_id;
    try {
      const raw = localStorage.getItem(`kb_dismissed_sections_${uid}`);
      if (raw) setDismissedKeys(new Set(JSON.parse(raw) as string[]));
    } catch { /* ignore */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.length > 0 ? items[0].user_id : null]);

  function persistDismissed(next: Set<string>) {
    if (items.length === 0) return;
    localStorage.setItem(`kb_dismissed_sections_${items[0].user_id}`, JSON.stringify([...next]));
    setDismissedKeys(next);
  }

  function handleDismiss(key: string) {
    persistDismissed(new Set([...dismissedKeys, key]));
  }

  function handleRestore(key: string) {
    const next = new Set(dismissedKeys);
    next.delete(key);
    persistDismissed(next);
  }

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

          {/* Barra de progresso por fase (clicável para filtrar) */}
          <FunnelProgressBar
            guidedCategories={allGuidedForReadiness}
            itemByCategory={itemByCategory}
            selectedPhases={selectedPhases}
            onTogglePhase={handleTogglePhase}
          />

          <div className="o-section-hdr" style={{ marginBottom: 12 }}>
            <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
              Seções sugeridas para este agente
            </span>
            {selectedPhases.size > 0 && (
              <button
                onClick={() => setSelectedPhases(new Set())}
                style={{
                  marginLeft: 10, fontSize: 9, color: 'var(--o-dim)', background: 'none',
                  border: '1px solid var(--o-b2)', borderRadius: 3, padding: '1px 7px',
                  cursor: 'pointer', fontFamily: 'var(--font-mono)', letterSpacing: 0.5,
                }}
              >
                limpar filtro ✕
              </button>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: guidedCommercialCategories.length > 0 ? 16 : 32 }}>
            {filteredGuidedCategories.length === 0 && (
              <div style={{ fontSize: 12, color: 'var(--o-dim)', padding: '12px 0' }}>
                Nenhuma seção nesta fase.
              </div>
            )}
            {filteredGuidedCategories.map(cat => {
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
                  onDismiss={() => handleDismiss(cat.key)}
                  deleting={deleting === (item?.id ?? -1)}
                  togglingActive={togglingId === (item?.id ?? -1)}
                />
              );
            })}
          </div>

          {/* Seção comercial — somente para hybrid_scheduler em modo commercial */}
          {guidedCommercialCategories.length > 0 && filteredCommercialCategories.length > 0 && (
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
                {filteredCommercialCategories.map(cat => {
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
                      onDismiss={() => handleDismiss(cat.key)}
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

      {/* ── Seções ignoradas ─────────────────────────────────── */}
      {dismissedKeys.size > 0 && (
        <div style={{ marginBottom: 24 }}>
          <button
            onClick={() => setShowDismissed(v => !v)}
            style={{
              fontSize: 11, color: 'var(--o-dim)', background: 'none', border: 'none',
              cursor: 'pointer', fontFamily: 'var(--font-mono)', letterSpacing: 0.5, padding: 0,
            }}
          >
            {dismissedKeys.size} seção{dismissedKeys.size > 1 ? 'ões' : ''} ignorada{dismissedKeys.size > 1 ? 's' : ''}{' '}
            {showDismissed ? '▲ ocultar' : '▼ mostrar'}
          </button>

          {showDismissed && (
            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[...dismissedKeys].map(key => {
                const cat = [...guidedCategories, ...guidedCommercialCategories].find(c => c.key === key);
                if (!cat) return null;
                const importanceColor = cat.importance === 'critical' ? 'var(--o-hot)' : 'var(--o-dim)';
                const importanceBorder = cat.importance === 'critical' ? 'var(--o-hot-b)' : 'var(--o-b1)';
                return (
                  <div
                    key={key}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '8px 12px', background: 'var(--o-b0)',
                      border: '1px solid var(--o-b1)', borderRadius: 4, opacity: 0.7,
                    }}
                  >
                    <span style={{ fontSize: 12, color: 'var(--o-sub)', flex: 1 }}>{cat.label}</span>
                    <span
                      className="font-mono-orion"
                      style={{
                        fontSize: 7, letterSpacing: 1.5, textTransform: 'uppercase', padding: '1px 5px',
                        borderRadius: 2, border: `1px solid ${importanceBorder}`, color: importanceColor, flexShrink: 0,
                      }}
                    >
                      {KNOWLEDGE_IMPORTANCE_LABELS[cat.importance]}
                    </span>
                    <button
                      className="o-btn"
                      style={{ fontSize: 11, padding: '3px 8px' }}
                      onClick={() => handleRestore(key)}
                    >
                      Restaurar
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
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
                  {(item.media_items?.length > 0 || item.media_url) && (
                    <span title={`${item.media_items?.length || 1} mídia(s) para envio`} style={{ fontSize: 11, flexShrink: 0 }}>
                      📷{item.media_items?.length > 1 ? <sup style={{ fontSize: 8 }}>{item.media_items.length}</sup> : null}
                    </span>
                  )}
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

      {/* ── Informações gerais do negócio ───────────────────── */}
      <div style={{ marginTop: 32, marginBottom: 8 }}>
        <div className="o-section-hdr" style={{ marginBottom: 12 }}>
          <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
            Informações gerais do negócio
          </span>
        </div>
        <BusinessInfo />
      </div>

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
