import { useState } from 'react';
import { FieldHelp } from './FieldHelp';
import { SuggestInput } from './SuggestField';
import type { AgentConfig } from '@/types/agente';
import { PAYMENT_GATEWAY_LABELS, OFFER_MEDIA_TYPE_LABELS } from '@/types/agente';
import { api } from '@/services/api';
import { buildVariableList } from '@/types/variables';
import { VariableTextarea } from './VariableTextarea';

interface CamadaOfertaProps {
  config: AgentConfig;
  onUpdate: (partial: Partial<AgentConfig>) => void;
}

// ─── Drawer: Mídia do pitch ───────────────────────────────────
function DrawerMidia({ mediaUrl, mediaType, onSave, onClose }: {
  mediaUrl: string; mediaType: string;
  onSave: (url: string, type: string) => void; onClose: () => void;
}) {
  const [url, setUrl]   = useState(mediaUrl);
  const [type, setType] = useState(mediaType);
  return (
    <DrawerBase title="Mídia do pitch" sub="Imagem, vídeo ou áudio enviado junto com a oferta" onClose={onClose} onSave={() => onSave(url, type)}>
      <div className="o-field">
        <label className="o-field-label">Tipo de mídia</label>
        <select className="o-select" value={type} onChange={e => setType(e.target.value)}>
          <option value="image">Imagem</option>
          <option value="video">Vídeo</option>
          <option value="audio">Áudio</option>
        </select>
      </div>
      <div className="o-field">
        <label className="o-field-label">URL da mídia</label>
        <div className="o-field-hint">Link público direto para o arquivo. O WhatsApp deve conseguir acessar esta URL.</div>
        <SuggestInput className="o-input" type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://…" />
      </div>
    </DrawerBase>
  );
}

// ─── Drawer: Detalhes da oferta ───────────────────────────────
function DrawerDetalhes({ config, onSave, onClose }: {
  config: AgentConfig; onSave: (v: Partial<AgentConfig>) => void; onClose: () => void;
}) {
  const [price, setPrice]         = useState(config.offer_anchor_price);
  const [guarantee, setGuarantee] = useState(config.offer_guarantee_text);
  const [upsell, setUpsell]       = useState(config.offer_upsell_message);
  const variables = buildVariableList(config.custom_variables || {});
  return (
    <DrawerBase title="Detalhes da oferta" sub="Preço, garantia e mensagem de upsell pós-compra" onClose={onClose}
      onSave={() => onSave({ offer_anchor_price: price, offer_guarantee_text: guarantee, offer_upsell_message: upsell })}>
      <div className="o-field">
        <label className="o-field-label">Preço âncora</label>
        <div className="o-field-hint">Ex: "de R$997 por R$497" ou "R$1.500/mês"</div>
        <SuggestInput className="o-input" value={price} onChange={e => setPrice(e.target.value)} maxLength={80} placeholder="R$ 997,00" />
        <div className="o-char-count">{price.length}/80</div>
      </div>
      <div className="o-field">
        <label className="o-field-label">Texto da garantia</label>
        <VariableTextarea
          value={guarantee}
          onChange={setGuarantee}
          variables={variables}
          maxLength={300}
          placeholder="Ex: Garantia incondicional de 7 dias. Se não gostar, devolvemos 100%."
        />
      </div>
      <div className="o-field">
        <label className="o-field-label">Mensagem de upsell pós-compra</label>
        <div className="o-field-hint">Enviada após o cliente confirmar a compra.</div>
        <VariableTextarea
          value={upsell}
          onChange={setUpsell}
          variables={variables}
          maxLength={400}
          placeholder="Ex: Parabéns, {{lead.nome}}! Enquanto aguarda o acesso, que tal nosso complemento exclusivo?"
        />
      </div>
    </DrawerBase>
  );
}

// ─── Modal: Gateway de pagamento ─────────────────────────────
function ModalGateway({ value, onSave, onClose }: { value: string; onSave: (v: string) => void; onClose: () => void }) {
  const [local, setLocal] = useState(value);
  const opts = [
    { v: 'hotmart',  label: 'Hotmart',       desc: 'Plataforma de infoprodutos e cursos digitais.' },
    { v: 'kiwify',   label: 'Kiwify',        desc: 'Checkout otimizado para produtos digitais.' },
    { v: 'stripe',   label: 'Stripe',        desc: 'Gateway internacional, cartão e PIX.' },
    { v: 'generico', label: 'Link genérico', desc: 'Qualquer link de pagamento externo.' },
  ];
  return (
    <ModalBase title="Gateway de pagamento" sub="Plataforma onde o lead finaliza a compra" onClose={onClose} onSave={() => onSave(local)}>
      {opts.map(o => (
        <OptCard key={o.v} selected={local === o.v} onClick={() => setLocal(o.v)} label={o.label} desc={o.desc} />
      ))}
    </ModalBase>
  );
}

