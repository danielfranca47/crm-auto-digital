import { useEffect, useRef, useState } from 'react';
import { api, type KnowledgeIngestStatus } from '@/services/api';
import { ApiError } from '@/lib/api-client';
import type { KnowledgeCategory } from '@/types/agente';

// ─── Constantes (espelham os limites do backend) ──────────────

const ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.webp', '.csv', '.xlsx', '.txt'];
const IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.webp']);
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_SOURCES = 6;
const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;

const REASON_LABELS: Record<string, string> = {
  extensao_nao_suportada: 'formato não suportado',
  arquivo_muito_grande: 'arquivo muito grande',
  arquivo_nao_enviado: 'arquivo não enviado',
  sem_texto_extraivel: 'sem texto extraível (se for PDF escaneado, envie como imagem)',
  url_vazia: 'URL vazia',
  openai_api_key_ausente: 'leitura de imagem indisponível no servidor',
};

function reasonLabel(reason?: string | null): string {
  if (!reason) return 'falha ao processar';
  for (const [key, label] of Object.entries(REASON_LABELS)) {
    if (reason.startsWith(key)) return label;
  }
  if (reason.startsWith('falha_scraping')) return 'não foi possível ler o site';
  if (reason.startsWith('falha_leitura_pdf')) return 'não foi possível ler o PDF';
  if (reason.startsWith('falha_vision')) return 'não foi possível ler a imagem';
  return 'falha ao processar';
}

type LocalSource =
  | { id: number; kind: 'file'; file: File; description: string; error?: string }
  | { id: number; kind: 'url'; url: string; description: string; error?: string };

type Phase = 'edit' | 'processing' | 'done' | 'error';

// ─── Componente ───────────────────────────────────────────────

