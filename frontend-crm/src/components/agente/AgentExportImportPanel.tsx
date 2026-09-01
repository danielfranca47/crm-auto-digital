/**
 * AgentExportImportPanel
 *
 * Modal com duas abas — Exportar e Importar — para backup e replicação
 * de configurações de agente entre contas.
 *
 * Exportar:
 *  - "Sem treinamento" → só o AI Profile
 *  - "Com treinamento" → AI Profile + itens de playground_training_items
 *
 * Importar:
 *  - Lê um .json exportado por este mesmo modal
 *  - Valida schema + version client-side
 *  - Aplica via api.agente.saveConfig() + api.playground.importTraining()
 *  - Preserva campos sensíveis do usuário atual (webhook secret, WhatsApp, etc.)
 */
import { useRef, useState } from 'react';
import { api } from '@/services/api';
import type { AgentConfig } from '@/types/agente';
import { DEFAULT_AGENT_CONFIG } from '@/types/agente';
import type { AgentExportPayload, TrainingItem } from '@/types/agente';

// Campos sensíveis/específicos por conta — não exportar, não importar
const EXPORT_EXCLUDE: (keyof AgentConfig)[] = [
  'operator_whatsapp',
  'payment_webhook_secret',
  'payment_webhook_url',
];

type Tab = 'export' | 'import' | 'reset';
type ExportMode = 'without_training' | 'with_training';
type TrainingImportChoice = 'replace' | 'keep';

interface Props {
  config: AgentConfig;
  onClose: () => void;
  onImportSuccess: () => void;
}

function validateImportPayload(raw: unknown): AgentExportPayload {
  if (typeof raw !== 'object' || raw === null) throw new Error('Arquivo inválido');
  const obj = raw as Record<string, unknown>;
  if (obj.schema !== 'crm-agent-export') throw new Error('Arquivo não é um export de agente válido');
  if (obj.version !== '1.0') throw new Error(`Versão ${String(obj.version)} não suportada. Esperado: 1.0`);
  if (typeof obj.profile !== 'object' || obj.profile === null) throw new Error('Perfil ausente no arquivo');
  if (typeof (obj.profile as Record<string, unknown>).agent_mode !== 'string')
    throw new Error('Campo obrigatório ausente: agent_mode');
  if (typeof (obj.profile as Record<string, unknown>).name !== 'string')
    throw new Error('Campo obrigatório ausente: name');
  if (obj.includes_training && !Array.isArray(obj.training))
    throw new Error('Campo training inválido no arquivo');
  return obj as AgentExportPayload;
}

