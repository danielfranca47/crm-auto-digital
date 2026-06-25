import { useState } from 'react';
import { FieldHelp } from './FieldHelp';
import { SuggestInput } from './SuggestField';
import type { AgentConfig } from '@/types/agente';
import { CALENDAR_INTEGRATION_LABELS, BRIEFING_CHANNEL_LABELS, SCHEDULING_OFFER_STYLE_LABELS } from '@/types/agente';

interface CamadaApresentacaoProps {
  config: AgentConfig;
  onUpdate: (partial: Partial<AgentConfig>) => void;
}

// ─── Drawer: Dossiê pré-reunião ───────────────────────────────
function DrawerBriefing({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [enabled, setEnabled]     = useState(config.briefing_enabled);
  const [channel, setChannel]     = useState(config.briefing_channel);
  const [leadTime, setLeadTime]   = useState(config.briefing_lead_time);
  const [whatsapp, setWhatsapp]   = useState(config.operator_whatsapp);

  return (
    <DrawerBase title="Dossiê pré-reunião" sub="Resumo do lead enviado automaticamente ao operador antes da reunião" onClose={onClose}
      onSave={() => onSave({ briefing_enabled: enabled, briefing_channel: channel, briefing_lead_time: leadTime, operator_whatsapp: whatsapp })}>
      <div className="o-field">
        <label className="o-field-label">Ativar envio automático de dossiê</label>
        <div className="o-toggle-row">
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--o-text)' }}>Envio automático</div>
            <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, marginTop: 2 }}>O agente prepara um resumo do lead antes da reunião</div>
          </div>
          <div className={`o-toggle ${enabled ? 'on' : ''}`} onClick={() => setEnabled(!enabled)} />
        </div>
      </div>

      {enabled && (
        <>
          <div className="o-field">
            <label className="o-field-label">Canal de entrega</label>
            <select className="o-select" value={channel} onChange={e => setChannel(e.target.value)}>
              <option value="whatsapp">WhatsApp</option>
              <option value="internal">Interno (CRM)</option>
            </select>
          </div>
          <SliderField label="Horas antes da reunião" value={leadTime} min={1} max={24} step={1} format={v => `${v}h antes`} onChange={setLeadTime} />
          {channel === 'whatsapp' && (
            <div className="o-field">
              <label className="o-field-label">Número do operador (WhatsApp)</label>
              <div className="o-field-hint">Formato internacional: +5511999999999</div>
              <SuggestInput
                className="o-input"
                type="tel"
                value={whatsapp}
                onChange={e => setWhatsapp(e.target.value)}
                placeholder="+5511999999999"
              />
            </div>
          )}
        </>
      )}
    </DrawerBase>
  );
}

