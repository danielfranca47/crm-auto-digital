import { useState } from 'react';
import type { AgentConfig, SalesFlow, SalesFlowNode, SalesFlowPhase, SalesFlowSignalKey, SalesFlowTriggerType } from '@/types/agente';
import {
  SALES_FLOW_PHASE_LABELS,
  SALES_FLOW_SIGNAL_LABELS,
  SALES_FLOW_SIGNAL_VALUES,
  SALES_FLOW_TRIGGER_LABELS,
} from '@/types/agente';

interface Props {
  config: AgentConfig;
  onUpdate: (partial: Partial<AgentConfig>) => void;
}

// ─── Helpers ─────────────────────────────────────────────────

function emptyNode(): SalesFlowNode {
  return {
    id: crypto.randomUUID(),
    label: '',
    enabled: true,
    trigger_phases: [],
    trigger_type: 'signal',
    trigger_signal: 'price_acceptance',
    trigger_value: null,
    trigger_keywords: [],
    trigger_field_key: null,
    trigger_field_value: null,
    action_instruction: '',
    action_media_category: null,
    priority: 0,
  };
}

function flowOf(config: AgentConfig): SalesFlow {
  return config.sales_flow ?? { enabled: true, nodes: [] };
}

function triggerSummary(node: SalesFlowNode): string {
  const phases = node.trigger_phases.map(p => SALES_FLOW_PHASE_LABELS[p]).join(', ');
  const phaseStr = phases ? `Em: ${phases}` : '';

  if (node.trigger_type === 'phase_entered') return phaseStr || 'Qualquer fase';
  if (node.trigger_type === 'signal') {
    const sig = node.trigger_signal ? SALES_FLOW_SIGNAL_LABELS[node.trigger_signal] : '—';
    const val = node.trigger_value
      ? SALES_FLOW_SIGNAL_VALUES[node.trigger_signal as SalesFlowSignalKey]?.find(v => v.value === node.trigger_value)?.label ?? node.trigger_value
      : '(qualquer)';
    return [phaseStr, `Sinal: ${sig} = ${val}`].filter(Boolean).join(' · ');
  }
  if (node.trigger_type === 'keyword') {
    const kws = node.trigger_keywords.slice(0, 3).join(', ');
    return [phaseStr, `Palavra: "${kws}"`].filter(Boolean).join(' · ');
  }
  if (node.trigger_type === 'qualification_field') {
    const f = node.trigger_field_key ?? '—';
    const v = node.trigger_field_value ? ` = "${node.trigger_field_value}"` : '';
    return [phaseStr, `Campo: ${f}${v}`].filter(Boolean).join(' · ');
  }
  return phaseStr || '—';
}

// ─── DrawerBase (padrão Orion) ────────────────────────────────

function DrawerBase({ title, sub, onClose, onSave, children }: {
  title: string; sub: string; onClose: () => void; onSave: () => void; children: React.ReactNode;
}) {
  return (
    <>
      <div className="o-drawer-overlay open" onClick={onClose} />
      <div className="o-drawer open">
        <div className="o-drawer-header">
          <div>
            <div className="font-display" style={{ fontSize: 20, fontWeight: 400, color: 'var(--o-text)' }}>{title}</div>
            <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginTop: 4, fontWeight: 300 }}>{sub}</div>
          </div>
          <button className="o-close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="o-drawer-body">{children}</div>
        <div className="o-drawer-footer">
          <button className="o-btn o-btn-primary" onClick={onSave}>Salvar</button>
          <button className="o-btn" onClick={onClose}>Cancelar</button>
        </div>
      </div>
    </>
  );
}

// ─── Drawer de criação/edição de node ────────────────────────

