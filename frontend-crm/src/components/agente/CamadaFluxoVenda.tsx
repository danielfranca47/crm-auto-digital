import { useState, useMemo, useEffect } from 'react';
import { api } from '@/services/api';
import type { KnowledgeItem, KnowledgeMediaItem } from '@/services/api';
import type {
  AgentConfig,
  SalesFlow,
  SalesFlowBlock,
  SalesFlowBlockTypeId,
  SalesFlowPhaseData,
  SalesFlowPhaseId,
} from '@/types/agente';
import {
  SALES_FLOW_PHASE_ID_LABELS,
  SALES_FLOW_BLOCK_CATEGORIES,
  SALES_FLOW_PHASES_BY_AGENT_MODE,
} from '@/types/agente';

interface Props {
  config: AgentConfig;
  onUpdate: (partial: Partial<AgentConfig>) => void;
}

// ─── Constants ────────────────────────────────────────────────

const BLOCK_META: Record<SalesFlowBlockTypeId, { icon: string; color: string; desc: string }> = {
  kw_trigger:       { icon: '💬', color: '#fbbf24', desc: 'Dispara ao detetar palavra-chave do lead' },
  phase_trigger:    { icon: '🚀', color: '#fbbf24', desc: 'Dispara automaticamente ao entrar na fase' },
  no_reply_trigger: { icon: '🔕', color: '#fbbf24', desc: 'Dispara se o lead não responder em X tempo' },
  intent_trigger:   { icon: '🧠', color: '#fbbf24', desc: 'Dispara quando a IA deteta uma intenção' },
  orientacao:       { icon: '🧭', color: '#6ee7b7', desc: 'Instrução injetada no contexto do agente' },
  mensagem:         { icon: '✉️', color: '#38bdf8', desc: 'Mensagem de texto fixo enviada ao lead' },
  midia:            { icon: '🎵', color: '#a78bfa', desc: 'Envio real de ficheiro (áudio/imagem/doc)' },
  avancar_fase:     { icon: '➡️', color: '#34d399', desc: 'Move o lead para outra fase automaticamente' },
  webhook:          { icon: '🌐', color: '#f472b6', desc: 'Chamada HTTP a sistema externo' },
  condicao:         { icon: '🔀', color: '#fb923c', desc: 'Cria dois caminhos baseados numa condição' },
  espera:           { icon: '⏳', color: '#94a3b8', desc: 'Pausa o fluxo por um tempo definido' },
};

const BLOCK_TYPE_LABELS: Record<SalesFlowBlockTypeId, string> = {
  kw_trigger:       'Palavra-chave',
  phase_trigger:    'Fase iniciada',
  no_reply_trigger: 'Sem resposta',
  intent_trigger:   'Intenção IA',
  orientacao:       'Orientação ao Agente',
  mensagem:         'Mensagem fixa',
  midia:            'Enviar Mídia',
  avancar_fase:     'Avançar Fase',
  webhook:          'Webhook / API',
  condicao:         'Condição',
  espera:           'Espera',
};

const PHASE_COLORS: Record<SalesFlowPhaseId, string> = {
  p0: '#10b981', p1: '#38bdf8', p2: '#60a5fa',
  p3a: '#a78bfa', p3b: '#c084fc',
  p4: '#fb923c', p5: '#f472b6',
};

const PHASE_LABEL_SHORT: Record<SalesFlowPhaseId, string> = {
  p0: 'Fase 0', p1: 'Fase 1', p2: 'Fase 2',
  p3a: 'Fase 3A', p3b: 'Fase 3B',
  p4: 'Fase 4', p5: 'Fase 5',
};

const PHASE_DESC: Record<SalesFlowPhaseId, string> = {
  p0:  'Primeiro contacto — recepção e cumprimento',
  p1:  'Recolha de dados: faturamento, setor, decisor, orçamento',
  p2:  'Apresentação do produto/serviço e proposta de valor',
  p3a: 'Lead quer agendar mas não confirmou data/hora específica',
  p3b: 'Lead confirmou data e hora — registo e confirmação',
  p4:  'Reengajar leads que não responderam ou confirmaram',
  p5:  'Converter o lead em cliente — proposta final',
};

// ─── Helpers ──────────────────────────────────────────────────

function flowOf(config: AgentConfig): SalesFlow {
  return config.sales_flow ?? { enabled: true, nodes: [] };
}

const ALL_PHASE_IDS: SalesFlowPhaseId[] = ['p0', 'p1', 'p2', 'p3a', 'p3b', 'p4', 'p5'];

function initPhases(sf: SalesFlow): SalesFlowPhaseData[] {
  if (!sf.phases?.length) return ALL_PHASE_IDS.map(id => ({ id, blocks: [] }));
  return ALL_PHASE_IDS.map(id => sf.phases!.find(p => p.id === id) ?? { id, blocks: [] });
}

function emptyBlock(typeId: SalesFlowBlockTypeId): SalesFlowBlock {
  return { id: crypto.randomUUID(), typeId };
}

function blockSummary(block: SalesFlowBlock): string {
  const kws = (block.keywords || '').split(',').map(k => k.trim()).filter(Boolean);
  switch (block.typeId) {
    case 'kw_trigger':       return kws.length ? `"${kws.slice(0, 3).join('", "')}"` : '—';
    case 'phase_trigger':    return 'Auto ao entrar';
    case 'no_reply_trigger': return block.wait_value ? `Sem resposta: ${block.wait_value} ${block.wait_unit || 'horas'}` : '—';
    case 'intent_trigger':   return (block.intent || '').slice(0, 55) || '—';
    case 'orientacao':       return (block.content || '').slice(0, 60) || '—';
    case 'mensagem':         return `"${(block.content || '').slice(0, 55)}"`;
    case 'midia':            return block.media_type ? `${block.media_type}${block.caption ? ': ' + block.caption.slice(0, 30) : ''}` : '—';
    case 'avancar_fase':     return block.target_phase ? `→ ${SALES_FLOW_PHASE_ID_LABELS[block.target_phase]}` : '—';
    case 'webhook':          return (block.url || '').slice(0, 50) || '—';
    case 'condicao':         return (block.condition || '').slice(0, 50) || '—';
    case 'espera':           return block.wait_value ? `${block.wait_value} ${block.wait_unit || 'horas'}` : '—';
    default:                 return '';
  }
}

