import { useState } from 'react';
import { FieldHelp } from './FieldHelp';
import { SuggestInput } from './SuggestField';
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

// ─── Presets de delay ─────────────────────────────────────────
const FIRST_REPLY_PRESETS = [
  { key: 'imediato', label: 'Imediato',      desc: 'Responde assim que a mensagem chega',        min: 0,   max: 0    },
  { key: 'rapido',   label: 'Rápido',        desc: '1–3 minutos de delay',                       min: 60,  max: 180  },
  { key: 'normal',   label: 'Normal',        desc: '5–15 minutos — padrão recomendado',          min: 300, max: 900  },
  { key: 'lento',    label: 'Lento',         desc: '15–60 minutos — máxima humanização',         min: 900, max: 3600 },
  { key: 'custom',   label: 'Personalizado', desc: 'Defina o intervalo manualmente com sliders', min: -1,  max: -1   },
];
const REPLY_PRESETS = [
  { key: 'imediato', label: 'Imediato',      desc: 'Responde sem delay',                         min: 0,  max: 0   },
  { key: 'rapido',   label: 'Rápido',        desc: '5–15 segundos',                              min: 5,  max: 15  },
  { key: 'normal',   label: 'Normal',        desc: '15 segundos a 1 minuto — padrão recomendado',min: 15, max: 60  },
  { key: 'lento',    label: 'Lento',         desc: '1–3 minutos',                                min: 60, max: 180 },
  { key: 'custom',   label: 'Personalizado', desc: 'Defina o intervalo manualmente com sliders', min: -1, max: -1  },
];
function detectPreset(presets: typeof FIRST_REPLY_PRESETS, min: number, max: number): string {
  return presets.find(p => p.min === min && p.max === max)?.key ?? 'custom';
}