// ─────────────────────────────────────────────────────────────
// Componente principal
// ─────────────────────────────────────────────────────────────

type DrawerKey = 'midia' | 'detalhes' | null;
type ModalKey  = 'gateway' | null;

export function CamadaOferta({ config, onUpdate }: CamadaOfertaProps) {
  const [drawer, setDrawer]             = useState<DrawerKey>(null);
  const [modal, setModal]               = useState<ModalKey>(null);
  const [secretRevealed, setSecretRevealed] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const mediaLabel = config.offer_media_url
    ? `${OFFER_MEDIA_TYPE_LABELS[config.offer_media_type] || config.offer_media_type} configurado`
    : 'Sem mídia';

  const gatewayLabel = PAYMENT_GATEWAY_LABELS[config.payment_gateway] || 'Não configurado';

  async function handleRegenerateSecret() {
    if (!window.confirm('Regenerar o token do webhook? O token anterior será invalidado.')) return;
    setRegenerating(true);
    try {
      const result = await api.core.regenerateWebhookSecret();
      onUpdate({ payment_webhook_secret: (result as any)?.payment_webhook_secret ?? '' });
    } catch {
      alert('Erro ao regenerar o token. Tente novamente.');
    } finally {
      setRegenerating(false);
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).catch(() => {});
  }

  return (
    <>
      {/* Seção: Mídia do pitch */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Mídia do pitch
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Mídia do pitch"
          value={mediaLabel}
          sub="Imagem, vídeo ou áudio enviado com a oferta"
          onClick={() => setDrawer('midia')}
          status={config.offer_media_url ? 'ok' : 'warn'}
          help="Mídia enviada ao lead junto com a oferta (imagem de produto, vídeo de vendas, áudio de apresentação). Use um link público direto — o WhatsApp precisa acessar a URL para baixar."
        />
      </div>

      {/* Seção: Detalhes da oferta */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Detalhes da oferta
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Preço âncora"
          value={config.offer_anchor_price || 'Não configurado'}
          sub="Preço apresentado ao lead"
          onClick={() => setDrawer('detalhes')}
          status={config.offer_anchor_price ? 'ok' : 'warn'}
          help="Preço âncora para criar percepção de valor. Ex: 'de R$997 por R$497'. Mostrar o preço original antes do desconto aumenta a conversão da oferta."
        />
        <EditCard
          label="Garantia"
          value={config.offer_guarantee_text ? config.offer_guarantee_text.slice(0, 50) + '…' : 'Não configurado'}
          sub="Texto da garantia ao lead"
          onClick={() => setDrawer('detalhes')}
          status={config.offer_guarantee_text ? 'ok' : 'warn'}
          italic
          help="Texto da garantia apresentada ao lead. Ex: '7 dias de reembolso total'. Reduz a objeção de risco — o lead se sente mais seguro para decidir na hora."
        />
        <EditCard
          label="Upsell pós-compra"
          value={config.offer_upsell_message ? config.offer_upsell_message.slice(0, 50) + '…' : 'Não configurado'}
          sub="Mensagem enviada após confirmação"
          onClick={() => setDrawer('detalhes')}
          status={config.offer_upsell_message ? 'ok' : 'warn'}
          italic
          help="Mensagem enviada automaticamente após o cliente confirmar a compra. Use para oferecer um upgrade, produto complementar ou bônus exclusivo enquanto o cliente ainda está aquecido."
        />
      </div>

      {/* Seção: Gateway de pagamento */}
      <div className="o-section-hdr">
        <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
          Gateway de pagamento
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 24 }}>
        <EditCard
          label="Plataforma"
          value={gatewayLabel}
          sub="Onde o lead finaliza a compra"
          onClick={() => setModal('gateway')}
          status={config.payment_gateway ? 'ok' : 'warn'}
          help="Plataforma de pagamento integrada (Hotmart, Kiwify, Stripe ou link genérico). O agente envia o link de checkout automaticamente após fechar a venda. Habilita o webhook de compra confirmada."
        />
      </div>

      {/* Webhook de pagamento */}
      {config.payment_gateway && (
        <>
          <div className="o-section-hdr">
            <span className="font-mono-orion" style={{ fontSize: 9, letterSpacing: '2.5px', textTransform: 'uppercase', color: 'var(--o-sub)' }}>
              Webhook de pagamento
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
            {/* URL do webhook */}
            <div>
              <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6, display: 'flex', alignItems: 'center' }}>
                URL do webhook <FieldHelp text="URL gerada automaticamente. Configure este endereço no painel da plataforma de pagamento para que ela notifique o CRM quando uma compra for confirmada." />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  className="o-input"
                  readOnly
                  value={config.payment_webhook_url || '(gerado ao salvar o gateway)'}
                  style={{ flex: 1, background: 'var(--o-b0)', cursor: 'default', fontSize: 12 }}
                />
                {config.payment_webhook_url && (
                  <button className="o-btn" style={{ whiteSpace: 'nowrap' }} onClick={() => copyToClipboard(config.payment_webhook_url)}>
                    Copiar
                  </button>
                )}
              </div>
              <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 4, fontWeight: 300 }}>
                Configure este URL no painel do {gatewayLabel} para receber notificações de compra.
              </div>
            </div>

            {/* Token do webhook */}
            <div>
              <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6, display: 'flex', alignItems: 'center' }}>
                Token de validação (secret) <FieldHelp text="Token de segurança para validar que as notificações vêm realmente da plataforma de pagamento. Nunca compartilhe publicamente — configure-o no painel da plataforma." />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  className="o-input"
                  readOnly
                  type={secretRevealed ? 'text' : 'password'}
                  value={config.payment_webhook_secret || '(não gerado)'}
                  style={{ flex: 1, background: 'var(--o-b0)', cursor: 'default', fontSize: 12 }}
                />
                <button className="o-btn" style={{ whiteSpace: 'nowrap' }} onClick={() => setSecretRevealed(v => !v)}>
                  {secretRevealed ? 'Ocultar' : 'Revelar'}
                </button>
                <button className="o-btn" style={{ whiteSpace: 'nowrap', color: 'var(--o-warn)' }} onClick={handleRegenerateSecret} disabled={regenerating}>
                  {regenerating ? '…' : 'Regenerar'}
                </button>
              </div>
              <div style={{ fontSize: 11, color: 'var(--o-sub)', marginTop: 4, fontWeight: 300 }}>
                Use este token para validar que as notificações vêm realmente do {gatewayLabel}.
              </div>
            </div>
          </div>
        </>
      )}

      {/* Drawers */}
      {drawer === 'midia' && (
        <DrawerMidia
          mediaUrl={config.offer_media_url}
          mediaType={config.offer_media_type}
          onClose={() => setDrawer(null)}
          onSave={(url, type) => { onUpdate({ offer_media_url: url, offer_media_type: type }); setDrawer(null); }}
        />
      )}
      {drawer === 'detalhes' && (
        <DrawerDetalhes config={config} onClose={() => setDrawer(null)} onSave={v => { onUpdate(v); setDrawer(null); }} />
      )}

      {/* Modais */}
      {modal === 'gateway' && (
        <ModalGateway
          value={config.payment_gateway}
          onClose={() => setModal(null)}
          onSave={v => { onUpdate({ payment_gateway: v }); setModal(null); }}
        />
      )}
    </>
  );
}

// ─── Componentes internos ─────────────────────────────────────

function EditCard({ label, value, sub, onClick, status, italic, help }: {
  label: string; value: string; sub: string; onClick: () => void;
  status?: 'ok' | 'warn' | 'miss'; italic?: boolean; help?: string;
}) {
  const borderColor = status === 'miss' ? 'var(--o-hot-b)' : 'var(--o-b0)';
  const valueColor  = status === 'miss' ? 'var(--o-hot)' : status === 'warn' ? 'var(--o-warn)' : 'var(--o-text)';
  return (
    <div className="o-edit-card" style={{ borderColor }} onClick={onClick}>
      <div className="font-mono-orion" style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', marginBottom: 6, display: 'flex', alignItems: 'center' }}>{label}{help && <FieldHelp text={help} />}</div>
      <div style={{ fontSize: 13, color: valueColor, marginBottom: 4, fontStyle: italic ? 'italic' : 'normal' }}>{value}</div>
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