// ─── MediaPreviewChip ─────────────────────────────────────────

function MediaPreviewChip({ media }: { media: Pick<KnowledgeMediaItem, 'media_url' | 'media_type'> }) {
  const { media_url, media_type } = media;
  const isImage = media_type === 'image' || /\.(jpg|jpeg|png|webp|gif)$/i.test(media_url);
  const icon = media_type === 'pdf' ? '📄' : media_type === 'video' ? '🎬'
    : (media_type === 'audio' || media_type === 'myaudio' || media_type === 'ptt') ? '🎵' : '📎';
  if (isImage) return (
    <img src={media_url} alt="" style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 4, border: '1px solid var(--o-b1)' }}
      onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
  );
  return (
    <div style={{ width: 40, height: 40, borderRadius: 4, border: '1px solid var(--o-b1)', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--o-bg2)', fontSize: 18 }}>
      {icon}
    </div>
  );
}

// ─── BlockForm ────────────────────────────────────────────────

function BlockForm({ block, setBlock, knowledgeItems }: {
  block: SalesFlowBlock;
  setBlock: (b: SalesFlowBlock) => void;
  knowledgeItems: KnowledgeItem[];
}) {
  function set<K extends keyof SalesFlowBlock>(k: K, v: SalesFlowBlock[K]) {
    setBlock({ ...block, [k]: v });
  }

  const allMedia = useMemo(() => {
    const items: { item: KnowledgeItem; media: KnowledgeMediaItem }[] = [];
    for (const ki of knowledgeItems) {
      for (const m of ki.media_items) items.push({ item: ki, media: m });
    }
    return items;
  }, [knowledgeItems]);

  const phaseOptions: SalesFlowPhaseId[] = ['p0', 'p1', 'p2a', 'p2b', 'p3', 'p4'];

  switch (block.typeId) {
    case 'kw_trigger':
      return (
        <>
          <div className="o-field">
            <label className="o-field-label">Palavras-chave (separadas por vírgula) *</label>
            <input className="o-input" placeholder="Ex: preço, valor, quanto custa"
              value={block.keywords || ''} onChange={e => set('keywords', e.target.value)} />
          </div>
          <div className="o-field">
            <label className="o-field-label">Tipo de correspondência</label>
            <select className="o-input" value={block.match || 'contains'} onChange={e => set('match', e.target.value)}>
              <option value="contains">Contém</option>
              <option value="exact">Exato</option>
              <option value="starts_with">Começa com</option>
            </select>
          </div>
          <div className="o-field" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" id="kw-fire-once" checked={!!block.fire_once}
              onChange={e => set('fire_once', e.target.checked)} style={{ cursor: 'pointer' }} />
            <label htmlFor="kw-fire-once" style={{ cursor: 'pointer', fontSize: 12.5 }}>
              Disparar apenas uma vez por lead
            </label>
          </div>
        </>
      );

    case 'phase_trigger':
      return (
        <div style={{ fontSize: 12.5, color: 'var(--o-sub)', padding: '8px 0', lineHeight: 1.6 }}>
          Este gatilho dispara automaticamente quando o lead entra nesta fase. Não requer configuração adicional.
        </div>
      );

    case 'no_reply_trigger':
      return (
        <>
          <div className="o-field">
            <label className="o-field-label">Aguardar *</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input className="o-input" type="number" min="1" placeholder="24" style={{ flex: 1 }}
                value={block.wait_value || ''} onChange={e => set('wait_value', e.target.value)} />
              <select className="o-input" style={{ flex: 1 }} value={block.wait_unit || 'hours'} onChange={e => set('wait_unit', e.target.value)}>
                <option value="minutes">minutos</option>
                <option value="hours">horas</option>
                <option value="days">dias</option>
              </select>
            </div>
          </div>
          <div className="o-field">
            <label className="o-field-label">Nota (opcional)</label>
            <input className="o-input" placeholder="Ex: Lead parou de responder após a proposta"
              value={block.note || ''} onChange={e => set('note', e.target.value)} />
          </div>
        </>
      );

    case 'intent_trigger':
      return (
        <>
          <div className="o-field">
            <label className="o-field-label">Intenção a detetar *</label>
            <input className="o-input" placeholder="Ex: pedir preço, demonstrar hesitação"
              value={block.intent || ''} onChange={e => set('intent', e.target.value)} />
          </div>
          <div className="o-field">
            <label className="o-field-label">Instrução ao agente (opcional)</label>
            <textarea className="o-input" rows={3} placeholder="Ex: Se o lead hesitar, usar argumento de ROI"
              value={block.note || ''} onChange={e => set('note', e.target.value)} style={{ resize: 'vertical' }} />
          </div>
          <div className="o-field" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" id="intent-fire-once" checked={!!block.fire_once}
              onChange={e => set('fire_once', e.target.checked)} style={{ cursor: 'pointer' }} />
            <label htmlFor="intent-fire-once" style={{ cursor: 'pointer', fontSize: 12.5 }}>
              Disparar apenas uma vez por lead
            </label>
          </div>
        </>
      );

    case 'orientacao':
      return (
        <>
          <div className="o-field">
            <label className="o-field-label">Instrução para o agente *</label>
            <div className="o-field-hint">Texto injetado no contexto do agente com alta prioridade.</div>
            <textarea className="o-input" rows={5} placeholder="Ex: O lead mencionou orçamento limitado. Apresente ROI antes de repetir o preço."
              value={block.content || ''} onChange={e => set('content', e.target.value)}
              style={{ resize: 'vertical', minHeight: 110 }} />
          </div>
          <div className="o-field">
            <label className="o-field-label">Prioridade</label>
            <select className="o-input" value={block.priority || 'normal'} onChange={e => set('priority', e.target.value)}>
              <option value="normal">Normal</option>
              <option value="high">Alta</option>
              <option value="critical">Crítica</option>
            </select>
          </div>
        </>
      );

    case 'mensagem':
      return (
        <>
          <div className="o-field">
            <label className="o-field-label">Texto da mensagem *</label>
            <div className="o-field-hint">Enviado diretamente ao lead — não gerado pela IA.</div>
            <textarea className="o-input" rows={4} placeholder="Ex: Olá! Preparamos uma proposta especial para si."
              value={block.content || ''} onChange={e => set('content', e.target.value)}
              style={{ resize: 'vertical' }} />
          </div>
          <div className="o-field">
            <label className="o-field-label">Canal</label>
            <select className="o-input" value={block.channel || 'whatsapp'} onChange={e => set('channel', e.target.value)}>
              <option value="whatsapp">WhatsApp</option>
              <option value="all">Todos</option>
            </select>
          </div>
        </>
      );

    case 'midia':
      return (
        <>
          <div className="o-field">
            <label className="o-field-label">Selecione o ficheiro *</label>
            <div className="o-field-hint">Escolha um ficheiro da base de conhecimento.</div>
            {allMedia.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--o-sub)', padding: '8px 0' }}>
                Nenhum ficheiro encontrado na base de conhecimento.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 240, overflowY: 'auto' }}>
                {allMedia.map(({ item, media }) => {
                  const selected = block.media_item_id === media.id;
                  return (
                    <div key={media.id}
                      onClick={() => setBlock({ ...block, media_item_id: media.id, media_url: media.media_url, media_type: media.media_type })}
                      style={{
                        display: 'flex', gap: 10, alignItems: 'center', padding: '8px 10px',
                        borderRadius: 8, cursor: 'pointer',
                        border: `1.5px solid ${selected ? 'var(--o-active)' : 'var(--o-b1)'}`,
                        background: selected ? 'color-mix(in srgb, var(--o-active) 8%, transparent)' : 'var(--o-bg2)',
                        transition: 'all .15s',
                      }}>
                      <MediaPreviewChip media={media} />
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                        <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--o-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {item.title || 'Sem título'}
                        </span>
                        <span style={{ fontSize: 11, color: 'var(--o-sub)' }}>
                          {media.media_type} · {item.category || 'sem categoria'}
                        </span>
                      </div>
                      {selected && <span style={{ marginLeft: 'auto', fontSize: 16, color: 'var(--o-active)' }}>✓</span>}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <div className="o-field">
            <label className="o-field-label">Legenda (opcional)</label>
            <input className="o-input" placeholder="Texto que acompanha o envio"
              value={block.caption || ''} onChange={e => set('caption', e.target.value)} />
          </div>
        </>
      );

    case 'avancar_fase':
      return (
        <>
          <div className="o-field">
            <label className="o-field-label">Fase de destino *</label>
            <select className="o-input" value={block.target_phase || ''} onChange={e => set('target_phase', e.target.value as SalesFlowPhaseId)}>
              <option value="">— Selecione —</option>
              {phaseOptions.map(id => <option key={id} value={id}>{SALES_FLOW_PHASE_ID_LABELS[id]}</option>)}
            </select>
          </div>
          <div className="o-field">
            <label className="o-field-label">Nota (opcional)</label>
            <input className="o-input" placeholder="Ex: Mover após confirmar interesse"
              value={block.note || ''} onChange={e => set('note', e.target.value)} />
          </div>
        </>
      );

    case 'webhook':
      return (
        <>
          <div className="o-field">
            <label className="o-field-label">URL do endpoint *</label>
            <input className="o-input" placeholder="https://..."
              value={block.url || ''} onChange={e => set('url', e.target.value)} />
          </div>
          <div className="o-field">
            <label className="o-field-label">Método</label>
            <select className="o-input" value={block.method || 'POST'} onChange={e => set('method', e.target.value)}>
              <option value="POST">POST</option>
              <option value="GET">GET</option>
              <option value="PUT">PUT</option>
            </select>
          </div>
          <div className="o-field">
            <label className="o-field-label">O que enviar / contexto</label>
            <textarea className="o-input" rows={3} placeholder="Ex: Enviar dados do lead ao agendar"
              value={block.note || ''} onChange={e => set('note', e.target.value)} style={{ resize: 'vertical' }} />
          </div>
        </>
      );

    case 'condicao':
      return (
        <>
          <div className="o-field">
            <label className="o-field-label">Condição a avaliar *</label>
            <input className="o-input" placeholder="Ex: lead informou data e hora específica"
              value={block.condition || ''} onChange={e => set('condition', e.target.value)} />
          </div>
          <div className="o-field">
            <label className="o-field-label">Caminho SIM → ação</label>
            <input className="o-input" placeholder="Ex: Avançar para Fase 2B"
              value={block.branch_yes || ''} onChange={e => set('branch_yes', e.target.value)} />
          </div>
          <div className="o-field">
            <label className="o-field-label">Caminho NÃO → ação</label>
            <input className="o-input" placeholder="Ex: Permanecer em Fase 2A"
              value={block.branch_no || ''} onChange={e => set('branch_no', e.target.value)} />
          </div>
        </>
      );

    case 'espera':
      return (
        <>
          <div className="o-field">
            <label className="o-field-label">Aguardar *</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input className="o-input" type="number" min="1" placeholder="24" style={{ flex: 1 }}
                value={block.wait_value || ''} onChange={e => set('wait_value', e.target.value)} />
              <select className="o-input" style={{ flex: 1 }} value={block.wait_unit || 'hours'} onChange={e => set('wait_unit', e.target.value)}>
                <option value="minutes">minutos</option>
                <option value="hours">horas</option>
                <option value="days">dias</option>
              </select>
            </div>
          </div>
          <div className="o-field">
            <label className="o-field-label">Motivo / contexto</label>
            <input className="o-input" placeholder="Ex: Aguardar resposta antes de follow up"
              value={block.note || ''} onChange={e => set('note', e.target.value)} />
          </div>
        </>
      );

    default: return null;
  }
}

// ─── BlockModal ───────────────────────────────────────────────

function BlockModal({ phaseId, initial, knowledgeItems, onSave, onClose }: {
  phaseId: SalesFlowPhaseId;
  initial: SalesFlowBlock | null;
  knowledgeItems: KnowledgeItem[];
  onSave: (b: SalesFlowBlock) => void;
  onClose: () => void;
}) {
  const isEdit = !!initial;
  const [activeCat, setActiveCat] = useState<'trigger' | 'action' | 'logic'>(
    initial ? (SALES_FLOW_BLOCK_CATEGORIES.find(c => c.types.includes(initial.typeId))?.id ?? 'action') : 'trigger'
  );
  const [selectedTypeId, setSelectedTypeId] = useState<SalesFlowBlockTypeId | null>(initial?.typeId ?? null);
  const [block, setBlock] = useState<SalesFlowBlock>(initial ?? { id: crypto.randomUUID(), typeId: 'phase_trigger' });

  const catDef = SALES_FLOW_BLOCK_CATEGORIES.find(c => c.id === activeCat)!;
  const phaseName = SALES_FLOW_PHASE_ID_LABELS[phaseId];

  function selectType(typeId: SalesFlowBlockTypeId) {
    setSelectedTypeId(typeId);
    setBlock(isEdit ? { ...block, typeId } : emptyBlock(typeId));
  }

  function handleSave() {
    if (!selectedTypeId) return;
    onSave(block);
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9000, display: 'flex', alignItems: 'flex-end', justifyContent: 'center', background: 'rgba(0,0,0,0.6)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{
        background: 'var(--o-bg)', border: '1px solid var(--o-b1)', borderRadius: '18px 18px 0 0',
        width: '100%', maxWidth: 560, maxHeight: '90vh', overflowY: 'auto',
        display: 'flex', flexDirection: 'column', gap: 0,
      }}>
        {/* Header */}
        <div style={{ padding: '20px 20px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--o-text)' }}>
              {isEdit ? 'Editar bloco' : 'Adicionar bloco'}
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginTop: 2 }}>
              {phaseName} — {SALES_FLOW_PHASE_ID_LABELS[phaseId]}
            </div>
          </div>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--o-sub)', padding: 4 }} onClick={onClose}>✕</button>
        </div>

        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Category tabs */}
          <div style={{ display: 'flex', gap: 6 }}>
            {SALES_FLOW_BLOCK_CATEGORIES.map(cat => {
              const isActive = cat.id === activeCat;
              const catColors: Record<string, string> = { trigger: '#fbbf24', action: '#6ee7b7', logic: '#fb923c' };
              return (
                <button key={cat.id}
                  onClick={() => { setActiveCat(cat.id); setSelectedTypeId(null); }}
                  style={{
                    padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                    border: `1px solid ${isActive ? catColors[cat.id] : 'var(--o-b1)'}`,
                    background: isActive ? `${catColors[cat.id]}22` : 'transparent',
                    color: isActive ? catColors[cat.id] : 'var(--o-sub)',
                    transition: 'all .15s',
                  }}>
                  {cat.label}
                </button>
              );
            })}
          </div>

          {/* Type grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {catDef.types.map(typeId => {
              const meta = BLOCK_META[typeId];
              const isSelected = selectedTypeId === typeId;
              return (
                <div key={typeId} onClick={() => selectType(typeId)}
                  style={{
                    borderRadius: 10, border: `1.5px solid ${isSelected ? meta.color : 'var(--o-b1)'}`,
                    background: isSelected ? `${meta.color}12` : 'var(--o-bg2)',
                    padding: '12px', cursor: 'pointer', transition: 'all .15s',
                    display: 'flex', gap: 10, alignItems: 'flex-start',
                  }}>
                  <span style={{ fontSize: 20, lineHeight: 1, flexShrink: 0 }}>{meta.icon}</span>
                  <div>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--o-text)', marginBottom: 2 }}>
                      {BLOCK_TYPE_LABELS[typeId]}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--o-sub)', lineHeight: 1.4 }}>{meta.desc}</div>
                    <span style={{
                      display: 'inline-block', fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                      letterSpacing: '0.06em', padding: '2px 5px', borderRadius: 4, marginTop: 4,
                      background: `${meta.color}22`, color: meta.color,
                    }}>
                      {activeCat === 'trigger' ? 'GATILHO' : activeCat === 'action' ? 'AÇÃO' : 'LÓGICA'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Form */}
          {selectedTypeId && (
            <div style={{ borderTop: '1px solid var(--o-b1)', paddingTop: 16, display: 'flex', flexDirection: 'column', gap: 0 }}>
              <BlockForm block={block} setBlock={setBlock} knowledgeItems={knowledgeItems} />
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '12px 20px 20px', display: 'flex', gap: 8, justifyContent: 'flex-end', borderTop: '1px solid var(--o-b1)' }}>
          <button className="o-btn" onClick={onClose}>Cancelar</button>
          <button className="o-btn o-btn-primary" onClick={handleSave} disabled={!selectedTypeId}
            style={{ opacity: selectedTypeId ? 1 : 0.45 }}>
            Salvar bloco
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── RuleBuilderModal ─────────────────────────────────────────

