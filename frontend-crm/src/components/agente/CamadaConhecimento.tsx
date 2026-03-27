import { useState, useEffect, useRef } from 'react';
import { api } from '@/services/api';

interface KnowledgeItem {
  id: number;
  title: string;
  content_text: string;
  source_type: string;
  created_at: string;
  updated_at: string;
}

// ─── Modal base (shared) ──────────────────────────────────────
function ModalBase({ title, sub, onClose, onSave, children, saveLabel = 'Salvar alterações' }: {
  title: string; sub: string; onClose: () => void; onSave?: () => void; children: React.ReactNode; saveLabel?: string;
}) {
  return (
    <div className="o-modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="o-modal" style={{ maxWidth: 600 }}>
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

// ─── Modal: Adicionar conhecimento ───────────────────────────
function ModalAdd({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [tab, setTab]     = useState<'text' | 'file'>('text');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [file, setFile]   = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
    <ModalBase title="Adicionar conhecimento" sub="Adicione texto livre ou faça upload de um arquivo" onClose={onClose} onSave={handleSave} saveLabel={saving ? 'Salvando…' : 'Adicionar'}>
      {/* Tabs */}
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
            <input className="o-input" value={title} onChange={e => setTitle(e.target.value)} maxLength={120} placeholder="Ex: Política de preços, FAQ, Script de vendas…" />
            <div className="o-char-count">{title.length}/120</div>
          </div>
          <div className="o-field">
            <label className="o-field-label">Conteúdo</label>
            <textarea className="o-textarea" style={{ minHeight: 200 }} value={content} onChange={e => setContent(e.target.value)} placeholder="Cole ou escreva o conteúdo que o agente deve saber…" />
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

// ─── Modal: Editar conhecimento ───────────────────────────────
function ModalEdit({ item, onClose, onSaved }: { item: KnowledgeItem; onClose: () => void; onSaved: () => void }) {
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
    <ModalBase title="Editar conhecimento" sub={`Editando: ${item.title}`} onClose={onClose} onSave={handleSave} saveLabel={saving ? 'Salvando…' : 'Salvar'}>
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

// ─── Modal: Ver conhecimento ──────────────────────────────────
function ModalView({ item, onClose }: { item: KnowledgeItem; onClose: () => void }) {
  return (
    <ModalBase title={item.title} sub={`Tipo: ${item.source_type} · Atualizado: ${new Date(item.updated_at).toLocaleDateString('pt-BR')}`} onClose={onClose}>
      <div style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: 'var(--o-text)', lineHeight: 1.6, maxHeight: 400, overflowY: 'auto', padding: '0 4px' }}>
        {item.content_text || 'Sem conteúdo.'}
      </div>
    </ModalBase>
  );
}

// ─────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────

export function CamadaConhecimento() {
  const [items, setItems]         = useState<KnowledgeItem[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [modalAdd, setModalAdd]   = useState(false);
  const [editItem, setEditItem]   = useState<KnowledgeItem | null>(null);
  const [viewItem, setViewItem]   = useState<KnowledgeItem | null>(null);
  const [deleting, setDeleting]   = useState<number | null>(null);

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

  return (
    <>
      {/* Header da seção */}
      <div className="o-section-hdr" style={{ marginBottom: 16 }}>
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Base de conhecimento
        </span>
        <span className="font-mono-orion" style={{ fontSize: 8, color: 'var(--o-dim)', border: '1px solid var(--o-b1)', padding: '1px 6px', borderRadius: 2 }}>
          {items.length} item(s)
        </span>
      </div>

      <div style={{ fontSize: 12.5, color: 'var(--o-sub)', marginBottom: 16, fontWeight: 300 }}>
        Documentos e textos que o agente pode consultar durante as conversas — FAQs, scripts, políticas, catálogos.
      </div>

      <button className="o-btn o-btn-primary" style={{ marginBottom: 20 }} onClick={() => setModalAdd(true)}>
        + Adicionar conhecimento
      </button>

      {loading && (
        <div style={{ padding: 32, textAlign: 'center' }}>
          <span className="font-mono-orion" style={{ fontSize: 10, color: 'var(--o-dim)' }}>Carregando…</span>
        </div>
      )}

      {error && (
        <div className="o-alert o-alert-danger">
          <span>⚠</span>
          <span>{error}</span>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div style={{ padding: 32, textAlign: 'center', border: '1px dashed var(--o-b1)', borderRadius: 4 }}>
          <div className="font-mono-orion" style={{ fontSize: 9, color: 'var(--o-dim)', marginBottom: 8 }}>NENHUM ITEM</div>
          <div style={{ fontSize: 12.5, color: 'var(--o-sub)', fontWeight: 300 }}>
            Adicione textos, scripts ou FAQs para que o agente possa consultá-los.
          </div>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Header da tabela */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px 120px 110px', gap: 12, padding: '4px 12px' }}>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Título</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Tipo</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Atualizado</span>
            <span className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}>Ações</span>
          </div>

          {items.map(item => (
            <div
              key={item.id}
              style={{
                display: 'grid', gridTemplateColumns: '1fr 100px 120px 110px', gap: 12,
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
                <button className="o-btn" style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => setEditItem(item)}>Editar</button>
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

      {/* Modais */}
      {modalAdd && (
        <ModalAdd
          onClose={() => setModalAdd(false)}
          onAdded={() => { setModalAdd(false); load(); }}
        />
      )}
      {editItem && (
        <ModalEdit
          item={editItem}
          onClose={() => setEditItem(null)}
          onSaved={() => { setEditItem(null); load(); }}
        />
      )}
      {viewItem && (
        <ModalView
          item={viewItem}
          onClose={() => setViewItem(null)}
        />
      )}
    </>
  );
}