export function AgentExportImportPanel({ config, onClose, onImportSuccess }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('export');
  const [exportMode, setExportMode] = useState<ExportMode>('without_training');
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const [importPayload, setImportPayload] = useState<AgentExportPayload | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importPartialError, setImportPartialError] = useState<string | null>(null);
  const [importSuccess, setImportSuccess] = useState<string | null>(null);
  const [trainingImportChoice, setTrainingImportChoice] = useState<TrainingImportChoice>('replace');

  const [resetAcknowledged, setResetAcknowledged] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetSuccess, setResetSuccess] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Export ─────────────────────────────────────────────────────────────────

  async function handleExport() {
    setExporting(true);
    setExportError(null);
    try {
      const profileToExport = { ...config } as Record<string, unknown>;
      EXPORT_EXCLUDE.forEach(k => delete profileToExport[k]);

      let trainingItems: TrainingItem[] = [];
      if (exportMode === 'with_training') {
        const result = await api.playground.exportTraining();
        trainingItems = result.items;
      }

      const payload: AgentExportPayload = {
        version: '1.0',
        schema: 'crm-agent-export',
        exported_at: new Date().toISOString(),
        agent_name: config.name || 'agente',
        includes_training: exportMode === 'with_training',
        profile: profileToExport as Partial<AgentConfig>,
        training: trainingItems,
      };

      const safeName = (config.name || 'agente').replace(/[^a-zA-Z0-9-_]/g, '-');
      const dateStr = new Date().toISOString().slice(0, 10);
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ai-agent-${safeName}-${dateStr}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(
        exportMode === 'with_training'
          ? 'Não foi possível carregar o treinamento. Tente exportar sem treinamento.'
          : 'Erro ao gerar o arquivo. Tente novamente.'
      );
    } finally {
      setExporting(false);
    }
  }

  // ── Import ─────────────────────────────────────────────────────────────────

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportPayload(null);
    setImportError(null);
    setImportPartialError(null);
    setImportSuccess(null);
    setTrainingImportChoice('replace');

    const reader = new FileReader();
    reader.onload = ev => {
      try {
        const raw = JSON.parse(ev.target?.result as string);
        const validated = validateImportPayload(raw);
        setImportPayload(validated);
      } catch (err) {
        setImportError(err instanceof Error ? err.message : 'Erro ao ler arquivo');
      }
    };
    reader.onerror = () => setImportError('Não foi possível ler o arquivo');
    reader.readAsText(file);

    // Reset input so the same file can be re-selected
    e.target.value = '';
  }

  // ── Reset ──────────────────────────────────────────────────────────────────

  async function handleReset() {
    if (!resetAcknowledged) return;
    setResetting(true);
    setResetError(null);
    setResetSuccess(null);
    try {
      const result = await api.playground.resetTraining();
      setResetSuccess(
        result.deleted > 0
          ? `${result.deleted} exemplo(s) de treinamento removido(s).`
          : 'Não havia treinamento para remover.'
      );
      setResetAcknowledged(false);
      onImportSuccess();
    } catch (err) {
      setResetError('Erro ao zerar o treinamento. Tente novamente.');
    } finally {
      setResetting(false);
    }
  }

  async function handleImport() {
    if (!importPayload) return;
    setImporting(true);
    setImportError(null);
    setImportPartialError(null);
    setImportSuccess(null);

    try {
      // Strip sensitive fields that may be present in the file
      const profilePatch = { ...importPayload.profile } as Record<string, unknown>;
      EXPORT_EXCLUDE.forEach(k => delete profilePatch[k]);

      // Merge: safe baseline → import data → preserve user's sensitive fields
      const mergedConfig: AgentConfig = {
        ...DEFAULT_AGENT_CONFIG,
        ...(profilePatch as Partial<AgentConfig>),
        operator_whatsapp: config.operator_whatsapp,
        payment_webhook_url: config.payment_webhook_url,
        payment_webhook_secret: config.payment_webhook_secret,
      };

      await api.agente.saveConfig(mergedConfig);

      const hasTraining = importPayload.includes_training && importPayload.training.length > 0;
      const willReplaceTraining = hasTraining && trainingImportChoice === 'replace';

      // Import training (may fail independently — show partial error)
      if (willReplaceTraining) {
        try {
          await api.playground.importTraining(importPayload.training);
        } catch {
          setImportPartialError(
            'Configuração aplicada com sucesso, mas o treinamento não foi importado. Tente importar novamente.'
          );
          onImportSuccess();
          setImporting(false);
          return;
        }
      }

      const trainingMsg = willReplaceTraining
        ? ` e ${importPayload.training.length} exemplo(s) de treinamento`
        : hasTraining
          ? '. Treinamento atual mantido'
          : '';
      setImportSuccess(`Agente "${importPayload.agent_name}" importado com sucesso${trainingMsg}.`);
      onImportSuccess();
      setTimeout(() => onClose(), 1800);
    } catch (err) {
      setImportError('Erro ao importar configuração. Verifique e tente novamente.');
    } finally {
      setImporting(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const tabStyle = (tab: Tab): React.CSSProperties => ({
    padding: '8px 20px',
    fontSize: 13,
    fontWeight: activeTab === tab ? 600 : 400,
    color: activeTab === tab ? 'var(--o-text)' : 'var(--o-sub)',
    borderBottom: activeTab === tab ? '2px solid var(--o-accent)' : '2px solid transparent',
    background: 'none',
    border: 'none',
    borderBottom: activeTab === tab ? '2px solid var(--o-accent)' : '2px solid transparent',
    cursor: 'pointer',
    transition: 'color 0.15s',
  });

  return (
    <div
      className="o-modal-overlay open"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="o-modal" style={{ maxWidth: 520 }}>
        {/* Header */}
        <div className="o-modal-header">
          <div>
            <div className="font-display" style={{ fontSize: 20, fontWeight: 400, color: 'var(--o-text)' }}>
              Exportar / Importar agente
            </div>
            <div style={{ fontSize: 12, color: 'var(--o-sub)', marginTop: 2 }}>
              Backup ou replicação da configuração completa
            </div>
          </div>
          <button className="o-close-btn" onClick={onClose}>✕</button>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--o-b1)', marginBottom: 0 }}>
          <button style={tabStyle('export')} onClick={() => setActiveTab('export')}>Exportar</button>
          <button style={tabStyle('import')} onClick={() => setActiveTab('import')}>Importar</button>
          <button style={tabStyle('reset')} onClick={() => setActiveTab('reset')}>Zerar treinamento</button>
        </div>

        {/* Body */}
        <div className="o-modal-body" style={{ minHeight: 220 }}>

          {/* ── Tab: Exportar ─────────────────────────────── */}
          {activeTab === 'export' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <p style={{ fontSize: 13, color: 'var(--o-sub)', margin: 0 }}>
                Gera um arquivo <code>.json</code> com toda a configuração do agente. Use para backup ou para replicar para outra conta.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--o-text)' }}>O que incluir no arquivo:</label>

                <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="exportMode"
                    value="without_training"
                    checked={exportMode === 'without_training'}
                    onChange={() => setExportMode('without_training')}
                    style={{ marginTop: 3 }}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--o-text)' }}>Somente configuração</div>
                    <div style={{ fontSize: 12, color: 'var(--o-sub)' }}>
                      Identidade, qualificação, pipeline, apresentação e oferta do agente.
                    </div>
                  </div>
                </label>

                <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="exportMode"
                    value="with_training"
                    checked={exportMode === 'with_training'}
                    onChange={() => setExportMode('with_training')}
                    style={{ marginTop: 3 }}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--o-text)' }}>Configuração + treinamento</div>
                    <div style={{ fontSize: 12, color: 'var(--o-sub)' }}>
                      Inclui também os exemplos de feedback do Playground (few-shot). Recomendado para replicação completa.
                    </div>
                  </div>
                </label>
              </div>

              {exportError && (
                <div style={{ fontSize: 12, color: 'var(--o-danger, #e53e3e)', padding: '8px 12px', background: 'var(--o-danger-bg, #fff5f5)', borderRadius: 6 }}>
                  {exportError}
                </div>
              )}
            </div>
          )}

          {/* ── Tab: Importar ─────────────────────────────── */}
          {activeTab === 'import' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <p style={{ fontSize: 13, color: 'var(--o-sub)', margin: 0 }}>
                Selecione um arquivo <code>.json</code> exportado por este sistema para aplicar a configuração nesta conta.
              </p>

              {/* File picker */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".json,application/json"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
              <button
                className="o-btn"
                style={{ alignSelf: 'flex-start', fontSize: 13 }}
                onClick={() => fileInputRef.current?.click()}
              >
                Selecionar arquivo .json
              </button>

              {/* Validation error */}
              {importError && (
                <div style={{ fontSize: 12, color: 'var(--o-danger, #e53e3e)', padding: '8px 12px', background: 'var(--o-danger-bg, #fff5f5)', borderRadius: 6 }}>
                  {importError}
                </div>
              )}

              {/* Preview card */}
              {importPayload && !importError && (
                <div style={{ border: '1px solid var(--o-b1)', borderRadius: 8, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--o-sub)', marginBottom: 4 }}>Agente detectado</div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--o-text)' }}>{importPayload.agent_name}</div>
                  <div style={{ fontSize: 12, color: 'var(--o-sub)' }}>
                    {importPayload.includes_training
                      ? `Inclui treinamento · ${importPayload.training.length} exemplo(s)`
                      : 'Somente configuração (sem treinamento)'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--o-sub)', opacity: 0.7 }}>
                    Exportado em: {new Date(importPayload.exported_at).toLocaleString('pt-BR')}
                  </div>
                </div>
              )}

              {/* Training choice — só quando o arquivo inclui treinamento */}
              {importPayload && importPayload.includes_training && importPayload.training.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--o-text)' }}>Treinamento do arquivo:</label>

                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="trainingImportChoice"
                      value="replace"
                      checked={trainingImportChoice === 'replace'}
                      onChange={() => setTrainingImportChoice('replace')}
                      style={{ marginTop: 3 }}
                    />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--o-text)' }}>Substituir treinamento atual</div>
                      <div style={{ fontSize: 12, color: 'var(--o-sub)' }}>
                        Remove o treinamento existente e aplica o do arquivo.
                      </div>
                    </div>
                  </label>

                  <label style={{ display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="trainingImportChoice"
                      value="keep"
                      checked={trainingImportChoice === 'keep'}
                      onChange={() => setTrainingImportChoice('keep')}
                      style={{ marginTop: 3 }}
                    />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--o-text)' }}>Manter treinamento atual</div>
                      <div style={{ fontSize: 12, color: 'var(--o-sub)' }}>
                        Aplica só a configuração do arquivo; o treinamento existente não é alterado.
                      </div>
                    </div>
                  </label>
                </div>
              )}

              {/* Warning */}
              {importPayload && (
                <div style={{ fontSize: 12, color: 'var(--o-warning-text, #7b4f12)', background: 'var(--o-warning-bg, #fffbeb)', border: '1px solid var(--o-warning-border, #f6e05e)', borderRadius: 6, padding: '8px 12px' }}>
                  ⚠️ A importação vai substituir a configuração atual do agente. Esta ação não pode ser desfeita.
                  {importPayload.includes_training && importPayload.training.length > 0 && trainingImportChoice === 'replace' && (
                    <> O treinamento existente também será substituído.</>
                  )}
                </div>
              )}

              {/* Partial error (training failed after profile saved) */}
              {importPartialError && (
                <div style={{ fontSize: 12, color: 'var(--o-warning-text, #7b4f12)', background: 'var(--o-warning-bg, #fffbeb)', border: '1px solid var(--o-warning-border, #f6e05e)', borderRadius: 6, padding: '8px 12px' }}>
                  {importPartialError}
                </div>
              )}

              {/* Success */}
              {importSuccess && (
                <div style={{ fontSize: 13, color: 'var(--o-success-text, #276749)', background: 'var(--o-success-bg, #f0fff4)', border: '1px solid var(--o-success-border, #9ae6b4)', borderRadius: 6, padding: '8px 12px' }}>
                  ✓ {importSuccess}
                </div>
              )}
            </div>
          )}

          {/* ── Tab: Zerar treinamento ─────────────────────── */}
          {activeTab === 'reset' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <p style={{ fontSize: 13, color: 'var(--o-sub)', margin: 0 }}>
                Remove todos os exemplos de treinamento (feedback do Playground) desta conta, sem alterar a configuração do agente. Use para recomeçar o aprendizado do zero.
              </p>

              <div style={{ fontSize: 12, color: 'var(--o-warning-text, #7b4f12)', background: 'var(--o-warning-bg, #fffbeb)', border: '1px solid var(--o-warning-border, #f6e05e)', borderRadius: 6, padding: '8px 12px' }}>
                ⚠️ Esta ação não pode ser desfeita. Recomendamos exportar o treinamento atual (aba "Exportar") antes de zerar, caso queira recuperá-lo depois.
              </div>

              <div className="o-field" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="checkbox"
                  id="reset-training-ack"
                  checked={resetAcknowledged}
                  onChange={e => setResetAcknowledged(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
                <label htmlFor="reset-training-ack" style={{ cursor: 'pointer', fontSize: 12.5 }}>
                  Estou ciente que essa ação não pode ser desfeita
                </label>
              </div>

              {resetError && (
                <div style={{ fontSize: 12, color: 'var(--o-danger, #e53e3e)', padding: '8px 12px', background: 'var(--o-danger-bg, #fff5f5)', borderRadius: 6 }}>
                  {resetError}
                </div>
              )}

              {resetSuccess && (
                <div style={{ fontSize: 13, color: 'var(--o-success-text, #276749)', background: 'var(--o-success-bg, #f0fff4)', border: '1px solid var(--o-success-border, #9ae6b4)', borderRadius: 6, padding: '8px 12px' }}>
                  ✓ {resetSuccess}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="o-modal-footer">
          {activeTab === 'export' && (
            <>
              <button
                className="o-btn o-btn-primary"
                onClick={handleExport}
                disabled={exporting}
              >
                {exporting ? 'Gerando arquivo…' : 'Baixar arquivo'}
              </button>
              <button className="o-btn" onClick={onClose}>Cancelar</button>
            </>
          )}
          {activeTab === 'import' && (
            <>
              <button
                className="o-btn o-btn-primary"
                onClick={handleImport}
                disabled={!importPayload || importing || !!importSuccess}
              >
                {importing ? 'Importando…' : 'Confirmar importação'}
              </button>
              <button className="o-btn" onClick={onClose}>Cancelar</button>
            </>
          )}
          {activeTab === 'reset' && (
            <>
              <button
                className="o-btn o-btn-primary"
                onClick={handleReset}
                disabled={!resetAcknowledged || resetting || !!resetSuccess}
              >
                {resetting ? 'Zerando…' : 'Zerar treinamento'}
              </button>
              <button className="o-btn" onClick={onClose}>Cancelar</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