function DrawerNode({ node: initial, qualFields, onSave, onClose }: {
  node: SalesFlowNode;
  qualFields: { key: string; label: string }[];
  onSave: (n: SalesFlowNode) => void;
  onClose: () => void;
}) {
  const [node, setNode] = useState<SalesFlowNode>({ ...initial });
  const set = <K extends keyof SalesFlowNode>(k: K, v: SalesFlowNode[K]) =>
    setNode(prev => ({ ...prev, [k]: v }));

  const allPhases: SalesFlowPhase[] = ['qualification', 'apresentation', 'follow-up', 'closing'];

  function togglePhase(p: SalesFlowPhase) {
    const phases = node.trigger_phases.includes(p)
      ? node.trigger_phases.filter(x => x !== p)
      : [...node.trigger_phases, p];
    set('trigger_phases', phases);
  }

  const sigValues = node.trigger_signal
    ? (SALES_FLOW_SIGNAL_VALUES[node.trigger_signal] ?? [])
    : [];

  function handleSave() {
    if (!node.label.trim()) return;
    if (!node.action_instruction.trim()) return;
    onSave(node);
  }

  return (
    <DrawerBase
      title={initial.label ? 'Editar Regra' : 'Nova Regra'}
      sub="Configure quando e o que o agente deve fazer"
      onClose={onClose}
      onSave={handleSave}
    >
      {/* Nome/label */}
      <div className="o-field">
        <label className="o-field-label">Nome da regra <span style={{ color: 'var(--o-warn)' }}>*</span></label>
        <input
          className="o-input"
          placeholder="Ex: Objeção de preço na apresentação"
          value={node.label}
          onChange={e => set('label', e.target.value)}
        />
      </div>

      {/* Fases */}
      <div className="o-field">
        <label className="o-field-label">Fases onde esta regra pode disparar</label>
        <div className="o-field-hint">Selecione uma ou mais fases. Se nenhuma for selecionada, a regra nunca dispara.</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
          {allPhases.map(p => {
            const active = node.trigger_phases.includes(p);
            return (
              <div
                key={p}
                onClick={() => togglePhase(p)}
                style={{
                  padding: '6px 14px', borderRadius: 20, cursor: 'pointer', fontSize: 12.5, fontWeight: 500,
                  border: `1.5px solid ${active ? 'var(--o-active)' : 'var(--o-b1)'}`,
                  background: active ? 'var(--o-active)' : 'transparent',
                  color: active ? '#fff' : 'var(--o-sub)',
                  transition: 'all .15s',
                }}
              >
                {SALES_FLOW_PHASE_LABELS[p]}
              </div>
            );
          })}
        </div>
      </div>

      {/* Tipo de trigger */}
      <div className="o-field">
        <label className="o-field-label">Tipo de gatilho</label>
        <select className="o-input" value={node.trigger_type} onChange={e => set('trigger_type', e.target.value as SalesFlowTriggerType)}>
          {(Object.keys(SALES_FLOW_TRIGGER_LABELS) as SalesFlowTriggerType[]).map(k => (
            <option key={k} value={k}>{SALES_FLOW_TRIGGER_LABELS[k]}</option>
          ))}
        </select>
      </div>

      {/* Campos condicionais por tipo */}
      {node.trigger_type === 'signal' && (
        <>
          <div className="o-field">
            <label className="o-field-label">Sinal</label>
            <select
              className="o-input"
              value={node.trigger_signal ?? ''}
              onChange={e => { set('trigger_signal', e.target.value as SalesFlowSignalKey); set('trigger_value', null); }}
            >
              {(Object.keys(SALES_FLOW_SIGNAL_LABELS) as SalesFlowSignalKey[]).map(k => (
                <option key={k} value={k}>{SALES_FLOW_SIGNAL_LABELS[k]}</option>
              ))}
            </select>
          </div>
          {sigValues.length > 0 && (
            <div className="o-field">
              <label className="o-field-label">Valor esperado</label>
              <select className="o-input" value={node.trigger_value ?? ''} onChange={e => set('trigger_value', e.target.value || null)}>
                <option value="">— Qualquer valor —</option>
                {sigValues.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
              </select>
            </div>
          )}
        </>
      )}

      {node.trigger_type === 'keyword' && (
        <div className="o-field">
          <label className="o-field-label">Palavras-chave (separadas por vírgula)</label>
          <div className="o-field-hint">O gatilho dispara se o lead enviar qualquer uma dessas palavras.</div>
          <input
            className="o-input"
            placeholder="Ex: caro, não tenho verba, está muito alto"
            value={node.trigger_keywords.join(', ')}
            onChange={e => set('trigger_keywords', e.target.value.split(',').map(k => k.trim()).filter(Boolean))}
          />
        </div>
      )}

      {node.trigger_type === 'qualification_field' && (
        <>
          <div className="o-field">
            <label className="o-field-label">Campo de qualificação</label>
            <select className="o-input" value={node.trigger_field_key ?? ''} onChange={e => set('trigger_field_key', e.target.value || null)}>
              <option value="">— Selecione —</option>
              {qualFields.map(f => <option key={f.key} value={f.key}>{f.label} ({f.key})</option>)}
            </select>
          </div>
          <div className="o-field">
            <label className="o-field-label">Valor esperado <span style={{ color: 'var(--o-sub)', fontWeight: 300 }}>(opcional)</span></label>
            <div className="o-field-hint">Se deixar em branco, dispara quando o campo tiver qualquer valor preenchido.</div>
            <input
              className="o-input"
              placeholder="Ex: sim, decisor, urgente"
              value={node.trigger_field_value ?? ''}
              onChange={e => set('trigger_field_value', e.target.value || null)}
            />
          </div>
        </>
      )}

      {/* Instrução para o agente */}
      <div className="o-field" style={{ marginTop: 8 }}>
        <label className="o-field-label">Instrução para o agente <span style={{ color: 'var(--o-warn)' }}>*</span></label>
        <div className="o-field-hint">
          Texto de alta prioridade injetado no prompt do agente quando esta regra disparar. Não é um script fixo —
          é uma orientação sobre como conduzir este momento específico.
        </div>
        <textarea
          className="o-input"
          rows={5}
          placeholder="Ex: O lead rejeitou o preço. Antes de continuar, apresente o caso de ROI com clientes similares. Use dados concretos e evite repetir o preço diretamente."
          value={node.action_instruction}
          onChange={e => set('action_instruction', e.target.value)}
          style={{ resize: 'vertical', minHeight: 110 }}
        />
      </div>

      {/* Categoria de mídia */}
      <div className="o-field">
        <label className="o-field-label">
          Categoria de mídia para enviar <span style={{ color: 'var(--o-sub)', fontWeight: 300 }}>(opcional)</span>
        </label>
        <div className="o-field-hint">
          Nome da categoria da base de conhecimento (ex: <code>roi_study</code>, <code>social_proof</code>).
          O agente incluirá a mídia correspondente quando esta regra disparar.
        </div>
        <input
          className="o-input"
          placeholder="Ex: roi_study"
          value={node.action_media_category ?? ''}
          onChange={e => set('action_media_category', e.target.value.trim() || null)}
        />
      </div>

      {/* Habilitado */}
      <div className="o-field" style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
        <div>
          <div className="o-field-label" style={{ marginBottom: 0 }}>Regra habilitada</div>
          <div style={{ fontSize: 11.5, color: 'var(--o-sub)', fontWeight: 300 }}>Desabilitar mantém a regra salva sem avaliá-la</div>
        </div>
        <div className={`o-toggle ${node.enabled ? 'on' : ''}`} onClick={() => set('enabled', !node.enabled)} />
      </div>
    </DrawerBase>
  );
}

// ─── Card de node ─────────────────────────────────────────────

function FlowNodeCard({ node, index, total, onEdit, onRemove, onMove }: {
  node: SalesFlowNode;
  index: number;
  total: number;
  onEdit: () => void;
  onRemove: () => void;
  onMove: (dir: -1 | 1) => void;
}) {
  return (
    <div style={{ marginBottom: 8, opacity: node.enabled ? 1 : 0.55 }}>
      {/* Bloco SE */}
      <div style={{
        borderLeft: '3px solid var(--o-warn)',
        background: 'var(--o-bg2)',
        borderRadius: '8px 8px 0 0',
        padding: '12px 14px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 10, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-warn)', fontWeight: 600 }}>
            SE (gatilho)
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {!node.enabled && (
              <span style={{ fontSize: 10, color: 'var(--o-sub)', background: 'var(--o-b1)', borderRadius: 10, padding: '2px 8px' }}>
                desabilitada
              </span>
            )}
            <span style={{ fontSize: 10.5, color: 'var(--o-sub)', fontWeight: 300 }}>
              prioridade {node.priority}
            </span>
          </div>
        </div>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--o-text)', marginBottom: 2 }}>{node.label}</div>
        <div style={{ fontSize: 12, color: 'var(--o-sub)', fontWeight: 300 }}>{triggerSummary(node)}</div>
      </div>

      {/* Conector */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-start', paddingLeft: 20 }}>
        <div style={{ width: 2, height: 20, background: 'var(--o-b2)', borderLeft: '2px dashed var(--o-b2)' }} />
      </div>

      {/* Bloco ENTÃO */}
      <div style={{
        borderLeft: '3px solid var(--o-active)',
        background: 'var(--o-bg2)',
        borderRadius: '0 0 8px 8px',
        padding: '12px 14px',
      }}>
        <div style={{ marginBottom: 6 }}>
          <span style={{ fontSize: 10, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-active)', fontWeight: 600 }}>
            ENTÃO (ação)
          </span>
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--o-text)', lineHeight: 1.55, marginBottom: 4 }}>
          {node.action_instruction.length > 160
            ? node.action_instruction.slice(0, 157) + '…'
            : node.action_instruction}
        </div>
        {node.action_media_category && (
          <div style={{ fontSize: 11.5, color: 'var(--o-sub)', marginTop: 4 }}>
            Mídia: <code style={{ fontSize: 11, background: 'var(--o-b1)', padding: '1px 6px', borderRadius: 4 }}>
              {node.action_media_category}
            </code>
          </div>
        )}
      </div>

      {/* Ações */}
      <div style={{ display: 'flex', gap: 6, marginTop: 6, justifyContent: 'flex-end' }}>
        {index > 0 && (
          <button className="o-btn" style={{ fontSize: 11, padding: '3px 10px' }} onClick={() => onMove(-1)}>↑</button>
        )}
        {index < total - 1 && (
          <button className="o-btn" style={{ fontSize: 11, padding: '3px 10px' }} onClick={() => onMove(1)}>↓</button>
        )}
        <button className="o-btn" style={{ fontSize: 11, padding: '3px 10px' }} onClick={onEdit}>Editar</button>
        <button className="o-btn" style={{ fontSize: 11, padding: '3px 10px', color: 'var(--o-danger, #e05c5c)' }} onClick={onRemove}>✕</button>
      </div>
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────

export function CamadaFluxoVenda({ config, onUpdate }: Props) {
  const sf = flowOf(config);
  const [drawerNode, setDrawerNode] = useState<SalesFlowNode | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  const qualFields = (config.qualification_fields ?? []).map(f => ({ key: f.key, label: f.label }));

  function updateFlow(partial: Partial<SalesFlow>) {
    onUpdate({ sales_flow: { ...sf, ...partial } });
  }

  function openNew() {
    const next = emptyNode();
    next.priority = sf.nodes.length;
    setEditingId(null);
    setDrawerNode(next);
  }

  function openEdit(id: string) {
    const found = sf.nodes.find(n => n.id === id);
    if (found) { setEditingId(id); setDrawerNode({ ...found }); }
  }

  function saveNode(node: SalesFlowNode) {
    let nodes: SalesFlowNode[];
    if (editingId) {
      nodes = sf.nodes.map(n => n.id === editingId ? node : n);
    } else {
      nodes = [...sf.nodes, node];
    }
    updateFlow({ nodes });
    setDrawerNode(null);
    setEditingId(null);
  }

  function removeNode(id: string) {
    updateFlow({ nodes: sf.nodes.filter(n => n.id !== id).map((n, i) => ({ ...n, priority: i })) });
  }

  function moveNode(id: string, dir: -1 | 1) {
    const nodes = [...sf.nodes];
    const idx = nodes.findIndex(n => n.id === id);
    if (idx < 0) return;
    const swapIdx = idx + dir;
    if (swapIdx < 0 || swapIdx >= nodes.length) return;
    [nodes[idx], nodes[swapIdx]] = [nodes[swapIdx], nodes[idx]];
    updateFlow({ nodes: nodes.map((n, i) => ({ ...n, priority: i })) });
  }

  const sorted = [...sf.nodes].sort((a, b) => a.priority - b.priority);
  const activeCount = sf.nodes.filter(n => n.enabled).length;

  return (
    <>
      {drawerNode && (
        <DrawerNode
          node={drawerNode}
          qualFields={qualFields}
          onSave={saveNode}
          onClose={() => { setDrawerNode(null); setEditingId(null); }}
        />
      )}

      {/* Header com toggle global */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--o-text)' }}>
            Fluxo de Venda
            {sf.nodes.length > 0 && (
              <span style={{ marginLeft: 10, fontSize: 11.5, color: 'var(--o-sub)', fontWeight: 300 }}>
                {activeCount} regra{activeCount !== 1 ? 's' : ''} ativa{activeCount !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--o-sub)', fontWeight: 300, marginTop: 3 }}>
            {sf.enabled ? 'Avaliando regras em cada turno' : 'Desabilitado — nenhuma regra será avaliada'}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className={`o-toggle ${sf.enabled ? 'on' : ''}`} onClick={() => updateFlow({ enabled: !sf.enabled })} />
        </div>
      </div>

      {/* Lista de nodes */}
      {sorted.length === 0 ? (
        <div style={{
          border: '1.5px dashed var(--o-b1)', borderRadius: 10, padding: '32px 24px',
          textAlign: 'center', color: 'var(--o-sub)', marginBottom: 16,
        }}>
          <div style={{ fontSize: 13.5, fontWeight: 400, marginBottom: 6 }}>Nenhuma regra configurada</div>
          <div style={{ fontSize: 12, fontWeight: 300 }}>
            Adicione regras para instruir o agente em momentos cruciais da conversa.
          </div>
        </div>
      ) : (
        <div style={{ marginBottom: 12 }}>
          {sorted.map((node, idx) => (
            <div key={node.id}>
              <FlowNodeCard
                node={node}
                index={idx}
                total={sorted.length}
                onEdit={() => openEdit(node.id)}
                onRemove={() => removeNode(node.id)}
                onMove={dir => moveNode(node.id, dir)}
              />
              {idx < sorted.length - 1 && (
                <div style={{ textAlign: 'center', padding: '4px 0', color: 'var(--o-dim, var(--o-b2))' }}>
                  <span style={{ fontSize: 16 }}>↕</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Botão adicionar */}
      <button className="o-btn" style={{ width: '100%', justifyContent: 'center', gap: 8 }} onClick={openNew}>
        <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> Adicionar Regra
      </button>

      {/* Info sobre base de conhecimento */}
      <div style={{
        marginTop: 20, padding: '12px 16px', borderRadius: 8,
        background: 'var(--o-bg2)', border: '1px solid var(--o-b1)',
        fontSize: 12, color: 'var(--o-sub)', fontWeight: 300, lineHeight: 1.65,
      }}>
        <strong style={{ color: 'var(--o-text)', fontWeight: 500 }}>Sobre este recurso:</strong>{' '}
        As regras do Fluxo de Venda injetam instruções de alta prioridade no agente em momentos específicos.
        O agente ainda consulta a base de conhecimento normalmente — este fluxo é complementar, não substituto.
        Prioridade: regras de menor número são avaliadas primeiro; apenas a primeira com match dispara por turno.
      </div>
    </>
  );
}
