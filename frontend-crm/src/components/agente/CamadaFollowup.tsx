import { useState } from 'react';
import { FieldHelp } from './FieldHelp';
import { SuggestInput } from './SuggestField';
import type { AgentConfig } from '@/types/agente';

interface CamadaFollowupProps {
  config: AgentConfig;
  onUpdate: (partial: Partial<AgentConfig>) => void;
}

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

// ─── Drawer: Check-in automático de clientes (client-list) ────────────────
function DrawerFollowupCheckin({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [enabled, setEnabled] = useState(config.followup_checkin_auto_trigger_enabled);
  const [days, setDays] = useState(config.followup_checkin_inactivity_days);
  const [instructions, setInstructions] = useState(config.followup_checkin_instructions ?? '');

  return (
    <DrawerBase title="Check-in automático de clientes" sub="Envia um check-in sem pressão de venda quando um cliente (Lista de Clientes) fica inactivo" onClose={onClose}
      onSave={() => onSave({
        followup_checkin_auto_trigger_enabled: enabled,
        followup_checkin_inactivity_days: days,
        followup_checkin_instructions: instructions.trim() || null,
      })}>
      <ToggleRow
        label="Ativar check-in automático"
        desc="Sem isto, clientes que já compraram (Lista de Clientes) nunca recebem contacto automático depois disso"
        value={enabled}
        onChange={setEnabled}
      />
      <SliderField label="Dias de inactividade antes de disparar" value={days} min={7} max={90} step={1} format={v => `${v} dia${v === 1 ? '' : 's'}`} onChange={setDays} />
      <div className="o-field">
        <label className="o-field-label">Instrução personalizada (opcional)</label>
        <div className="o-field-hint">Deixar vazio usa o tom padrão: agradecer por ser cliente, sem pressão de venda, perguntar se quer agendar a próxima sessão.</div>
        <textarea className="o-input" rows={3} style={{ resize: 'vertical' }}
          value={instructions} onChange={e => setInstructions(e.target.value)}
          placeholder="Ex.: mencionar sempre o nome do serviço/pacote que o cliente comprou."
        />
      </div>
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

// ─── Drawer: Instrução genérica de follow-up por template ─────────────────────
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

type DrawerKey =
  | 'followup_avancado'
  | 'followup_auto'
  | 'followup_checkin'
  | 'followup_instrucoes'
  | 'followup_goal_instrs'
  | 'cart_recovery_attempts'
  | 'followup_outcome_instrs'
  | null;

export function CamadaFollowup({ config, onUpdate }: CamadaFollowupProps) {
  const [drawer, setDrawer] = useState<DrawerKey>(null);

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

  return (
    <>
      {/* Seção 1: Gatilho automático */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Seção 1 · Gatilho automático
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
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
        {!_isCloserAgent && (
          <EditCard
            label="Check-in automático de clientes"
            sub="Reengaja clientes (Lista de Clientes) inactivos, sem pressão de venda"
            value={config.followup_checkin_auto_trigger_enabled ? `Ativo · ${config.followup_checkin_inactivity_days} dia(s)` : 'Desativado'}
            onClick={() => setDrawer('followup_checkin')}
            status={config.followup_checkin_auto_trigger_enabled ? 'ok' : undefined}
            help="Quando ativo, o sistema envia um check-in automático para clientes já convertidos (Lista de Clientes) sem sessão/contacto há N dias — tom de relacionamento, nunca de venda nova."
          />
        )}
      </div>

      {/* Seção 2: Cadência e tentativas */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Seção 2 · Cadência e tentativas
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Follow-up avançado"
          sub={`Máx. ${config.followup_max_attempts} tentativas · ${config.followup_allowed_hours}`}
          value={`Cadência: ${config.followup_cadence || 'não configurada'}`}
          onClick={() => setDrawer('followup_avancado')} status="ok"
          help="Parâmetros avançados: máximo de tentativas (após isso o lead é arquivado), horário permitido de envio e cadência personalizada em minutos."
        />
      </div>

      {/* Seção 3: Instruções de conteúdo */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Seção 3 · Instruções de conteúdo
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label={`Instrução de follow-up · ${_fuInstrLabel}`}
          sub="Personalização do negócio para as mensagens automáticas"
          value={_fuInstrValue ? _fuInstrValue.slice(0, 60) + (_fuInstrValue.length > 60 ? '…' : '') : 'Não configurado (usa padrão do agente)'}
          onClick={() => setDrawer('followup_instrucoes')}
          status={_fuInstrValue ? 'ok' : undefined}
          help="Instrução de texto livre injectada no prompt de follow-up — permite personalizar o que o bot diz com base no contexto real do teu negócio."
        />
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

      {/* Seção 4: Qualificação e follow-up */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Seção 4 · Qualificação e follow-up
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <div className="o-edit-card" onClick={() => onUpdate({ nurture_vs_discard_rule: !config.nurture_vs_discard_rule })}>
          <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6, display: 'flex', alignItems: 'center' }}>Nurture vs Descarte <FieldHelp text="Leads abaixo do score mínimo (configurado em Qualificação → Score mínimo): Nurture — continua recebendo conteúdo e pode avançar depois; Descarte — arquivado imediatamente." /></div>
          <div style={{ fontSize: 13, color: 'var(--o-text)', marginBottom: 4 }}>{config.nurture_vs_discard_rule ? 'Nurture passivo' : 'Descarte imediato'}</div>
          <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 8 }}>Depende do "Score mínimo" em Camada 2 · Qualificação</div>
          <span className={`o-badge ${config.nurture_vs_discard_rule ? 'o-badge-ok' : 'o-badge-warn'}`}>
            {config.nurture_vs_discard_rule ? 'Nurture ativo' : 'Descarte'}
          </span>
          <span className="o-edit-arrow">›</span>
        </div>
      </div>

      {/* Drawers */}
      {drawer === 'followup_avancado'      && <DrawerFollowupAvancado            config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'followup_auto'          && <DrawerFollowupAutomatico          config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'followup_checkin'       && <DrawerFollowupCheckin             config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'followup_instrucoes'    && <DrawerFollowUpInstructions        config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'followup_goal_instrs'   && <DrawerFollowupGoalInstructions    config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'cart_recovery_attempts' && <DrawerCartRecoveryAttempts        config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
      {drawer === 'followup_outcome_instrs'&& <DrawerFollowupOutcomeInstructions config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />}
    </>
  );
}

// ─── Componentes internos ─────────────────────────────────────

function EditCard({ label, value, sub, onClick, status, critical, help }: {
  label: string; value: string; sub: string; onClick: () => void;
  status: 'ok' | 'warn' | 'miss' | undefined; critical?: boolean; help?: string;
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