type RBStep = 'pick-trigger' | 'config-trigger' | 'rule-builder' | 'adding-block';

function RuleBuilderModal({ phaseId, knowledgeItems, onSave, onClose }: {
  phaseId: SalesFlowPhaseId;
  knowledgeItems: KnowledgeItem[];
  onSave: (blocks: SalesFlowBlock[]) => void;
  onClose: () => void;
}) {
  const [step, setStep] = useState<RBStep>('pick-trigger');
  const [triggerBlock, setTriggerBlock] = useState<SalesFlowBlock | null>(null);
  const [extraBlocks, setExtraBlocks] = useState<SalesFlowBlock[]>([]);
  const [addingCat, setAddingCat] = useState<'action' | 'logic' | null>(null);
  const [pendingTypeId, setPendingTypeId] = useState<SalesFlowBlockTypeId | null>(null);
  const [pendingBlock, setPendingBlock] = useState<SalesFlowBlock | null>(null);

  const phaseName = SALES_FLOW_PHASE_ID_LABELS[phaseId];
  const triggerCat = SALES_FLOW_BLOCK_CATEGORIES.find(c => c.id === 'trigger')!;

  function pickTriggerType(typeId: SalesFlowBlockTypeId) {
    setTriggerBlock(emptyBlock(typeId));
    setStep('config-trigger');
  }

  function startAddingBlock(cat: 'action' | 'logic') {
    setAddingCat(cat);
    setPendingTypeId(null);
    setPendingBlock(null);
    setStep('adding-block');
  }

  function pickPendingType(typeId: SalesFlowBlockTypeId) {
    setPendingTypeId(typeId);
    setPendingBlock(emptyBlock(typeId));
  }

  function confirmPendingBlock() {
    if (!pendingBlock) return;
    setExtraBlocks(prev => [...prev, pendingBlock]);
    setAddingCat(null);
    setPendingTypeId(null);
    setPendingBlock(null);
    setStep('rule-builder');
  }

  function cancelAddingBlock() {
    setAddingCat(null);
    setPendingTypeId(null);
    setPendingBlock(null);
    setStep('rule-builder');
  }

  function removeExtra(id: string) {
    setExtraBlocks(prev => prev.filter(b => b.id !== id));
  }

  function handleSave() {
    const allBlocks: SalesFlowBlock[] = [];
    if (triggerBlock) allBlocks.push(triggerBlock);
    allBlocks.push(...extraBlocks);
    if (!allBlocks.length) return;
    onSave(allBlocks);
  }

  const canSave = triggerBlock !== null || extraBlocks.length > 0;

  const stepTitles: Record<RBStep, string> = {
    'pick-trigger':   'Escolher gatilho',
    'config-trigger': 'Configurar gatilho',
    'rule-builder':   'Montar regra',
    'adding-block':   addingCat === 'action' ? 'Adicionar ação' : 'Adicionar lógica',
  };

  function renderContent() {
    if (step === 'pick-trigger') return (
      <>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--o-sub)' }}>
            Escolha o que ativa esta regra. O gatilho governa todas as ações que adicionar a seguir.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {triggerCat.types.map(typeId => {
              const meta = BLOCK_META[typeId];
              return (
                <div key={typeId} onClick={() => pickTriggerType(typeId)}
                  style={{
                    borderRadius: 10, border: '1.5px solid var(--o-b1)',
                    background: 'var(--o-bg2)', padding: '12px', cursor: 'pointer', transition: 'all .15s',
                    display: 'flex', gap: 10, alignItems: 'flex-start',
                  }}
                  onMouseEnter={e => { const el = e.currentTarget as HTMLDivElement; el.style.borderColor = meta.color; el.style.background = `${meta.color}10`; }}
                  onMouseLeave={e => { const el = e.currentTarget as HTMLDivElement; el.style.borderColor = 'var(--o-b1)'; el.style.background = 'var(--o-bg2)'; }}>
                  <span style={{ fontSize: 20, lineHeight: 1, flexShrink: 0 }}>{meta.icon}</span>
                  <div>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--o-text)', marginBottom: 2 }}>{BLOCK_TYPE_LABELS[typeId]}</div>
                    <div style={{ fontSize: 11, color: 'var(--o-sub)', lineHeight: 1.4 }}>{meta.desc}</div>
                    <span style={{ display: 'inline-block', fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', padding: '2px 5px', borderRadius: 4, marginTop: 4, background: `${meta.color}22`, color: meta.color }}>GATILHO</span>
                  </div>
                </div>
              );
            })}
          </div>
          <div onClick={() => { setTriggerBlock(null); setStep('rule-builder'); }}
            style={{
              borderRadius: 10, border: '1.5px dashed var(--o-b1)',
              background: 'transparent', padding: '11px 14px', cursor: 'pointer', transition: 'all .15s',
              display: 'flex', alignItems: 'center', gap: 10,
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--o-sub)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--o-b1)'; }}>
            <span style={{ fontSize: 16 }}>⚡</span>
            <div>
              <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--o-text)' }}>Sem gatilho — sempre ao entrar na fase</div>
              <div style={{ fontSize: 11, color: 'var(--o-sub)' }}>As ações disparam automaticamente quando o lead chega a esta fase</div>
            </div>
          </div>
        </div>
        <div style={{ padding: '12px 20px 20px', display: 'flex', gap: 8, justifyContent: 'flex-end', borderTop: '1px solid var(--o-b1)' }}>
          <button className="o-btn" onClick={onClose}>Cancelar</button>
        </div>
      </>
    );

    if (step === 'config-trigger' && triggerBlock) return (
      <>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 8, border: `1.5px solid ${BLOCK_META[triggerBlock.typeId].color}44`, background: `${BLOCK_META[triggerBlock.typeId].color}10` }}>
            <span style={{ fontSize: 18 }}>{BLOCK_META[triggerBlock.typeId].icon}</span>
            <div>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--o-text)' }}>{BLOCK_TYPE_LABELS[triggerBlock.typeId]}</div>
              <div style={{ fontSize: 11, color: 'var(--o-sub)' }}>{BLOCK_META[triggerBlock.typeId].desc}</div>
            </div>
          </div>
          <BlockForm block={triggerBlock} setBlock={b => setTriggerBlock(b)} knowledgeItems={knowledgeItems} />
        </div>
        <div style={{ padding: '12px 20px 20px', display: 'flex', gap: 8, justifyContent: 'space-between', borderTop: '1px solid var(--o-b1)' }}>
          <button className="o-btn" onClick={() => setStep('pick-trigger')}>← Voltar</button>
          <button className="o-btn o-btn-primary" onClick={() => setStep('rule-builder')}>Próximo →</button>
        </div>
      </>
    );

    if (step === 'rule-builder') return (
      <>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--o-sub)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Gatilho</div>
            {triggerBlock ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', borderRadius: 8, border: `1.5px solid ${BLOCK_META[triggerBlock.typeId].color}55`, background: `${BLOCK_META[triggerBlock.typeId].color}10` }}>
                <span style={{ fontSize: 16 }}>{BLOCK_META[triggerBlock.typeId].icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 11.5, fontWeight: 600, color: BLOCK_META[triggerBlock.typeId].color }}>{BLOCK_TYPE_LABELS[triggerBlock.typeId]}</div>
                  <div style={{ fontSize: 11, color: 'var(--o-sub)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{blockSummary(triggerBlock)}</div>
                </div>
              </div>
            ) : (
              <div style={{ padding: '9px 12px', borderRadius: 8, border: '1.5px dashed var(--o-b1)', fontSize: 12, color: 'var(--o-sub)' }}>
                ⚡ Sempre ao entrar na fase
              </div>
            )}
          </div>

          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--o-sub)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Ações / Lógica</div>
            {extraBlocks.length === 0 ? (
              <div style={{ padding: '9px 12px', borderRadius: 8, border: '1.5px dashed var(--o-b1)', fontSize: 12, color: 'var(--o-sub)', textAlign: 'center' }}>
                Nenhuma ação adicionada ainda
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {extraBlocks.map(b => {
                  const meta = BLOCK_META[b.typeId];
                  return (
                    <div key={b.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', borderRadius: 8, border: '1px solid var(--o-b1)', background: 'var(--o-bg2)' }}>
                      <span style={{ fontSize: 15 }}>{meta.icon}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: meta.color, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{BLOCK_TYPE_LABELS[b.typeId]}</div>
                        <div style={{ fontSize: 11, color: 'var(--o-sub)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{blockSummary(b)}</div>
                      </div>
                      <button style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 14, color: 'var(--o-sub)', padding: '2px 4px' }} onClick={() => removeExtra(b.id)}>✕</button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button className="o-btn" style={{ flex: 1, justifyContent: 'center', gap: 5, fontSize: 12 }} onClick={() => startAddingBlock('action')}>
              <span style={{ fontSize: 13 }}>+</span> Adicionar ação
            </button>
            <button className="o-btn" style={{ flex: 1, justifyContent: 'center', gap: 5, fontSize: 12 }} onClick={() => startAddingBlock('logic')}>
              <span style={{ fontSize: 13 }}>+</span> Adicionar lógica
            </button>
          </div>
        </div>
        <div style={{ padding: '12px 20px 20px', display: 'flex', gap: 8, justifyContent: 'space-between', borderTop: '1px solid var(--o-b1)' }}>
          <button className="o-btn" onClick={() => setStep(triggerBlock !== null ? 'config-trigger' : 'pick-trigger')}>← Voltar</button>
          <button className="o-btn o-btn-primary" onClick={handleSave} disabled={!canSave} style={{ opacity: canSave ? 1 : 0.45 }}>
            Salvar regra
          </button>
        </div>
      </>
    );

    if (step === 'adding-block' && addingCat) {
      const catDef = SALES_FLOW_BLOCK_CATEGORIES.find(c => c.id === addingCat)!;
      return (
        <>
          <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {catDef.types.map(typeId => {
                const meta = BLOCK_META[typeId];
                const isSelected = pendingTypeId === typeId;
                return (
                  <div key={typeId} onClick={() => pickPendingType(typeId)}
                    style={{
                      borderRadius: 10,
                      border: `1.5px solid ${isSelected ? meta.color : 'var(--o-b1)'}`,
                      background: isSelected ? `${meta.color}12` : 'var(--o-bg2)',
                      padding: '12px', cursor: 'pointer', transition: 'all .15s',
                      display: 'flex', gap: 10, alignItems: 'flex-start',
                    }}>
                    <span style={{ fontSize: 20, lineHeight: 1, flexShrink: 0 }}>{meta.icon}</span>
                    <div>
                      <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--o-text)', marginBottom: 2 }}>{BLOCK_TYPE_LABELS[typeId]}</div>
                      <div style={{ fontSize: 11, color: 'var(--o-sub)', lineHeight: 1.4 }}>{meta.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>
            {pendingTypeId && pendingBlock && (
              <div style={{ borderTop: '1px solid var(--o-b1)', paddingTop: 16 }}>
                <BlockForm block={pendingBlock} setBlock={b => setPendingBlock(b)} knowledgeItems={knowledgeItems} />
              </div>
            )}
          </div>
          <div style={{ padding: '12px 20px 20px', display: 'flex', gap: 8, justifyContent: 'space-between', borderTop: '1px solid var(--o-b1)' }}>
            <button className="o-btn" onClick={cancelAddingBlock}>Cancelar</button>
            <button className="o-btn o-btn-primary" onClick={confirmPendingBlock} disabled={!pendingTypeId} style={{ opacity: pendingTypeId ? 1 : 0.45 }}>
              Confirmar {addingCat === 'action' ? 'ação' : 'lógica'}
            </button>
          </div>
        </>
      );
    }

    return null;
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9000, display: 'flex', alignItems: 'flex-end', justifyContent: 'center', background: 'rgba(0,0,0,0.6)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{
        background: 'var(--o-bg)', border: '1px solid var(--o-b1)', borderRadius: '18px 18px 0 0',
        width: '100%', maxWidth: 560, maxHeight: '90vh', overflowY: 'auto',
        display: 'flex', flexDirection: 'column', gap: 0,
      }}>
        <div style={{ padding: '20px 20px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--o-text)' }}>{stepTitles[step]}</div>
            <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginTop: 2 }}>{phaseName}</div>
          </div>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: 'var(--o-sub)', padding: 4 }} onClick={onClose}>✕</button>
        </div>
        {renderContent()}
      </div>
    </div>
  );
}

// ─── PhaseSection ─────────────────────────────────────────────

function PhaseSection({ phase, onAddBlock, onEditBlock, onRemoveBlock, isActive = true }: {
  phase: SalesFlowPhaseData;
  onAddBlock: (phaseId: SalesFlowPhaseId) => void;
  onEditBlock: (phaseId: SalesFlowPhaseId, blockId: string) => void;
  onRemoveBlock: (phaseId: SalesFlowPhaseId, blockId: string) => void;
  isActive?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const { id, blocks } = phase;
  const color = PHASE_COLORS[id];
  const activeBlocks = blocks.length;

  return (
    <div style={{ borderRadius: 12, border: `1.5px solid ${color}30`, background: 'var(--o-bg)', overflow: 'hidden', opacity: isActive ? 1 : 0.4 }}>
      {/* Header */}
      <div onClick={() => setExpanded(v => !v)}
        style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', userSelect: 'none' }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0, boxShadow: isActive ? `0 0 6px ${color}` : 'none' }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 10.5, fontFamily: 'monospace', color, letterSpacing: '0.05em' }}>
              {PHASE_LABEL_SHORT[id]}
            </span>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--o-text)' }}>{SALES_FLOW_PHASE_ID_LABELS[id]}</span>
            {activeBlocks > 0 && (
              <span style={{
                fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 10,
                background: `${color}22`, color,
              }}>{activeBlocks} bloco{activeBlocks !== 1 ? 's' : ''}</span>
            )}
            {!isActive && (
              <span style={{
                fontSize: 9.5, fontWeight: 500, padding: '1px 7px', borderRadius: 10,
                background: 'var(--o-bg2)', color: 'var(--o-sub)', border: '1px solid var(--o-b1)',
              }}>Não ativo neste agente</span>
            )}
          </div>
          {!expanded && (
            <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginTop: 2, fontWeight: 300 }}>{PHASE_DESC[id]}</div>
          )}
        </div>
        <span style={{ fontSize: 13, color: 'var(--o-sub)', fontWeight: 300 }}>{expanded ? '▲' : '▼'}</span>
      </div>

      {/* Body */}
      {expanded && (
        <div style={{ borderTop: `1px solid ${color}20`, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Block list — agrupado por gatilho */}
          {(() => {
            const TRIGGER_IDS = new Set(['phase_trigger', 'kw_trigger', 'no_reply_trigger', 'intent_trigger']);
            type Group = { trigger: SalesFlowBlock | null; actions: SalesFlowBlock[] };
            const groups: Group[] = [];
            let cur: Group = { trigger: null, actions: [] };
            for (const b of blocks) {
              if (TRIGGER_IDS.has(b.typeId)) {
                if (cur.trigger !== null || cur.actions.length > 0) groups.push(cur);
                cur = { trigger: b, actions: [] };
              } else {
                cur.actions.push(b);
              }
            }
            if (cur.trigger !== null || cur.actions.length > 0) groups.push(cur);

            function BlockRow({ block }: { block: SalesFlowBlock }) {
              const meta = BLOCK_META[block.typeId];
              return (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  background: 'var(--o-bg2)', borderRadius: 8, padding: '9px 12px',
                  border: '1px solid var(--o-b1)',
                }}>
                  <span style={{ fontSize: 16, flexShrink: 0 }}>{meta.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                      <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: meta.color }}>
                        {block.typeId.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--o-sub)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {blockSummary(block)}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                    <button className="o-btn" style={{ fontSize: 10.5, padding: '3px 9px' }}
                      onClick={() => onEditBlock(id, block.id)}>Editar</button>
                    <button className="o-btn" style={{ fontSize: 10.5, padding: '3px 9px', color: 'var(--o-danger, #e05c5c)' }}
                      onClick={() => onRemoveBlock(id, block.id)}>✕</button>
                  </div>
                </div>
              );
            }

            return groups.map((group, gi) => (
              <div key={gi} style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {/* Gatilho (ou label implícito "sempre ao entrar") */}
                {group.trigger ? (
                  <BlockRow block={group.trigger} />
                ) : group.actions.length > 0 ? (
                  <div style={{ fontSize: 10, color: 'var(--o-sub)', fontWeight: 500, padding: '2px 4px 4px', letterSpacing: '0.04em' }}>
                    ⚡ Sempre ao entrar na fase
                  </div>
                ) : null}

                {/* Ações — indentadas com linha vertical */}
                {group.actions.length > 0 && (
                  <div style={{ display: 'flex', marginTop: 4 }}>
                    <div style={{
                      width: 2, flexShrink: 0, borderRadius: 2,
                      background: group.trigger ? BLOCK_META[group.trigger.typeId].color + '55' : 'var(--o-b1)',
                      marginLeft: 14, marginRight: 10,
                    }} />
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {group.actions.map(b => <BlockRow key={b.id} block={b} />)}
                    </div>
                  </div>
                )}
              </div>
            ));
          })()}

          {/* Add button */}
          <button className="o-btn"
            style={{ width: '100%', justifyContent: 'center', gap: 6, borderStyle: 'dashed', fontSize: 12.5 }}
            onClick={() => onAddBlock(id)}>
            <span style={{ fontSize: 15, lineHeight: 1 }}>+</span> Adicionar bloco nesta fase
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────

export function CamadaFluxoVenda({ config, onUpdate }: Props) {
  const sf = flowOf(config);
  const [phases, setPhases] = useState<SalesFlowPhaseData[]>(() => initPhases(sf));

  const rawMode = config.agent_mode ?? 'consultivo';
  const agentGroup: string = rawMode === 'sdr_scheduler' ? 'agenda'
                           : rawMode === 'closer'         ? 'direto'
                           : rawMode;
  const activePhasesForMode = SALES_FLOW_PHASES_BY_AGENT_MODE[agentGroup]
                           ?? SALES_FLOW_PHASES_BY_AGENT_MODE['agenda'];
  const [modal, setModal] = useState<{ phaseId: SalesFlowPhaseId; blockId: string | null } | null>(null);
  const [ruleBuilderPhaseId, setRuleBuilderPhaseId] = useState<SalesFlowPhaseId | null>(null);
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);

  useEffect(() => {
    api.crm.getKnowledgeList()
      .then(setKnowledgeItems)
      .catch(() => {});
  }, []);

  function updateFlow(newPhases: SalesFlowPhaseData[]) {
    setPhases(newPhases);
    onUpdate({ sales_flow: { ...sf, phases: newPhases } });
  }

  function openAdd(phaseId: SalesFlowPhaseId) {
    setRuleBuilderPhaseId(phaseId);
  }

  function openEdit(phaseId: SalesFlowPhaseId, blockId: string) {
    setModal({ phaseId, blockId });
  }

  function removeBlock(phaseId: SalesFlowPhaseId, blockId: string) {
    updateFlow(phases.map(p =>
      p.id === phaseId ? { ...p, blocks: p.blocks.filter(b => b.id !== blockId) } : p
    ));
  }

  function saveBlocks(phaseId: SalesFlowPhaseId, newBlocks: SalesFlowBlock[]) {
    if (!newBlocks.length) return;
    updateFlow(phases.map(p => {
      if (p.id !== phaseId) return p;
      return { ...p, blocks: [...p.blocks, ...newBlocks] };
    }));
    setRuleBuilderPhaseId(null);
  }

  function saveBlock(block: SalesFlowBlock) {
    if (!modal) return;
    const { phaseId, blockId } = modal;
    updateFlow(phases.map(p => {
      if (p.id !== phaseId) return p;
      if (blockId) {
        return { ...p, blocks: p.blocks.map(b => b.id === blockId ? block : b) };
      }
      return { ...p, blocks: [...p.blocks, block] };
    }));
    setModal(null);
  }

  const modalPhase = modal ? phases.find(p => p.id === modal.phaseId) : null;
  const modalInitial = modal?.blockId && modalPhase
    ? (modalPhase.blocks.find(b => b.id === modal.blockId) ?? null)
    : null;

  const totalBlocks = phases.reduce((sum, p) => sum + p.blocks.length, 0);
  const legacyCount = sf.nodes?.length ?? 0;

  return (
    <>
      {modal && modalPhase && (
        <BlockModal
          phaseId={modal.phaseId}
          initial={modalInitial}
          knowledgeItems={knowledgeItems}
          onSave={saveBlock}
          onClose={() => setModal(null)}
        />
      )}
      {ruleBuilderPhaseId && (
        <RuleBuilderModal
          phaseId={ruleBuilderPhaseId}
          knowledgeItems={knowledgeItems}
          onSave={(blocks) => saveBlocks(ruleBuilderPhaseId, blocks)}
          onClose={() => setRuleBuilderPhaseId(null)}
        />
      )}

      {/* Header com toggle global */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--o-text)' }}>
            Fluxo de Venda
            {totalBlocks > 0 && (
              <span style={{ marginLeft: 10, fontSize: 11.5, color: 'var(--o-sub)', fontWeight: 300 }}>
                {totalBlocks} bloco{totalBlocks !== 1 ? 's' : ''} configurado{totalBlocks !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--o-sub)', fontWeight: 300, marginTop: 3 }}>
            {sf.enabled ? 'Avaliando blocos em cada turno' : 'Desabilitado — nenhum bloco será avaliado'}
          </div>
        </div>
        <div className={`o-toggle ${sf.enabled ? 'on' : ''}`}
          onClick={() => onUpdate({ sales_flow: { ...sf, enabled: !sf.enabled } })} />
      </div>

      {/* Fases p0, p1, p2 — sempre visíveis */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 8 }}>
        {(['p0', 'p1', 'p2'] as SalesFlowPhaseId[]).map(id => {
          const phase = phases.find(p => p.id === id)!;
          return (
            <PhaseSection key={id} phase={phase}
              onAddBlock={openAdd} onEditBlock={openEdit} onRemoveBlock={removeBlock}
              isActive={activePhasesForMode.includes(id)} />
          );
        })}
      </div>

      {/* Grupo Fases de Agendamento (3A / 3B) — apenas para agenda/sdr_scheduler */}
      {agentGroup === 'agenda' && (
        <div style={{
          border: '1.5px solid #a78bfa30', borderRadius: 12, padding: '12px 12px 4px',
          marginBottom: 8, background: 'transparent',
        }}>
          <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#a78bfa', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>Fases de Agendamento (3A / 3B)</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <PhaseSection phase={phases.find(p => p.id === 'p3a')!}
              onAddBlock={openAdd} onEditBlock={openEdit} onRemoveBlock={removeBlock} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 14px' }}>
              <div style={{ width: 2, height: 24, background: 'var(--o-b1)', marginLeft: 12 }} />
              <span style={{ fontSize: 10.5, color: 'var(--o-sub)', fontWeight: 300 }}>→ confirma data e hora</span>
            </div>
            <PhaseSection phase={phases.find(p => p.id === 'p3b')!}
              onAddBlock={openAdd} onEditBlock={openEdit} onRemoveBlock={removeBlock} />
          </div>
        </div>
      )}

      {/* Fases p4 e p5 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
        {(['p4', 'p5'] as SalesFlowPhaseId[]).map(id => {
          const phase = phases.find(p => p.id === id)!;
          return (
            <PhaseSection key={id} phase={phase}
              onAddBlock={openAdd} onEditBlock={openEdit} onRemoveBlock={removeBlock}
              isActive={activePhasesForMode.includes(id)} />
          );
        })}
      </div>

      {/* Aviso de regras legadas */}
      {legacyCount > 0 && (
        <div style={{
          padding: '10px 14px', borderRadius: 8, fontSize: 12, color: 'var(--o-sub)', fontWeight: 300,
          background: 'var(--o-bg2)', border: '1px dashed var(--o-b1)', lineHeight: 1.6, marginBottom: 12,
        }}>
          <strong style={{ color: 'var(--o-warn)', fontWeight: 500 }}>⚠ {legacyCount} regra{legacyCount !== 1 ? 's' : ''} do sistema legado</strong>{' '}
          ainda ativas. O agente continuará a avaliá-las. Para gerir, utilize o novo sistema de fases acima.
        </div>
      )}

      {/* Info */}
      <div style={{
        padding: '12px 16px', borderRadius: 8, background: 'var(--o-bg2)', border: '1px solid var(--o-b1)',
        fontSize: 12, color: 'var(--o-sub)', fontWeight: 300, lineHeight: 1.65,
      }}>
        <strong style={{ color: 'var(--o-text)', fontWeight: 500 }}>Como funciona:</strong>{' '}
        Os blocos de cada fase são avaliados quando o lead entra nessa fase. Blocos de <em>Orientação</em> injetam instruções no agente;
        blocos de <em>Mídia</em> e <em>Mensagem</em> são enviados diretamente sem passar pelo LLM.
        Gatilhos de palavra-chave disparam apenas quando o lead escreve a palavra naquela fase.
      </div>
    </>
  );
}