// ─── Modal: Modo de operação do agendamento ──────────────────
function ModalAppointmentMode({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const opts = [
    {
      v: 'exploratory',
      label: 'Agendamento Exploratório',
      desc: 'O lead agenda uma sessão de diagnóstico ou consulta sem compromisso de compra. O pagamento (se houver) acontece presencialmente na marcação após a sessão.',
    },
    {
      v: 'commercial',
      label: 'Compromisso Comercial',
      desc: 'O agente apresenta serviços e preços, trata objeções e fecha a escolha de um pacote antes de agendar. O pagamento é sempre presencial na marcação — nenhum link de checkout é enviado.',
    },
  ];
  return (
    <ModalBase title="Modo de operação" sub="Como o agente conduz o lead após a qualificação" onClose={onClose} onSave={() => onSave(local)}>
      {opts.map(o => (
        <OptCard key={o.v} selected={local === o.v} onClick={() => setLocal(o.v)} label={o.label} desc={o.desc} />
      ))}
    </ModalBase>
  );
}

// ─── Modal: Integração de calendário ─────────────────────────
function ModalCalendario({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const opts = [
    { v: 'none',            label: 'Sem integração',    desc: 'O agente não sincroniza com nenhum calendário.' },
    { v: 'google_calendar', label: 'Google Calendar',   desc: 'Consulta disponibilidade e cria eventos automaticamente.' },
    { v: 'calendly',        label: 'Calendly',          desc: 'Compartilha link do Calendly e aguarda confirmação.' },
  ];
  return (
    <ModalBase title="Integração de calendário" sub="Como o agente verifica disponibilidade e agenda reuniões" onClose={onClose} onSave={() => onSave(local)}>
      {opts.map(o => (
        <OptCard key={o.v} selected={local === o.v} onClick={() => setLocal(o.v)} label={o.label} desc={o.desc} />
      ))}
      {local !== 'none' && (
        <div style={{ marginTop: 12, padding: '10px 12px', background: 'var(--o-b0)', borderRadius: 4, border: '1px solid var(--o-b1)', fontSize: 12, color: 'var(--o-sub)' }}>
          ℹ A configuração detalhada da integração está em desenvolvimento. Selecione para reservar a configuração.
        </div>
      )}
    </ModalBase>
  );
}

// ─── Modal: Estilo de oferta de horário ───────────────────────
function ModalSchedulingOfferStyle({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const opts = [
    {
      v: 'offer_alternatives',
      label: 'Sempre oferecer alternativas',
      desc: 'O agente nunca confirma de imediato o horário exato pedido — propõe sempre 2-3 opções próximas, mesmo que o horário esteja livre. Pode funcionar como gatilho comercial de escassez.',
    },
    {
      v: 'confirm_exact',
      label: 'Confirmar horário exato quando disponível',
      desc: 'Se o horário pedido pelo lead estiver livre, o agente confirma diretamente. Só propõe alternativas quando o horário pedido realmente não está disponível.',
    },
  ];
  return (
    <ModalBase title="Estilo de oferta de horário" sub="Como o agente responde quando o lead pede um horário específico" onClose={onClose} onSave={() => onSave(local)}>
      {opts.map(o => (
        <OptCard key={o.v} selected={local === o.v} onClick={() => setLocal(o.v)} label={o.label} desc={o.desc} />
      ))}
    </ModalBase>
  );
}

// ─── Modal: Gestão pós-confirmação (cancelamento/reagendamento) ──
function ModalMeetingManagement({ value, onSave, onClose }: { value: boolean; onSave: (v: boolean) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const opts = [
    {
      v: true,
      label: 'Bot continua disponível',
      desc: 'Depois de confirmar a reunião, o bot volta a responder o lead só para cancelar ou reagendar — qualquer outra mensagem recebe uma resposta mínima, sem reabrir venda.',
    },
    {
      v: false,
      label: 'Desativar bot e aguardar handoff manual',
      desc: 'Depois de confirmar a reunião, o bot fica mudo para esse lead (mesmo comportamento de uma desativação manual). Um cancelamento ou pedido de remarcação só é atendido se o operador reativar o bot.',
    },
  ];
  return (
    <ModalBase title="Gestão pós-confirmação" sub="O que o bot faz se o lead pedir para cancelar ou remarcar depois de confirmar a reunião" onClose={onClose} onSave={() => onSave(local)}>
      {opts.map(o => (
        <OptCard key={String(o.v)} selected={local === o.v} onClick={() => setLocal(o.v)} label={o.label} desc={o.desc} />
      ))}
    </ModalBase>
  );
}

// ─────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────

type DrawerKey = 'briefing' | null;
type ModalKey  = 'calendario' | 'modoOperacao' | 'ofertaHorario' | 'gestaoPosConfirmacao' | null;

const APPOINTMENT_MODE_LABELS: Record<string, string> = {
  exploratory: 'Agendamento Exploratório',
  commercial:  'Compromisso Comercial',
};

export function CamadaApresentacao({ config, onUpdate }: CamadaApresentacaoProps) {
  const [drawer, setDrawer] = useState<DrawerKey>(null);
  const [modal, setModal]   = useState<ModalKey>(null);

  const apptModeLabel = APPOINTMENT_MODE_LABELS[config.appointment_mode] || 'Agendamento Exploratório';
  const briefingLabel = config.briefing_enabled
    ? `${BRIEFING_CHANNEL_LABELS[config.briefing_channel] || config.briefing_channel} · ${config.briefing_lead_time}h antes`
    : 'Desativado';
  const calLabel = CALENDAR_INTEGRATION_LABELS[config.calendar_integration] || 'Sem integração';
  const offerStyleLabel = SCHEDULING_OFFER_STYLE_LABELS[config.scheduling_offer_style] || 'Sempre oferecer alternativas';
  const meetingManagementLabel = config.meeting_management_enabled !== false
    ? 'Bot continua disponível'
    : 'Desativado (handoff manual)';

  return (
    <>
      {/* Seção: Modo de operação */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Modo de operação
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Objetivo do agendamento"
          value={apptModeLabel}
          sub="Como o agente conduz o lead após qualificar"
          onClick={() => setModal('modoOperacao')}
          status="ok"
          help="Exploratório: o lead agenda uma sessão de diagnóstico sem compromisso. Comercial: o agente apresenta preços e trata objeções antes de agendar — maior conversão, maior resistência inicial."
        />
      </div>

      {/* Seção: Dossiê pré-reunião */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Dossiê pré-reunião
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Envio de dossiê"
          value={briefingLabel}
          sub="Resumo do lead para o operador"
          onClick={() => setDrawer('briefing')}
          status={config.briefing_enabled ? 'ok' : 'warn'}
          help="Ativa o envio automático de um resumo do lead ao operador antes da reunião. O operador chega preparado para a conversa com contexto, histórico e qualificação do lead."
        />
        {config.briefing_enabled && config.briefing_channel === 'whatsapp' && (
          <EditCard
            label="Número do operador"
            value={config.operator_whatsapp || 'Não configurado'}
            sub="WhatsApp de destino do dossiê"
            onClick={() => setDrawer('briefing')}
            status={config.operator_whatsapp ? 'ok' : 'miss'}
            help="Número de WhatsApp que receberá o dossiê pré-reunião. Formato internacional com DDI: +5511999999999."
          />
        )}
      </div>

      {/* Seção: Disponibilidade de horários */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Disponibilidade de horários
        </span>
      </div>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 12, color: 'var(--o-sub)', fontWeight: 300, marginBottom: 10 }}>
          Informe os dias e horários disponíveis para atendimento. O bot usará estas informações para propor horários ao lead na fase de Agendamento.
        </div>
        <div className="o-field-hint" style={{ marginBottom: 8, fontSize: 11 }}>
          Exemplo: Seg-Sex: 14h, 16h, 18h · Sáb: 10h, 12h
        </div>
        <textarea
          className="o-input"
          style={{ width: '100%', minHeight: 80, resize: 'vertical', fontFamily: 'inherit', fontSize: 13 }}
          placeholder={'Seg-Sex: 14h, 16h, 18h\nSábado: 10h, 12h'}
          value={config.availability_schedule || ''}
          onChange={e => onUpdate({ availability_schedule: e.target.value })}
        />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Estilo de oferta de horário"
          value={offerStyleLabel}
          sub="Como o agente responde a um horário específico pedido"
          onClick={() => setModal('ofertaHorario')}
          status="ok"
          help="Sempre oferecer alternativas: o agente propõe 2-3 opções mesmo quando o horário pedido está livre (tática de escassez). Confirmar horário exato: o agente confirma direto quando o horário pedido está disponível."
        />
      </div>

      {/* Seção: Gestão pós-confirmação */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Gestão pós-confirmação
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Cancelamento e reagendamento"
          value={meetingManagementLabel}
          sub="O que o bot faz se o lead pedir mudança após confirmar"
          onClick={() => setModal('gestaoPosConfirmacao')}
          status={config.meeting_management_enabled !== false ? 'ok' : 'warn'}
          help="Bot continua disponível: gerencia cancelamento/reagendamento automaticamente, sem reabrir venda. Desativado: o bot fica mudo após confirmar a reunião e só volta a responder se o operador reativar manualmente."
        />
      </div>

      {/* Seção: Calendário */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Integração de calendário
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Calendário"
          value={calLabel}
          sub="Verificação de disponibilidade e agendamento"
          onClick={() => setModal('calendario')}
          status={config.calendar_integration && config.calendar_integration !== 'none' ? 'ok' : 'warn'}
          help="Integração de calendário: sem integração (agendamento manual), Google Calendar (cria eventos e verifica disponibilidade automaticamente) ou Calendly (compartilha link)."
        />
      </div>

      {/* Drawers */}
      {drawer === 'briefing' && (
        <DrawerBriefing config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />
      )}

      {/* Modais */}
      {modal === 'modoOperacao' && (
        <ModalAppointmentMode
          value={config.appointment_mode || 'exploratory'}
          onClose={() => setModal(null)}
          onSave={v => { onUpdate({ appointment_mode: v as 'commercial' | 'exploratory' }); setModal(null); }}
        />
      )}
      {modal === 'calendario' && (
        <ModalCalendario
          value={config.calendar_integration}
          onClose={() => setModal(null)}
          onSave={v => { onUpdate({ calendar_integration: v }); setModal(null); }}
        />
      )}
      {modal === 'ofertaHorario' && (
        <ModalSchedulingOfferStyle
          value={config.scheduling_offer_style || 'offer_alternatives'}
          onClose={() => setModal(null)}
          onSave={v => { onUpdate({ scheduling_offer_style: v as 'offer_alternatives' | 'confirm_exact' }); setModal(null); }}
        />
      )}
      {modal === 'gestaoPosConfirmacao' && (
        <ModalMeetingManagement
          value={config.meeting_management_enabled !== false}
          onClose={() => setModal(null)}
          onSave={v => { onUpdate({ meeting_management_enabled: v }); setModal(null); }}
        />
      )}
    </>
  );
}

// ─── Componentes internos ─────────────────────────────────────

function EditCard({ label, value, sub, onClick, status, help }: {
  label: string; value: string; sub: string; onClick: () => void;
  status?: 'ok' | 'warn' | 'miss'; help?: string;
}) {
  const borderColor = status === 'miss' ? 'var(--o-hot-b)' : 'var(--o-b0)';
  const valueColor  = status === 'miss' ? 'var(--o-hot)' : status === 'warn' ? 'var(--o-warn)' : 'var(--o-text)';
  return (
    <div className="o-edit-card" style={{ borderColor }} onClick={onClick}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6, display: 'flex', alignItems: 'center' }}>{label}{help && <FieldHelp text={help} />}</div>
      <div style={{ fontSize: 13, color: valueColor, marginBottom: 4 }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--o-sub)', fontWeight: 300, marginBottom: status ? 8 : 0 }}>{sub}</div>
      {status && (
        <span className={`o-badge ${status === 'ok' ? 'o-badge-ok' : status === 'warn' ? 'o-badge-warn' : 'o-badge-miss'}`}>
          {status === 'ok' ? 'Configurado' : status === 'warn' ? 'Parcial' : 'Pendente'}
        </span>
      )}
      <span className="o-edit-arrow">›</span>
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
        <span className="font-mono-orion" style={{ fontSize: 11, color: 'var(--o-text)', minWidth: 56, textAlign: 'right' }}>
          {format(value)}
        </span>
      </div>
    </div>
  );
}