// ─── Drawer: Delay de resposta ────────────────────────────────
function DrawerDelayResposta({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [frPreset, setFrPreset] = useState(() => detectPreset(FIRST_REPLY_PRESETS, config.first_reply_delay_min_seconds, config.first_reply_delay_max_seconds));
  const [frMin, setFrMin] = useState(config.first_reply_delay_min_seconds);
  const [frMax, setFrMax] = useState(config.first_reply_delay_max_seconds);
  const [rPreset, setRPreset]   = useState(() => detectPreset(REPLY_PRESETS, config.reply_delay_min_seconds, config.reply_delay_max_seconds));
  const [rMin,  setRMin]  = useState(config.reply_delay_min_seconds);
  const [rMax,  setRMax]  = useState(config.reply_delay_max_seconds);
  const [bufSecs, setBufSecs] = useState(config.multi_message_buffer_seconds ?? 8);

  function selectFrPreset(p: typeof FIRST_REPLY_PRESETS[number]) {
    setFrPreset(p.key);
    if (p.key !== 'custom') { setFrMin(p.min); setFrMax(p.max); }
  }
  function selectRPreset(p: typeof REPLY_PRESETS[number]) {
    setRPreset(p.key);
    if (p.key !== 'custom') { setRMin(p.min); setRMax(p.max); }
  }

  const fmtFirst = (v: number) => v === 0 ? 'imediato' : v < 60 ? `${v}s` : `${Math.round(v / 60)}min`;
  const fmtReply = (v: number) => v === 0 ? 'imediato' : `${v}s`;
  const fmtBuf = (v: number) => {
    if (v === 0) return 'Desabilitado';
    if (v < 60) return `${v}s`;
    const h = Math.floor(v / 3600);
    const m = Math.floor((v % 3600) / 60);
    const s = v % 60;
    if (h > 0) return m === 0 ? `${h}h` : `${h}h ${m}min`;
    return s === 0 ? `${m}min` : `${m}min ${s}s`;
  };

  return (
    <DrawerBase title="Delay de resposta" sub="Simula tempo de leitura e digitação humana — aumenta taxa de abertura" onClose={onClose}
      onSave={() => onSave({ first_reply_delay_min_seconds: frMin, first_reply_delay_max_seconds: frMax, reply_delay_min_seconds: rMin, reply_delay_max_seconds: rMax, multi_message_buffer_seconds: bufSecs })}>

      <div className="o-field">
        <label className="o-field-label">Absorção de mensagens consecutivas</label>
        <div className="o-field-hint">
          Quando o lead envia várias mensagens em sequência, o agente aguarda este período antes de responder,
          acumulando todas as mensagens em uma única resposta. Evita respostas fragmentadas e dá uma sensação mais natural.
          Defina 0 para desabilitar.
        </div>
        <SliderField label={fmtBuf(bufSecs)} value={bufSecs} min={0} max={7200} step={30} format={fmtBuf} onChange={setBufSecs} />
      </div>

      <div className="o-field" style={{ marginTop: 8 }}>
        <label className="o-field-label">Primeira mensagem (novo lead)</label>
        <div className="o-field-hint">Delay antes de responder o primeiro contato. Aplicado quando buffer está desabilitado ou não há mensagens acumuladas. O lead verá "Digitando..." durante o período.</div>
        {FIRST_REPLY_PRESETS.map(p => (
          <OptCard key={p.key} selected={frPreset === p.key} onClick={() => selectFrPreset(p)} label={p.label} desc={p.desc} />
        ))}
        {frPreset === 'custom' && (
          <>
            <SliderField label="Mínimo" value={frMin} min={0} max={7200} step={60} format={fmtFirst} onChange={setFrMin} />
            <SliderField label="Máximo" value={frMax} min={0} max={7200} step={60} format={fmtFirst} onChange={setFrMax} />
          </>
        )}
      </div>

      <div className="o-field" style={{ marginTop: 8 }}>
        <label className="o-field-label">Dentro da conversa</label>
        <div className="o-field-hint">Delay antes de cada resposta subsequente. Aplicado quando buffer está desabilitado.</div>
        {REPLY_PRESETS.map(p => (
          <OptCard key={p.key} selected={rPreset === p.key} onClick={() => selectRPreset(p)} label={p.label} desc={p.desc} />
        ))}
        {rPreset === 'custom' && (
          <>
            <SliderField label="Mínimo" value={rMin} min={0} max={300} step={5} format={fmtReply} onChange={setRMin} />
            <SliderField label="Máximo" value={rMax} min={0} max={300} step={5} format={fmtReply} onChange={setRMax} />
          </>
        )}
      </div>
    </DrawerBase>
  );
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
    <DrawerBase title="Mídia inválida" sub="O que fazer quando o lead envia vídeo, figurinha, reação ou áudio sem transcrição ativa" onClose={onClose} onSave={() => onSave({ media_fallback: fallback, media_fallback_msg: msg })}>
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

// ─── Drawer: Janela de horário ────────────────────────────────
const DAYS = [
  { key: 'mon', label: 'Seg' }, { key: 'tue', label: 'Ter' },
  { key: 'wed', label: 'Qua' }, { key: 'thu', label: 'Qui' },
  { key: 'fri', label: 'Sex' }, { key: 'sat', label: 'Sáb' },
  { key: 'sun', label: 'Dom' },
];
type DaySchedule  = { enabled: boolean; start: string; end: string };
type WeekSchedule = Record<string, DaySchedule>;

const DAY_DEFAULTS: WeekSchedule = {
  mon: { enabled: true,  start: '09:00', end: '18:00' },
  tue: { enabled: true,  start: '09:00', end: '18:00' },
  wed: { enabled: true,  start: '09:00', end: '18:00' },
  thu: { enabled: true,  start: '09:00', end: '18:00' },
  fri: { enabled: true,  start: '09:00', end: '18:00' },
  sat: { enabled: false, start: '09:00', end: '18:00' },
  sun: { enabled: false, start: '09:00', end: '18:00' },
};

function parseCustomSchedule(json: string): WeekSchedule {
  const result: WeekSchedule = JSON.parse(JSON.stringify(DAY_DEFAULTS));
  try {
    const data = JSON.parse(json);
    for (const [k, val] of Object.entries(data)) {
      if (k in result && typeof val === 'string') {
        if (val) {
          const parts = val.split('-');
          result[k] = parts.length === 2
            ? { enabled: true, start: parts[0], end: parts[1] }
            : { ...result[k], enabled: false };
        } else {
          result[k] = { ...result[k], enabled: false };
        }
      }
    }
  } catch { /* usa defaults */ }
  return result;
}

function serializeCustomSchedule(s: WeekSchedule): string {
  const obj: Record<string, string> = {};
  for (const [k, v] of Object.entries(s)) obj[k] = v.enabled ? `${v.start}-${v.end}` : '';
  return JSON.stringify(obj);
}

function DrawerHorarioTrabalho({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [mode, setMode] = useState(config.availability_mode);
  const [schedule, setSchedule] = useState<WeekSchedule>(() => parseCustomSchedule(config.availability_schedule));

  function toggleDay(key: string) {
    setSchedule(prev => ({ ...prev, [key]: { ...prev[key], enabled: !prev[key].enabled } }));
  }
  function setTime(key: string, field: 'start' | 'end', value: string) {
    setSchedule(prev => ({ ...prev, [key]: { ...prev[key], [field]: value } }));
  }

  return (
    <DrawerBase title="Janela de horário" sub="Define quando o agente está disponível para responder — mensagens fora do horário são agendadas para a próxima janela" onClose={onClose}
      onSave={() => onSave({ availability_mode: mode, availability_schedule: mode === 'custom' ? serializeCustomSchedule(schedule) : config.availability_schedule })}>

      <div className="o-field">
        <label className="o-field-label">Disponibilidade</label>
        <OptCard selected={mode === '24h'}            onClick={() => setMode('24h')}            label="24 horas"           desc="O agente responde a qualquer hora, todos os dias." />
        <OptCard selected={mode === 'business_hours'} onClick={() => setMode('business_hours')} label="Horário comercial"  desc="Segunda a sexta, 09:00–18:00 — fuso configurado na Camada 1." />
        <OptCard selected={mode === 'custom'}         onClick={() => setMode('custom')}         label="Personalizado"      desc="Defina dias e horários específicos manualmente." />
      </div>

      {mode === 'custom' && (
        <div className="o-field" style={{ marginTop: 8 }}>
          <label className="o-field-label">Agenda personalizada</label>
          <div className="o-field-hint">Fuso horário configurado na Camada 1. Mensagens fora do horário são agendadas para a próxima abertura.</div>
          {DAYS.map(({ key, label }) => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <div className={`o-toggle ${schedule[key].enabled ? 'on' : ''}`} onClick={() => toggleDay(key)} style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: 'var(--o-sub)', width: 28, flexShrink: 0 }}>{label}</span>
              {schedule[key].enabled ? (
                <>
                  <input type="time" className="o-input" style={{ width: 90, padding: '3px 8px', fontSize: 12 }}
                    value={schedule[key].start} onChange={e => setTime(key, 'start', e.target.value)} />
                  <span style={{ fontSize: 12, color: 'var(--o-sub)' }}>–</span>
                  <input type="time" className="o-input" style={{ width: 90, padding: '3px 8px', fontSize: 12 }}
                    value={schedule[key].end} onChange={e => setTime(key, 'end', e.target.value)} />
                </>
              ) : (
                <span style={{ fontSize: 11, color: 'var(--o-dim)' }}>Indisponível</span>
              )}
            </div>
          ))}
        </div>
      )}
    </DrawerBase>
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
        <SuggestInput
          className="o-input"
          value={allowedHours}
          onChange={e => setAllowedHours(e.target.value)}
          placeholder="08:00-20:00"
        />
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Follow-up automático (gatilho por inatividade) ───────────────
function DrawerFollowupAutomatico({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [enabled, setEnabled] = useState(config.followup_auto_trigger_enabled);
  const [days, setDays] = useState(config.followup_auto_trigger_inactivity_days);

  return (
    <DrawerBase title="Follow-up automático" sub="Inicia o follow-up sozinho quando o lead fica em silêncio" onClose={onClose}
      onSave={() => onSave({ followup_auto_trigger_enabled: enabled, followup_auto_trigger_inactivity_days: days })}>
      <ToggleRow
        label="Ativar disparo automático"
        desc="Sem isto, o follow-up só começa quando você arrasta o card manualmente para a coluna Follow-up"
        value={enabled}
        onChange={setEnabled}
      />
      <SliderField label="Dias de silêncio antes de disparar" value={days} min={1} max={14} step={1} format={v => `${v} dia${v === 1 ? '' : 's'}`} onChange={setDays} />
    </DrawerBase>
  );
}

// ─── Drawer: Follow-up goal instructions (Agent 1) ───────────────────────────
function DrawerFollowupGoalInstructions({
  config, onSave, onClose,
}: { config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void }) {
  const goals = [
    { key: 'advance_closing', label: 'Avançar fechamento', hint: 'Lead saiu quente/morno e o objectivo é fechar.' },
    { key: 'nurture', label: 'Nutrir relacionamento', hint: 'Lead precisa de mais tempo — sem pressão comercial.' },
    { key: 'reschedule_conversation', label: 'Reagendar conversa', hint: 'Reunião não aconteceu ou lead pediu recontacto.' },
  ] as const;
  const init = config.followup_goal_instructions ?? {};
  const [vals, setVals] = useState<Record<string, string>>({
    advance_closing: init.advance_closing ?? '',
    nurture: init.nurture ?? '',
    reschedule_conversation: init.reschedule_conversation ?? '',
  });
  function handleSave() {
    const result: Record<string, string> = {};
    for (const { key } of goals) { if (vals[key].trim()) result[key] = vals[key].trim(); }
    onSave({ followup_goal_instructions: Object.keys(result).length ? result : null });
  }
  return (
    <DrawerBase title="Instrução por objectivo de follow-up" sub="Agent 1 — personaliza a abordagem consoante o goal escolhido no modal de transição" onClose={onClose} onSave={handleSave}>
      {goals.map(({ key, label, hint }) => (
        <div key={key} className="o-field">
          <label className="o-field-label">{label}</label>
          <div className="o-field-hint">{hint}</div>
          <textarea className="o-input" rows={3} style={{ resize: 'vertical' }}
            value={vals[key]} onChange={e => setVals(v => ({ ...v, [key]: e.target.value }))}
            placeholder="Deixar vazio usa o comportamento padrão do agente."
          />
        </div>
      ))}
    </DrawerBase>
  );
}

// ─── Drawer: Cart recovery attempt instructions (Agent 2) ─────────────────────
function DrawerCartRecoveryAttempts({
  config, onSave, onClose,
}: { config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void }) {
  const defaults = [
    { label: '1ª tentativa', hint: 'Default: lembrete neutro — pedido reservado, sem pressão.' },
    { label: '2ª tentativa', hint: 'Default: reforçar benefício + antecipar objeção mais comum.' },
    { label: '3ª tentativa', hint: 'Default: urgência máxima — oferta expira hoje, CTA directo.' },
  ];
  const init = config.cart_recovery_attempt_instructions ?? [null, null, null];
  const [vals, setVals] = useState<[string, string, string]>([
    init[0] ?? '', init[1] ?? '', init[2] ?? '',
  ]);
  function handleSave() {
    const result: [string | null, string | null, string | null] = [
      vals[0].trim() || null, vals[1].trim() || null, vals[2].trim() || null,
    ];
    onSave({ cart_recovery_attempt_instructions: result.some(Boolean) ? result : null });
  }
  return (
    <DrawerBase title="Instrução por tentativa — recuperação de carrinho" sub="Agent 2 — personaliza o que o bot diz em cada tentativa de recuperação" onClose={onClose} onSave={handleSave}>
      {defaults.map(({ label, hint }, i) => (
        <div key={i} className="o-field">
          <label className="o-field-label">{label}</label>
          <div className="o-field-hint">{hint}</div>
          <textarea className="o-input" rows={3} style={{ resize: 'vertical' }}
            value={vals[i]} onChange={e => setVals(prev => { const n = [...prev] as [string,string,string]; n[i] = e.target.value; return n; })}
            placeholder="Deixar vazio usa o comportamento padrão do agente."
          />
        </div>
      ))}
    </DrawerBase>
  );
}

// ─── Drawer: Follow-up outcome instructions (Agent 3) ─────────────────────────
function DrawerFollowupOutcomeInstructions({
  config, onSave, onClose,
}: { config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void }) {
  const outcomes = [
    { key: 'interested_not_closed', label: 'Interessado, mas não fechou', hint: 'Default: retomar contexto, remover objeção, propor nova data.' },
    { key: 'reschedule_needed', label: 'Precisa remarcar', hint: 'Default: oferecer 2-3 horários directamente, pergunta fechada.' },
    { key: 'converted', label: 'Convertido', hint: 'Default: boas-vindas, confirmar próximo passo, link de pagamento.' },
  ] as const;
  const init = config.followup_outcome_instructions ?? {};
  const [vals, setVals] = useState<Record<string, string>>({
    interested_not_closed: init.interested_not_closed ?? '',
    reschedule_needed: init.reschedule_needed ?? '',
    converted: init.converted ?? '',
  });
  function handleSave() {
    const result: Record<string, string> = {};
    for (const { key } of outcomes) { if (vals[key].trim()) result[key] = vals[key].trim(); }
    onSave({ followup_outcome_instructions: Object.keys(result).length ? result : null });
  }
  return (
    <DrawerBase title="Instrução por outcome da sessão" sub="Agent 3 — personaliza o que o bot diz consoante como terminou a sessão/reunião" onClose={onClose} onSave={handleSave}>
      {outcomes.map(({ key, label, hint }) => (
        <div key={key} className="o-field">
          <label className="o-field-label">{label}</label>
          <div className="o-field-hint">{hint}</div>
          <textarea className="o-input" rows={3} style={{ resize: 'vertical' }}
            value={vals[key]} onChange={e => setVals(v => ({ ...v, [key]: e.target.value }))}
            placeholder="Deixar vazio usa o comportamento padrão do agente."
          />
        </div>
      ))}
    </DrawerBase>
  );
}

function DrawerFollowUpInstructions({
  config, onSave, onClose,
}: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const isCloser = config.template_key?.includes('closer');
  const isHybrid = config.template_key?.includes('hybrid');
  const fieldKey = isCloser
    ? 'followup_recovery_instructions'
    : isHybrid
    ? 'followup_postsession_instructions'
    : 'followup_sdr_instructions';
  const title = isCloser
    ? 'Instrução de recuperação de carrinho'
    : isHybrid
    ? 'Instrução de follow-up pós-sessão'
    : 'Instrução de follow-up pós-reunião';
  const hint = isCloser
    ? 'Personaliza o que o bot diz nas mensagens de recuperação de carrinho (Agent 2). O bot já sabe em que tentativa está — podes referenciar isso.'
    : isHybrid
    ? 'Personaliza o que o bot diz após cada tipo de sessão (interessado mas não fechou, remarcação, convertido). O bot já conhece o outcome.'
    : 'Personaliza o que o bot diz nas mensagens de follow-up pós-reunião (Agent 1). O bot já conhece o outcome (quente/morno/frio) e o objetivo escolhido.';
  const [value, setValue] = useState<string>(config[fieldKey] ?? '');
  return (
    <DrawerBase title={title} sub="Personalização do negócio — injectada antes das regras genéricas" onClose={onClose}
      onSave={() => onSave({ [fieldKey]: value || null } as Partial<AgentConfig>)}>
      <div className="o-field">
        <label className="o-field-label">{title}</label>
        <div className="o-field-hint">{hint}</div>
        <textarea
          className="o-input"
          rows={6}
          value={value}
          onChange={e => setValue(e.target.value)}
          placeholder="Ex.: Nunca menciones preço — isso é papel do humano. Quando o lead estiver morno, referencia o caso do cliente X..."
          style={{ resize: 'vertical' }}
        />
        <div style={{ fontSize: 10, color: 'var(--o-sub)', marginTop: 4 }}>
          Deixar vazio usa o comportamento padrão do agente.
        </div>
      </div>
    </DrawerBase>
  );
}

type DrawerKey = 'followup' | 'followup_avancado' | 'followup_auto' | 'followup_instrucoes' | 'followup_goal_instrs' | 'cart_recovery_attempts' | 'followup_outcome_instrs' | 'limite' | 'intervalo' | 'midia' | 'delay_resposta' | 'horario_trabalho' | null;
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

  const _isCloserAgent = config.template_key?.includes('closer');
  const _isHybridAgent = config.template_key?.includes('hybrid');
  const _fuInstrValue = _isCloserAgent
    ? config.followup_recovery_instructions
    : _isHybridAgent
    ? config.followup_postsession_instructions
    : config.followup_sdr_instructions;
  const _fuInstrLabel = _isCloserAgent
    ? 'Recuperação de carrinho'
    : _isHybridAgent
    ? 'Pós-sessão'
    : 'Pós-reunião';

  const fmtDelayFirst = (v: number) => v === 0 ? 'imediato' : v < 60 ? `${v}s` : `${Math.round(v / 60)}min`;
  const delayFirstLabel = config.first_reply_delay_max_seconds > 0
    ? `${fmtDelayFirst(config.first_reply_delay_min_seconds)}–${fmtDelayFirst(config.first_reply_delay_max_seconds)}`
    : 'Imediato';
  const delayReplyLabel = config.reply_delay_max_seconds > 0
    ? `${config.reply_delay_min_seconds}–${config.reply_delay_max_seconds}s`
    : 'Imediato';
  const fmtBufLabel = (v: number) => {
    if (!v || v <= 0) return 'buffer off';
    if (v < 60) return `buffer ${v}s`;
    const h = Math.floor(v / 3600);
    const m = Math.floor((v % 3600) / 60);
    if (h > 0) return m === 0 ? `buffer ${h}h` : `buffer ${h}h ${m}min`;
    return `buffer ${m}min`;
  };
  const bufferLabel = fmtBufLabel(config.multi_message_buffer_seconds ?? 0);
  const availabilityLabel = config.availability_mode === 'business_hours'
    ? 'Seg–Sex · 09–18h'
    : config.availability_mode === 'custom'
    ? 'Personalizado'
    : '24h (sempre ativo)';

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
        <EditCard label="Intervalo entre mensagens" value={`${config.interval_min}–${config.interval_max} segundos`} sub="Delay simulado de comportamento humano" onClick={() => setDrawer('intervalo')} status="ok" help="Intervalo aleatório entre mensagens consecutivas. Simula comportamento humano e reduz risco de ban pelo WhatsApp. Valores muito baixos aumentam a suspeita de automação." />
        <EditCard label="Limite diário de disparos" value={`${config.daily_limit} mensagens/dia`} sub="Proteção comportamental" onClick={() => setDrawer('limite')} status="ok" help="Limite de disparos por dia neste número. Recomendado 150–300 para uso regular. Acima disso aumenta o risco de detecção e bloqueio pelo WhatsApp." />
        <EditCard
          label="Delay de resposta" sub="Tempo antes de responder o lead"
          value={`${bufferLabel} · 1ª msg: ${delayFirstLabel} · conversa: ${delayReplyLabel}`}
          onClick={() => setDrawer('delay_resposta')} status="ok"
          help="Buffer acumula mensagens consecutivas do lead antes de responder (evita respostas fragmentadas). Delays simulam tempo humano de leitura e digitação — o lead vê 'Digitando...' durante o período."
        />
        <EditCard
          label="Janela de horário" sub="Período em que o agente responde"
          value={availabilityLabel}
          onClick={() => setDrawer('horario_trabalho')} status="ok"
          help="Controla quando o agente está disponível para responder. Mensagens recebidas fora do horário são agendadas para a próxima abertura da janela (não são descartadas)."
        />
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
        <div className="o-edit-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 10 }}>
          <div>
            <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6 }}>Receber áudio</div>
            <div style={{ fontSize: 13, color: 'var(--o-text)', marginBottom: 4 }}>
              {config.audio_transcription_enabled ? 'Transcrição ativa' : 'Desativado'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 8 }}>
              Transcreve o áudio do lead via IA e responde normalmente. Se desativado, segue Mídia inválida.
            </div>
          </div>
          <ToggleRow
            label="Ativar transcrição de áudio"
            desc="Usa Whisper (OpenAI) — requer OPENAI_API_KEY no servidor"
            value={config.audio_transcription_enabled ?? false}
            onChange={v => onUpdate({ audio_transcription_enabled: v })}
          />
        </div>
        <EditCard
          label="Mídia inválida" sub="Vídeo, figurinha, reação e áudio sem transcrição"
          value={MEDIA_FALLBACK_LABELS[config.media_fallback] || config.media_fallback || '—'}
          onClick={() => setDrawer('midia')} status={mediaConfigured ? 'ok' : 'warn'}
          help="O que fazer quando o lead envia mídia não processável. Áudio com 'Receber áudio' ativo é transcrito e não cai neste fluxo."
        />
        <EditCard
          label="Opt-out por palavra-chave" sub="STOP · PARAR · SAIR · CANCELAR"
          value={optoutConfigured ? `${config.opt_out_keywords.length} palavras configuradas` : 'Não configurado'}
          onClick={() => setModal('optout')} status={optoutConfigured ? 'ok' : 'miss'}
          critical={!optoutConfigured}
          help="Palavras que indicam que o lead quer parar de receber mensagens. Crítico: sem configuração, o bot continua contatando quem pediu para parar — risco direto de ban do número."
        />
        <EditCard
          label="Consentimento LGPD" sub="Lei brasileira — obrigatório"
          value={LGPD_LABELS[config.lgpd_mode] || 'Não configurado'}
          onClick={() => setModal('lgpd')} status={lgpdConfigured ? 'ok' : 'miss'}
          critical={!lgpdConfigured}
          help="Define quando o agente coleta consentimento de uso de dados. Obrigatório por lei brasileira (LGPD). Pode ser implícito (inbound), explícito (confirmação) ou apenas no outbound."
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
          help="Intervalos da cadência de follow-up após silêncio do lead (1ª, 2ª e 3ª tentativa). Cadências muito curtas parecem spam; muito longas perdem o momento de compra."
        />
        <EditCard
          label="Follow-up avançado"
          sub={`Máx. ${config.followup_max_attempts} tentativas · ${config.followup_allowed_hours}`}
          value={`Cadência: ${config.followup_cadence || 'não configurada'}`}
          onClick={() => setDrawer('followup_avancado')} status="ok"
          help="Parâmetros avançados: máximo de tentativas (após isso o lead é arquivado), horário permitido de envio e cadência personalizada em minutos."
        />
        {!_isCloserAgent && (
          <EditCard
            label="Follow-up automático"
            sub="Dispara sozinho quando o lead fica em silêncio em Apresentação"
            value={config.followup_auto_trigger_enabled ? `Ativo · ${config.followup_auto_trigger_inactivity_days} dia(s)` : 'Desativado'}
            onClick={() => setDrawer('followup_auto')}
            status={config.followup_auto_trigger_enabled ? 'ok' : undefined}
            help="Quando ativo, o sistema cria o follow-up automaticamente para leads de Apresentação sem resposta há N dias — sem depender do operador arrastar o card."
          />
        )}
        <EditCard
          label={`Instrução de follow-up · ${_fuInstrLabel}`}
          sub="Personalização do negócio para as mensagens automáticas"
          value={_fuInstrValue ? _fuInstrValue.slice(0, 60) + (_fuInstrValue.length > 60 ? '…' : '') : 'Não configurado (usa padrão do agente)'}
          onClick={() => setDrawer('followup_instrucoes')}
          status={_fuInstrValue ? 'ok' : undefined}
          help="Instrução de texto livre injectada no prompt de follow-up — permite personalizar o que o bot diz com base no contexto real do teu negócio."
        />
        {/* Fase 6 — goal instructions (Agent 1) */}
        {!_isCloserAgent && !_isHybridAgent && (
          <EditCard
            label="Instrução por objectivo · Pós-reunião"
            sub="Personaliza a abordagem consoante o goal escolhido no modal"
            value={config.followup_goal_instructions
              ? `${Object.keys(config.followup_goal_instructions).length} goal(s) configurado(s)`
              : 'Não configurado (usa padrão do agente)'}
            onClick={() => setDrawer('followup_goal_instrs')}
            status={config.followup_goal_instructions ? 'ok' : undefined}
            help="Define o que o bot deve fazer especificamente para cada objectivo: avançar fechamento, nutrir ou reagendar. Sobrescreve o comportamento genérico da variante."
          />
        )}
        {/* Fase 7 — attempt instructions (Agent 2) */}
        {_isCloserAgent && (
          <EditCard
            label="Instrução por tentativa · Carrinho"
            sub="Personaliza o conteúdo de cada tentativa de recuperação"
            value={config.cart_recovery_attempt_instructions?.some(Boolean)
              ? `${config.cart_recovery_attempt_instructions.filter(Boolean).length} tentativa(s) personalizada(s)`
              : 'Não configurado (usa padrão do agente)'}
            onClick={() => setDrawer('cart_recovery_attempts')}
            status={config.cart_recovery_attempt_instructions?.some(Boolean) ? 'ok' : undefined}
            help="Personaliza o que o bot diz em cada uma das 3 tentativas de recuperação de carrinho: 1ª lembrete, 2ª benefício/objeção, 3ª urgência. Usa os activos reais do teu negócio."
          />
        )}
        {/* Fase 8 — outcome instructions (Agent 3) */}
        {_isHybridAgent && (
          <EditCard
            label="Instrução por outcome · Pós-sessão"
            sub="Personaliza a abordagem consoante como terminou a sessão"
            value={config.followup_outcome_instructions
              ? `${Object.keys(config.followup_outcome_instructions).length} outcome(s) configurado(s)`
              : 'Não configurado (usa padrão do agente)'}
            onClick={() => setDrawer('followup_outcome_instrs')}
            status={config.followup_outcome_instructions ? 'ok' : undefined}
            help="Define instruções específicas para cada resultado de sessão: interessado mas não fechou, precisa remarcar, ou convertido. Sobrescreve os defaults genéricos do agente."
          />
        )}
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
          help="O que acontece quando um lead arquivado envia uma mensagem espontaneamente: reativar o bot, reiniciar o fluxo, retomar do ponto exato, ou apenas notificar o operador sem responder."
        />
      </div>

      {/* Drawers */}
      {drawer === 'followup'            && <DrawerFollowup            config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'followup_avancado'   && <DrawerFollowupAvancado    config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'followup_auto'       && <DrawerFollowupAutomatico  config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'followup_instrucoes'    && <DrawerFollowUpInstructions        config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'followup_goal_instrs'  && <DrawerFollowupGoalInstructions    config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'cart_recovery_attempts'&& <DrawerCartRecoveryAttempts        config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'followup_outcome_instrs'&&<DrawerFollowupOutcomeInstructions config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'limite'            && <DrawerLimite    value={config.daily_limit} onClose={() => setDrawer(null)} onSave={v => { onUpdate({ daily_limit: v }); setDrawer(null); }} />}
      {drawer === 'intervalo'         && <DrawerIntervalo config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'midia'             && <DrawerMidia           config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'delay_resposta'    && <DrawerDelayResposta   config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'horario_trabalho'  && <DrawerHorarioTrabalho config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}

      {/* Modais */}
      {modal === 'optout'    && <ModalOptOut    config={config} onClose={() => setModal(null)} onSave={v => { onUpdate(v); setModal(null); }} />}
      {modal === 'lgpd'      && <ModalLGPD      config={config} onClose={() => setModal(null)} onSave={v => { onUpdate(v); setModal(null); }} />}
      {modal === 'reativacao'&& <ModalReativacao config={config} onClose={() => setModal(null)} onSave={v => { onUpdate(v); setModal(null); }} />}
    </>
  );
}

// ─── Componentes internos ─────────────────────────────────────

function EditCard({ label, value, sub, onClick, status, critical, help }: {
  label: string; value: string; sub: string; onClick: () => void;
  status: 'ok' | 'warn' | 'miss'; critical?: boolean; help?: string;
}) {
  const borderColor = critical ? 'var(--o-hot-b)' : 'var(--o-b0)';
  const valueColor  = status === 'miss' ? 'var(--o-hot)' : status === 'warn' ? 'var(--o-warn)' : 'var(--o-text)';
  return (
    <div className="o-edit-card" style={{ borderColor }} onClick={onClick}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6, display: 'flex', alignItems: 'center' }}>{label}{help && <FieldHelp text={help} />}</div>
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
