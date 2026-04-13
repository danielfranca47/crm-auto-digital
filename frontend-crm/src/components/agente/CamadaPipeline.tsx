import { useState } from 'react';
import type { AgentConfig } from '@/types/agente';
import { LGPD_LABELS, REATIVACAO_LABELS, MEDIA_FALLBACK_LABELS } from '@/types/agente';
import { buildVariableList } from '@/types/variables';
import { VariableTextarea } from './VariableTextarea';

interface CamadaPipelineProps {
  config: AgentConfig;
  onUpdate: (partial: Partial<AgentConfig>) => void;
  /** Número do agente conectado (exibido no card de conexão) */
  phoneNumber?: string | null;
}

// ─── Drawer: Follow-up cadência ───────────────────────────────
function DrawerFollowup({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [h1, setH1] = useState(config.followup_h1);
  const [h2, setH2] = useState(config.followup_h2);
  const [h3, setH3] = useState(config.followup_h3);
  return (
    <DrawerBase title="Cadência de follow-up" sub="Intervalos entre tentativas — ritmo espaçado protege o número" onClose={onClose} onSave={() => onSave({ followup_h1: h1, followup_h2: h2, followup_h3: h3 })}>
      <SliderField label="1ª tentativa — após silêncio de" value={h1} min={1} max={72} step={1} format={v => `${v}h`} onChange={setH1} />
      <SliderField label="2ª tentativa — após mais" value={h2} min={24} max={168} step={24} format={v => `${Math.round(v / 24)}d`} onChange={setH2} />
      <SliderField label="3ª tentativa — após mais" value={h3} min={48} max={336} step={24} format={v => `${Math.round(v / 24)}d`} onChange={setH3} />
    </DrawerBase>
  );
}

// ─── Drawer: Limite diário ────────────────────────────────────
function DrawerLimite({ value, onSave, onClose }: { value: number; onSave: (v: number) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  return (
    <DrawerBase title="Limite diário de disparos" sub="Proteção comportamental — não é teto da Meta" onClose={onClose} onSave={() => onSave(local)}>
      <div className="o-field">
        <label className="o-field-label">Mensagens por dia</label>
        <div className="o-field-hint">Envios acelerados aumentam o risco de detecção pelo WhatsApp. Recomendamos 150–300 para uso regular.</div>
        <SliderField label="" value={local} min={50} max={500} step={50} format={v => String(v)} onChange={setLocal} />
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Intervalo entre mensagens ───────────────────────
function DrawerIntervalo({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [iMin, setMin] = useState(config.interval_min);
  const [iMax, setMax] = useState(config.interval_max);
  return (
    <DrawerBase title="Intervalo entre mensagens" sub="Simula comportamento humano — reduz risco de detecção" onClose={onClose} onSave={() => onSave({ interval_min: iMin, interval_max: iMax })}>
      <SliderField label="Mínimo (segundos)" value={iMin} min={1} max={15} step={1} format={v => `${v}s`} onChange={setMin} />
      <SliderField label="Máximo (segundos)" value={iMax} min={3} max={30} step={1} format={v => `${v}s`} onChange={setMax} />
    </DrawerBase>
  );
}

// ─── Drawer: Mídia inválida ───────────────────────────────────
function DrawerMidia({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [fallback, setFallback] = useState(config.media_fallback);
  const [msg, setMsg] = useState(config.media_fallback_msg);
  const variables = buildVariableList(config.custom_variables || {});
  return (
    <DrawerBase title="Mídia inválida" sub="O que fazer quando o lead envia áudio, vídeo, figurinha ou reação" onClose={onClose} onSave={() => onSave({ media_fallback: fallback, media_fallback_msg: msg })}>
      <div className="o-field">
        <label className="o-field-label">Comportamento</label>
        <select className="o-select" value={fallback} onChange={e => setFallback(e.target.value)}>
          <option value="continuar">Responder e continuar o fluxo</option>
          <option value="pausar">Responder e pausar o bot</option>
          <option value="ignorar">Ignorar silenciosamente</option>
        </select>
      </div>
      {fallback !== 'ignorar' && (
        <div className="o-field">
          <label className="o-field-label">Mensagem ao lead</label>
          <VariableTextarea value={msg} onChange={setMsg} variables={variables} />
        </div>
      )}
    </DrawerBase>
  );
}

// ─── Modal: Opt-out ───────────────────────────────────────────
function ModalOptOut({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [keywords, setKeywords] = useState<string[]>([...config.opt_out_keywords]);
  const [kwInput, setKwInput] = useState('');
  const [disable, setDisable] = useState(config.opt_out_disable);
  const [notify, setNotify] = useState(config.opt_out_notify);
  const [confirm, setConfirm] = useState(config.opt_out_confirm);
  const [confirmMsg, setConfirmMsg] = useState(config.opt_out_confirm_msg);
  const optOutVariables = buildVariableList(config.custom_variables || {});

  function addKw() {
    const v = kwInput.trim().toUpperCase();
    if (v && !keywords.includes(v)) { setKeywords(prev => [...prev, v]); }
    setKwInput('');
  }
  function rmKw(kw: string) { setKeywords(prev => prev.filter(k => k !== kw)); }
  function handleKwKeydown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addKw(); }
  }

  return (
    <ModalBase title="Opt-out por palavra-chave" sub="Quando o lead envia estas palavras o bot para imediatamente" onClose={onClose}
      onSave={() => onSave({ opt_out_keywords: keywords, opt_out_disable: disable, opt_out_notify: notify, opt_out_confirm: confirm, opt_out_confirm_msg: confirmMsg })}>

      <div className="o-field">
        <label className="o-field-label">Palavras-chave de cancelamento</label>
        <div className="o-field-hint">Digite e pressione Enter ou vírgula para adicionar. A detecção ignora maiúsculas e acentos.</div>
        <div className="o-tag-wrap" onClick={() => document.getElementById('kw-input')?.focus()}>
          {keywords.map(kw => (
            <span key={kw} className="o-kw-tag">
              {kw}
              <button onClick={() => rmKw(kw)}>×</button>
            </span>
          ))}
          <input
            id="kw-input"
            className="o-tag-input"
            placeholder="Adicionar palavra…"
            value={kwInput}
            onChange={e => setKwInput(e.target.value)}
            onKeyDown={handleKwKeydown}
            onBlur={addKw}
          />
        </div>
      </div>

      <div className="o-field">
        <label className="o-field-label">Ações automáticas ao detectar</label>
        <ToggleRow label="Desabilitar bot imediatamente" desc="Antes de qualquer processamento pelo LLM" value={disable} onChange={setDisable} />
        <ToggleRow label="Registrar opt-out com timestamp" desc="Tabela lead_consents — necessário para LGPD" value={notify} onChange={setNotify} />
        <ToggleRow label="Enviar confirmação ao lead" desc='Mensagem de "você foi removido da nossa lista"' value={confirm} onChange={setConfirm} />
      </div>

      {confirm && (
        <div className="o-field">
          <label className="o-field-label">Mensagem de confirmação ao lead</label>
          <VariableTextarea value={confirmMsg} onChange={setConfirmMsg} variables={optOutVariables} />
        </div>
      )}
    </ModalBase>
  );
}

// ─── Modal: LGPD ─────────────────────────────────────────────
function ModalLGPD({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [mode, setMode] = useState(config.lgpd_mode);
  const [msg, setMsg] = useState(config.lgpd_msg);
  const lgpdVariables = buildVariableList(config.custom_variables || {});

  return (
    <ModalBase title="Consentimento LGPD" sub="Lei Geral de Proteção de Dados — obrigatório independente do tipo de API" onClose={onClose}
      onSave={() => onSave({ lgpd_mode: mode, lgpd_msg: msg })}>
      <div className="o-field">
        <label className="o-field-label">Quando coletar consentimento</label>
        <OptCard selected={mode === 'inbound'}  onClick={() => setMode('inbound')}  label="Inbound implícito"      desc="O lead entrou em contato — consentimento implícito registrado automaticamente." />
        <OptCard selected={mode === 'explicit'} onClick={() => setMode('explicit')} label="Confirmação explícita"  desc="O agente envia mensagem pedindo confirmação antes de iniciar o fluxo." />
        <OptCard selected={mode === 'outbound'} onClick={() => setMode('outbound')} label="Apenas no outbound"     desc="Coleta consentimento só quando o bot inicia o contato." />
      </div>
      {mode === 'explicit' && (
        <div className="o-field">
          <label className="o-field-label">Mensagem de opt-in explícito</label>
          <VariableTextarea value={msg} onChange={setMsg} variables={lgpdVariables} />
        </div>
      )}
    </ModalBase>
  );
}

// ─── Modal: Reativação ────────────────────────────────────────
function ModalReativacao({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [mode, setMode] = useState(config.reactivation_mode);
  const [msg, setMsg] = useState(config.reactivation_msg);
  const reativacaoVariables = buildVariableList(config.custom_variables || {});

  return (
    <ModalBase title="Reativação de arquivados" sub="O que acontece quando um lead arquivado envia uma mensagem espontaneamente" onClose={onClose}
      onSave={() => onSave({ reactivation_mode: mode, reactivation_msg: msg })}>
      <div className="o-field">
        <label className="o-field-label">Comportamento ao detectar retorno</label>
        <OptCard selected={mode === 'reativar-notificar'} onClick={() => setMode('reativar-notificar')} label="Reativar e notificar operador" desc="Move para reengajamento, aciona playbook e notifica o operador imediatamente." />
        <OptCard selected={mode === 'reiniciar'}           onClick={() => setMode('reiniciar')}          label="Reativar e reiniciar do início" desc="Move para to-prospect e reinicia o fluxo completo de qualificação." />
        <OptCard selected={mode === 'retomar'}             onClick={() => setMode('retomar')}            label="Reativar e retomar do ponto exato" desc="Retoma do último estágio de qualificação atingido." />
        <OptCard selected={mode === 'notificar-somente'}   onClick={() => setMode('notificar-somente')}  label="Manter arquivado e notificar" desc="O bot não responde. O operador recebe o alerta e decide manualmente." />
      </div>
      <div className="o-field">
        <label className="o-field-label">Mensagem de reabertura</label>
        <VariableTextarea value={msg} onChange={setMsg} variables={reativacaoVariables} />
      </div>
    </ModalBase>
  );
}

// ─────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────

// ─── Drawer: Follow-up avançado ───────────────────────────────
function DrawerFollowupAvancado({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [maxAttempts, setMaxAttempts] = useState(config.followup_max_attempts);
  const [firstOffset, setFirstOffset] = useState(config.followup_first_offset);
  const [cadence, setCadence]         = useState(config.followup_cadence);
  const [allowedHours, setAllowedHours] = useState(config.followup_allowed_hours);
  const [cadenceError, setCadenceError] = useState<string | null>(null);

  function validateCadence(v: string) {
    setCadence(v);
    const parts = v.split(',').map(s => s.trim());
    if (parts.some(p => isNaN(Number(p)) || Number(p) <= 0)) {
      setCadenceError('Formato inválido — use números separados por vírgula. Ex: 60,1440,4320');
    } else {
      setCadenceError(null);
    }
  }

  return (
    <DrawerBase title="Follow-up avançado" sub="Parâmetros detalhados de cadência e horário de envio" onClose={onClose}
      onSave={() => onSave({ followup_max_attempts: maxAttempts, followup_first_offset: firstOffset, followup_cadence: cadence, followup_allowed_hours: allowedHours })}>
      <SliderField label="Máx. tentativas de follow-up" value={maxAttempts} min={1} max={10} step={1} format={v => String(v)} onChange={setMaxAttempts} />
      <SliderField label="Primeiro offset (minutos após silêncio)" value={firstOffset} min={5} max={1440} step={5} format={v => v < 60 ? `${v}min` : `${Math.round(v/60)}h`} onChange={setFirstOffset} />
      <div className="o-field">
        <label className="o-field-label">Cadência completa (minutos, separados por vírgula)</label>
        <div className="o-field-hint">Ex: 60,1440,4320 → 1h depois, 1 dia depois, 3 dias depois</div>
        <input
          className={`o-input${cadenceError ? ' o-input-error' : ''}`}
          value={cadence}
          onChange={e => validateCadence(e.target.value)}
          placeholder="60,1440,4320"
        />
        {cadenceError && <div style={{ fontSize: 11, color: 'var(--o-hot)', marginTop: 4 }}>{cadenceError}</div>}
      </div>
      <div className="o-field">
        <label className="o-field-label">Horário permitido (UTC)</label>
        <div className="o-field-hint">Formato: HH:MM-HH:MM. Ex: 08:00-20:00 (fuso configurado na Camada 1)</div>
        <input
          className="o-input"
          value={allowedHours}
          onChange={e => setAllowedHours(e.target.value)}
          placeholder="08:00-20:00"
        />
      </div>
    </DrawerBase>
  );
}

type DrawerKey = 'followup' | 'followup_avancado' | 'limite' | 'intervalo' | 'midia' | null;
type ModalKey  = 'optout' | 'lgpd' | 'reativacao' | null;

export function CamadaPipeline({ config, onUpdate, phoneNumber }: CamadaPipelineProps) {
  const [drawer, setDrawer] = useState<DrawerKey>(null);
  const [modal, setModal]   = useState<ModalKey>(null);

  const optoutConfigured   = config.opt_out_keywords.length > 0;
  const lgpdConfigured     = !!config.lgpd_mode;
  const reatConfigured     = !!config.reactivation_mode;
  const mediaConfigured    = !!config.media_fallback;
  const followupConfigured = config.followup_h1 > 0;

  const fu1Label = `${config.followup_h1}h · ${Math.round(config.followup_h2 / 24)}d · ${Math.round(config.followup_h3 / 24)}d`;

  return (
    <>
      {/* Seção 0: Conexão */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Seção 0 · Conexão do número
        </span>
        <span style={{ fontSize: 8, color: 'var(--o-active)', fontFamily: '"DM Mono"', border: '1px solid var(--o-act-b)', padding: '1px 6px', borderRadius: 2 }}>
          {phoneNumber ? 'Sessão ativa' : 'Verificar'}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <InfoCard label="Número conectado" value={phoneNumber ?? '—'} sub="Sessão QR via WhatsApp Web" status="ok" />
        <EditCard label="Intervalo entre mensagens" value={`${config.interval_min}–${config.interval_max} segundos`} sub="Delay simulado de comportamento humano" onClick={() => setDrawer('intervalo')} status="ok" />
        <EditCard label="Limite diário de disparos" value={`${config.daily_limit} mensagens/dia`} sub="Proteção comportamental" onClick={() => setDrawer('limite')} status="ok" />
      </div>

      {/* Seção 1: Comportamento por evento */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Seção 1 · Comportamento por evento
        </span>
        {(!optoutConfigured || !lgpdConfigured) && (
          <span style={{ fontSize: 8, color: 'var(--o-hot)', fontFamily: '"DM Mono"', border: '1px solid var(--o-hot-b)', padding: '1px 6px', borderRadius: 2 }}>
            {[!optoutConfigured, !lgpdConfigured].filter(Boolean).length} críticos
          </span>
        )}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Mídia inválida" sub="Áudio, vídeo, figurinha ou reação"
          value={MEDIA_FALLBACK_LABELS[config.media_fallback] || config.media_fallback || '—'}
          onClick={() => setDrawer('midia')} status={mediaConfigured ? 'ok' : 'warn'}
        />
        <EditCard
          label="Opt-out por palavra-chave" sub="STOP · PARAR · SAIR · CANCELAR"
          value={optoutConfigured ? `${config.opt_out_keywords.length} palavras configuradas` : 'Não configurado'}
          onClick={() => setModal('optout')} status={optoutConfigured ? 'ok' : 'miss'}
          critical={!optoutConfigured}
        />
        <EditCard
          label="Consentimento LGPD" sub="Lei brasileira — obrigatório"
          value={LGPD_LABELS[config.lgpd_mode] || 'Não configurado'}
          onClick={() => setModal('lgpd')} status={lgpdConfigured ? 'ok' : 'miss'}
          critical={!lgpdConfigured}
        />
      </div>

      {/* Seção 2: Cadência */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Seção 2 · Cadência e follow-up
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Thresholds de follow-up" sub="Cadência espaçada — proteção comportamental"
          value={fu1Label}
          onClick={() => setDrawer('followup')} status={followupConfigured ? 'ok' : 'warn'}
        />
        <EditCard
          label="Follow-up avançado"
          sub={`Máx. ${config.followup_max_attempts} tentativas · ${config.followup_allowed_hours}`}
          value={`Cadência: ${config.followup_cadence || 'não configurada'}`}
          onClick={() => setDrawer('followup_avancado')} status="ok"
        />
      </div>

      {/* Seção 3: Reativação */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Seção 3 · Reativação e handoff
        </span>
        {!reatConfigured && (
          <span style={{ fontSize: 8, color: 'var(--o-hot)', fontFamily: '"DM Mono"', border: '1px solid var(--o-hot-b)', padding: '1px 6px', borderRadius: 2 }}>
            1 crítico
          </span>
        )}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Reativação de arquivados" sub="Leads que retornam espontaneamente"
          value={REATIVACAO_LABELS[config.reactivation_mode] || 'Não configurado'}
          onClick={() => setModal('reativacao')} status={reatConfigured ? 'ok' : 'miss'}
          critical={!reatConfigured}
        />
      </div>

      {/* Drawers */}
      {drawer === 'followup'          && <DrawerFollowup          config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'followup_avancado' && <DrawerFollowupAvancado  config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'limite'            && <DrawerLimite    value={config.daily_limit} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ daily_limit: v }); setDrawer(null); }} />}
      {drawer === 'intervalo'         && <DrawerIntervalo config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'midia'             && <DrawerMidia     config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}

      {/* Modais */}
      {modal === 'optout'    && <ModalOptOut    config={config} onClose={() => setModal(null)} onSave={v => { onUpdate(v); setModal(null); }} />}
      {modal === 'lgpd'      && <ModalLGPD      config={config} onClose={() => setModal(null)} onSave={v => { onUpdate(v); setModal(null); }} />}
      {modal === 'reativacao'&& <ModalReativacao config={config} onClose={() => setModal(null)} onSave={v => { onUpdate(v); setModal(null); }} />}
    </>
  );
}

// ─── Componentes internos ─────────────────────────────────────

function EditCard({ label, value, sub, onClick, status, critical }: {
  label: string; value: string; sub: string; onClick: () => void;
  status: 'ok' | 'warn' | 'miss'; critical?: boolean;
}) {
  const borderColor = critical ? 'var(--o-hot-b)' : 'var(--o-b0)';
  const valueColor  = status === 'miss' ? 'var(--o-hot)' : status === 'warn' ? 'var(--o-warn)' : 'var(--o-text)';
  return (
    <div className="o-edit-card" style={{ borderColor }} onClick={onClick}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 13, color: valueColor, marginBottom: 4 }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 8 }}>{sub}</div>
      <span className={`o-badge ${status === 'ok' ? 'o-badge-ok' : status === 'warn' ? 'o-badge-warn' : 'o-badge-miss'}`}>
        {status === 'ok' ? 'Configurado' : status === 'warn' ? 'Parcial' : critical ? 'Crítico' : 'Pendente'}
      </span>
      <span className="o-edit-arrow">›</span>
    </div>
  );
}

function InfoCard({ label, value, sub, status }: { label: string; value: string; sub: string; status: 'ok' | 'miss' }) {
  return (
    <div className="o-edit-card" style={{ borderColor: status === 'ok' ? 'var(--o-act-b)' : 'var(--o-b0)' }}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 13, color: 'var(--o-text)', marginBottom: 4 }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 8 }}>{sub}</div>
      <span className={`o-badge ${status === 'ok' ? 'o-badge-ok' : 'o-badge-miss'}`}>
        {status === 'ok' ? 'Conectado' : 'Desconectado'}
      </span>
    </div>
  );
}

function SliderField({ label, value, min, max, step, format, onChange }: {
  label: string; value: number; min: number; max: number; step: number;
  format: (v: number) => string; onChange: (v: number) => void;
}) {
  return (
    <div className="o-field">
      {label && <label className="o-field-label">{label}</label>}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <input
          type="range" className="o-slider"
          min={min} max={max} step={step} value={value}
          onChange={e => onChange(Number(e.target.value))}
        />
        <span className="font-mono-orion" style={{ fontSize: 11, color: 'var(--o-text)', minWidth: 36, textAlign: 'right' }}>
          {format(value)}
        </span>
      </div>
    </div>
  );
}

function ToggleRow({ label, desc, value, onChange }: { label: string; desc: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="o-toggle-row">
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--o-text)' }}>{label}</div>
        <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, marginTop: 2 }}>{desc}</div>
      </div>
      <div className={`o-toggle ${value ? 'on' : ''}`} onClick={() => onChange(!value)} />
    </div>
  );
}