export function KnowledgeIngestPanel({
  categories,
  context,
  onFinished,
}: {
  /** Categorias guiadas do template (key/label/description/importance) enviadas ao classificador */
  categories: KnowledgeCategory[];
  context: { niche?: string; audience?: string; offer?: string };
  /** Chamado ao concluir, com as keys das categorias preenchidas pela IA */
  onFinished: (coveredKeys: string[]) => void;
}) {
  const [sources, setSources] = useState<LocalSource[]>([]);
  const [urlInput, setUrlInput] = useState('');
  const [phase, setPhase] = useState<Phase>('edit');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [status, setStatus] = useState<KnowledgeIngestStatus | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const nextId = useRef(1);
  const pollRef = useRef<{ timer: ReturnType<typeof setTimeout> | null; cancelled: boolean }>({
    timer: null,
    cancelled: false,
  });

  useEffect(() => {
    const poll = pollRef.current;
    return () => {
      poll.cancelled = true;
      if (poll.timer) clearTimeout(poll.timer);
    };
  }, []);

  const labelByKey = new Map(categories.map(c => [c.key, c.label]));

  function addFiles(list: FileList | null) {
    if (!list) return;
    setSources(prev => {
      const next = [...prev];
      for (const file of Array.from(list)) {
        if (next.length >= MAX_SOURCES) break;
        const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase();
        let error: string | undefined;
        if (!ALLOWED_EXTENSIONS.includes(ext)) {
          error = 'formato não suportado';
        } else if (file.size > (IMAGE_EXTENSIONS.has(ext) ? MAX_IMAGE_BYTES : MAX_FILE_BYTES)) {
          error = `arquivo acima de ${IMAGE_EXTENSIONS.has(ext) ? 5 : 10}MB`;
        } else if (next.some(s => s.kind === 'file' && s.file.name === file.name)) {
          error = 'arquivo duplicado no lote';
        }
        next.push({ id: nextId.current++, kind: 'file', file, description: '', error });
      }
      return next;
    });
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function addUrl() {
    const url = urlInput.trim();
    if (!url || sources.length >= MAX_SOURCES) return;
    setSources(prev => [...prev, { id: nextId.current++, kind: 'url', url, description: '' }]);
    setUrlInput('');
  }

  function removeSource(id: number) {
    setSources(prev => prev.filter(s => s.id !== id));
  }

  function setDescription(id: number, description: string) {
    setSources(prev => prev.map(s => (s.id === id ? { ...s, description } : s)));
  }

  const validSources = sources.filter(s => !s.error);

  async function startProcessing() {
    if (validSources.length === 0) return;
    setPhase('processing');
    setErrorMsg(null);
    try {
      const files = validSources.filter(s => s.kind === 'file').map(s => (s as { file: File }).file);
      const meta = {
        sources: validSources.map(s =>
          s.kind === 'file'
            ? { kind: 'file' as const, filename: s.file.name, description: s.description || undefined }
            : { kind: 'url' as const, url: s.url, description: s.description || undefined }
        ),
        context,
        categories: categories.map(c => ({
          key: c.key,
          label: c.label,
          description: c.description,
          importance: c.importance,
        })),
      };
      const created = await api.crm.ingestKnowledge(files, meta);
      pollStatus(created.job_id, Date.now());
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setErrorMsg(err.message || 'Limite semanal de importações atingido. Atualize seu plano.');
        setPhase('error');
        return;
      }
      const detail = (err as { message?: string })?.message ?? '';
      setErrorMsg(
        detail.includes('409') || detail.toLowerCase().includes('andamento')
          ? 'Já existe uma importação em andamento. Aguarde a conclusão.'
          : 'Não foi possível iniciar o processamento. Tente novamente.'
      );
      setPhase('error');
    }
  }

  function pollStatus(jobId: number, startedAt: number) {
    const poll = pollRef.current;
    const tick = async () => {
      if (poll.cancelled) return;
      if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
        setErrorMsg('O processamento demorou mais que o esperado. Recarregue a página em alguns minutos.');
        setPhase('error');
        return;
      }
      try {
        const s = await api.crm.getKnowledgeIngestStatus(jobId);
        if (poll.cancelled) return;
        if (s.status === 'completed') {
          setStatus(s);
          setPhase('done');
          return;
        }
        if (s.status === 'failed') {
          setErrorMsg('O processamento falhou. Tente novamente com outros materiais.');
          setPhase('error');
          return;
        }
      } catch {
        /* erro transitório de rede — continua o polling */
      }
      poll.timer = setTimeout(tick, POLL_INTERVAL_MS);
    };
    poll.timer = setTimeout(tick, POLL_INTERVAL_MS);
  }

  // ─── Render: processando ────────────────────────────────────

  if (phase === 'processing') {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0' }}>
        <div className="font-display" style={{ fontSize: 17, color: 'var(--o-text)', marginBottom: 10 }}>
          Processando seus materiais…
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--o-sub)', lineHeight: 1.6, maxWidth: 420, margin: '0 auto' }}>
          A IA está lendo os arquivos e páginas enviados e preenchendo as seções da base de
          conhecimento que eles cobrirem. Isso costuma levar menos de um minuto.
        </div>
        <div className="font-mono-orion" style={{ fontSize: 9, letterSpacing: 2, color: 'var(--o-dim)', marginTop: 18 }}>
          EXTRAINDO → CLASSIFICANDO → GRAVANDO
        </div>
      </div>
    );
  }

  // ─── Render: erro ───────────────────────────────────────────

  if (phase === 'error') {
    return (
      <div style={{ textAlign: 'center', padding: '24px 0' }}>
        <div style={{ fontSize: 13, color: 'var(--o-hot)', marginBottom: 16 }}>{errorMsg}</div>
        <button className="o-btn" onClick={() => setPhase('edit')}>← Voltar aos materiais</button>
      </div>
    );
  }

  // ─── Render: resumo ─────────────────────────────────────────

  if (phase === 'done' && status?.result) {
    const covered = status.result.covered ?? [];
    const uncovered = status.result.uncovered ?? [];
    const skipped = status.result.skipped_existing ?? [];
    const failedSources = (status.result.sources ?? []).filter(s => s.status === 'failed');

    return (
      <div>
        <div className="font-display" style={{ fontSize: 17, color: 'var(--o-text)', marginBottom: 14 }}>
          Resultado da importação
        </div>

        {covered.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-active)', marginBottom: 8 }}>
              ✓ Preenchidas pela IA ({covered.length})
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {covered.map(c => (
                <div key={c.category} style={{ padding: '8px 12px', background: 'var(--o-b0)', border: '1px solid var(--o-active-b)', borderRadius: 4 }}>
                  <div style={{ fontSize: 12.5, color: 'var(--o-text)', fontWeight: 500 }}>
                    {labelByKey.get(c.category) ?? c.category}
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {c.preview}…
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {covered.length === 0 && (
          <div style={{ fontSize: 12.5, color: 'var(--o-sub)', marginBottom: 16 }}>
            Os materiais enviados não cobriram nenhuma seção nova da base.
          </div>
        )}

        {skipped.length > 0 && (
          <div style={{ fontSize: 11.5, color: 'var(--o-dim)', marginBottom: 12 }}>
            Já preenchidas antes (mantidas sem alteração): {skipped.map(k => labelByKey.get(k) ?? k).join(', ')}
          </div>
        )}

        {uncovered.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>
              Ficaram pendentes ({uncovered.length})
            </div>
            <div style={{ fontSize: 12, color: 'var(--o-sub)', lineHeight: 1.7 }}>
              {uncovered.map(k => labelByKey.get(k) ?? k).join(' · ')}
            </div>
          </div>
        )}

        {failedSources.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-hot)', marginBottom: 6 }}>
              Fontes com falha
            </div>
            {failedSources.map((s, i) => (
              <div key={i} style={{ fontSize: 11.5, color: 'var(--o-sub)' }}>
                {s.filename ?? s.url}: {reasonLabel(s.reason)}
              </div>
            ))}
          </div>
        )}

        <button
          className="o-btn o-btn-primary"
          onClick={() => onFinished(covered.map(c => c.category))}
        >
          Continuar →
        </button>
      </div>
    );
  }

  // ─── Render: edição do lote ─────────────────────────────────

  return (
    <div>
      <div style={{ fontSize: 12.5, color: 'var(--o-sub)', lineHeight: 1.6, marginBottom: 14 }}>
        Envie materiais do seu negócio — PDF, imagem (foto de tabela de preços, cartaz), planilha,
        texto ou o link do seu site. A IA lê tudo e preenche sozinha as seções da base de
        conhecimento que os materiais cobrirem. Adicione uma descrição a cada fonte para ajudar
        (ex.: “minha tabela de preços”).
      </div>

      {/* Fontes adicionadas */}
      {sources.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 14 }}>
          {sources.map(s => (
            <div
              key={s.id}
              style={{
                padding: '10px 12px', background: 'var(--o-b0)', borderRadius: 4,
                border: `1px solid ${s.error ? 'var(--o-hot-b)' : 'var(--o-b1)'}`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, flexShrink: 0 }}>{s.kind === 'url' ? '🔗' : '📄'}</span>
                <span style={{ fontSize: 12.5, color: 'var(--o-text)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {s.kind === 'file' ? s.file.name : s.url}
                </span>
                <button
                  onClick={() => removeSource(s.id)}
                  style={{ background: 'none', border: 'none', color: 'var(--o-dim)', cursor: 'pointer', fontSize: 13, padding: 2 }}
                  title="Remover fonte"
                >
                  ✕
                </button>
              </div>
              {s.error ? (
                <div style={{ fontSize: 11, color: 'var(--o-hot)', marginTop: 4 }}>{s.error}</div>
              ) : (
                <input
                  className="o-input"
                  style={{ marginTop: 8, fontSize: 12 }}
                  placeholder="O que é este material? (ex.: minha tabela de preços)"
                  value={s.description}
                  onChange={e => setDescription(s.id, e.target.value)}
                />
              )}
            </div>
          ))}
        </div>
      )}

      {/* Adicionar fontes */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 6 }}>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ALLOWED_EXTENSIONS.join(',')}
          style={{ display: 'none' }}
          onChange={e => addFiles(e.target.files)}
        />
        <button
          className="o-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={sources.length >= MAX_SOURCES}
        >
          + Adicionar arquivos
        </button>
        <input
          className="o-input"
          style={{ flex: 1, minWidth: 180 }}
          placeholder="https://seusite.com"
          value={urlInput}
          onChange={e => setUrlInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') addUrl(); }}
          disabled={sources.length >= MAX_SOURCES}
        />
        <button className="o-btn" onClick={addUrl} disabled={!urlInput.trim() || sources.length >= MAX_SOURCES}>
          + URL
        </button>
      </div>
      <div style={{ fontSize: 10.5, color: 'var(--o-dim)', marginBottom: 16 }}>
        Até {MAX_SOURCES} fontes por lote · PDF, JPG, PNG, WEBP, CSV, XLSX, TXT · máx. 10MB (imagens 5MB)
      </div>

      <button
        className="o-btn o-btn-primary"
        onClick={startProcessing}
        disabled={validSources.length === 0}
      >
        ✦ Processar com IA
      </button>
    </div>
  );
}