function OptCard({ selected, onClick, label, desc }: { selected: boolean; onClick: () => void; label: string; desc: string }) {
  return (
    <div className={`o-opt-card ${selected ? 'selected' : ''}`} onClick={onClick}>
      <div style={{
        width: 16, height: 16, borderRadius: '50%', flexShrink: 0, marginTop: 2,
        border: `2px solid ${selected ? 'var(--o-active)' : 'var(--o-b1)'}`,
        background: selected ? 'var(--o-active)' : 'transparent',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {selected && <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#fff' }} />}
      </div>
      <div>
        <div style={{ fontSize: 13.5, fontWeight: 500, marginBottom: 3, color: 'var(--o-text)' }}>{label}</div>
        <div style={{ fontSize: 12, color: 'var(--o-sub)', fontWeight: 300, lineHeight: 1.55 }}>{desc}</div>
      </div>
    </div>
  );
}

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

function ModalBase({ title, sub, onClose, onSave, children }: {
  title: string; sub: string; onClose: () => void; onSave: () => void; children: React.ReactNode;
}) {
  return (
    <div className="o-modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="o-modal">
        <div className="o-modal-header">
          <div>
            <div className="font-display" style={{ fontSize: 22, fontWeight: 400, color: 'var(--o-text)' }}>{title}</div>
            <div style={{ fontSize: 12, color: 'var(--o-sub)', fontWeight: 300, marginTop: 3 }}>{sub}</div>
          </div>
          <button className="o-close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="o-modal-body">{children}</div>
        <div className="o-modal-footer">
          <button className="o-btn o-btn-primary" onClick={onSave}>Salvar alterações</button>
          <button className="o-btn" onClick={onClose}>Cancelar</button>
        </div>
      </div>
    </div>
  );
}
