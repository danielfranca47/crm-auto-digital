import { useState } from 'react';
import { api } from '@/services/api';
import { KNOWLEDGE_IMPORTANCE_LABELS, type KnowledgeCategory, type AgentConfig } from '@/types/agente';

// ─── Utilitários ──────────────────────────────────────────────

function personalizeCategory(
  cat: KnowledgeCategory,
  niche: string,
  audience: string,
  offer: string,
): KnowledgeCategory {
  const n = niche    || '[nicho do negócio]';
  const a = audience || '[público-alvo]';
  const o = offer    || '[descrição da oferta]';
  return {
    ...cat,
    hint: cat.hint
      .replace(/\[NICHO\]/g, n)
      .replace(/\[PÚBLICO\]/g, a)
      .replace(/\[OFERTA\]/g, o),
    placeholder: cat.placeholder
      .replace(/\[NICHO\]/g, n)
      .replace(/\[PÚBLICO\]/g, a)
      .replace(/\[OFERTA\]/g, o),
  };
}

function getReadinessLevel(
  guidedCategories: KnowledgeCategory[],
  filledKeys: Set<string>,
): 'none' | 'basic' | 'optimized' {
  const critical    = guidedCategories.filter(c => c.importance === 'critical');
  const recommended = guidedCategories.filter(c => c.importance === 'recommended');
  const criticalFilled    = critical.filter(c => filledKeys.has(c.key)).length;
  const recommendedFilled = recommended.filter(c => filledKeys.has(c.key)).length;
  if (criticalFilled < 2)              return 'none';
  if (criticalFilled < critical.length) return 'basic';
  if (recommendedFilled >= 2)           return 'optimized';
  return 'basic';
}

const READINESS_CONFIG = {
  none: {
    color: 'var(--o-hot)', dot: 'var(--o-hot)', borderColor: 'var(--o-hot-b)',
    label: 'Não funcional',
    message: 'O agente não tem informações suficientes para responder bem.',
  },
  basic: {
    color: '#d97706', dot: '#d97706', borderColor: '#92400e44',
    label: 'Funcional básico',
    message: 'O agente consegue operar, mas sem diferenciação.',
  },
  optimized: {
    color: 'var(--o-active)', dot: 'var(--o-active)', borderColor: 'var(--o-active-b)',
    label: 'Otimizado',
    message: 'O agente está pronto para operar com alta performance.',
  },
} as const;

// ─── Passo 0: Confirmação de contexto ────────────────────────

function StepContext({
  niche, setNiche,
  audience, setAudience,
  offer, setOffer,
  onContinue,
  onExit,
}: {
  niche: string;    setNiche:    (v: string) => void;
  audience: string; setAudience: (v: string) => void;
  offer: string;    setOffer:    (v: string) => void;
  onContinue: () => void;
  onExit: () => void;
}) {
  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div
          className="font-display"
          style={{ fontSize: 18, fontWeight: 400, color: 'var(--o-text)', marginBottom: 8 }}
        >
          Antes de preencher, confirme 2 coisas rápidas
        </div>
        <div style={{ fontSize: 13, color: 'var(--o-sub)', lineHeight: 1.6 }}>
          Já temos esses dados das etapas anteriores — confira se estão corretos.
          Os exemplos das próximas etapas serão personalizados com base neles.
        </div>
      </div>

      <div className="o-field">
        <label className="o-field-label">Nicho do negócio</label>
        <input
          className="o-input"
          value={niche}
          onChange={e => setNiche(e.target.value)}
          placeholder="Ex: clínica estética, consultoria jurídica, infoprodutos…"
        />
      </div>
      <div className="o-field">
        <label className="o-field-label">Público-alvo</label>
        <input
          className="o-input"
          value={audience}
          onChange={e => setAudience(e.target.value)}
          placeholder="Ex: mulheres 30–50 anos, PMEs, médicos…"
        />
      </div>
      <div className="o-field">
        <label className="o-field-label">Oferta principal</label>
        <input
          className="o-input"
          value={offer}
          onChange={e => setOffer(e.target.value)}
          placeholder="Ex: Pacote 4 sessões de massagem, Consultoria mensal, Curso online…"
        />
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
        <button
          className="o-btn o-btn-primary"
          onClick={onContinue}
        >
          Continuar →
        </button>
        <button
          className="o-btn"
          onClick={onExit}
          style={{ color: 'var(--o-sub)' }}
        >
          Preencher depois
        </button>
      </div>
    </div>
  );
}

// ─── Passo N: Preencher categoria ─────────────────────────────

function StepCategory({
  category,
  isCritical,
  onSaved,
  onSkip,
}: {
  category: KnowledgeCategory;
  isCritical: boolean;
  onSaved: (key: string) => void;
  onSkip?: () => void;
}) {
  const [content, setContent] = useState('');
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function handleSave() {
    if (!content.trim() || content.trim().length < 20) {
      setError('O conteúdo deve ter pelo menos 20 caracteres.');
      return;
    }
    setSaving(true);
    try {
      await api.crm.createKnowledgeManual({
        title:        category.label,
        content_text: content.trim(),
        category:     category.key,
      });
      onSaved(category.key);
    } catch {
      setError('Erro ao salvar. Tente novamente.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      {/* Cabeçalho da categoria */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <span style={{ fontSize: 16, fontWeight: 500, color: 'var(--o-text)' }}>
          {category.label}
        </span>
        <span
          className="font-mono-orion"
          style={{
            fontSize: 7, letterSpacing: 1.5, textTransform: 'uppercase', padding: '1px 5px',
            borderRadius: 2,
            border: `1px solid ${isCritical ? 'var(--o-hot-b)' : 'var(--o-b1)'}`,
            color: isCritical ? 'var(--o-hot)' : 'var(--o-dim)',
          }}
        >
          {KNOWLEDGE_IMPORTANCE_LABELS[category.importance]}
        </span>
      </div>

      <div style={{ fontSize: 12.5, color: 'var(--o-sub)', marginBottom: 16, lineHeight: 1.6 }}>
        {category.description}
      </div>

      {/* Hint */}
      <div style={{
        background: 'var(--o-b0)', border: '1px solid var(--o-b1)', borderRadius: 4,
        padding: '10px 14px', marginBottom: 16, fontSize: 12.5, color: 'var(--o-sub)', lineHeight: 1.6,
      }}>
        <span
          className="font-mono-orion"
          style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)', display: 'block', marginBottom: 4 }}
        >
          O que preencher
        </span>
        {category.hint}
      </div>

      <div className="o-field">
        <textarea
          className="o-textarea"
          style={{ minHeight: 200 }}
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder={category.placeholder}
          // eslint-disable-next-line jsx-a11y/no-autofocus
          autoFocus
        />
      </div>

      {error && (
        <div style={{ fontSize: 12, color: 'var(--o-hot)', marginBottom: 10 }}>{error}</div>
      )}

      <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
        <button
          className="o-btn o-btn-primary"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Salvando…' : 'Salvar e continuar →'}
        </button>
        {onSkip && (
          <button
            className="o-btn"
            onClick={onSkip}
            style={{ color: 'var(--o-sub)' }}
          >
            {isCritical ? 'Pular esta etapa' : 'Pular por agora'}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Passo final: Conclusão ───────────────────────────────────

function StepDone({
  guidedCategories,
  filledKeys,
  onFinish,
}: {
  guidedCategories: KnowledgeCategory[];
  filledKeys: Set<string>;
  onFinish: () => void;
}) {
  const level     = getReadinessLevel(guidedCategories, filledKeys);
  const readiness = READINESS_CONFIG[level];

  const criticalTotal    = guidedCategories.filter(c => c.importance === 'critical').length;
  const criticalFilled   = guidedCategories.filter(c => c.importance === 'critical'    && filledKeys.has(c.key)).length;
  const recommendedTotal  = guidedCategories.filter(c => c.importance === 'recommended').length;
  const recommendedFilled = guidedCategories.filter(c => c.importance === 'recommended' && filledKeys.has(c.key)).length;

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ marginBottom: 24 }}>
        <div
          className="font-display"
          style={{ fontSize: 20, fontWeight: 400, color: 'var(--o-text)', marginBottom: 8 }}
        >
          Configuração concluída
        </div>
        <div style={{ fontSize: 13, color: 'var(--o-sub)' }}>
          Veja o status de prontidão do seu agente
        </div>
      </div>

      {/* Score de prontidão */}
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 12,
        padding: '14px 22px', borderRadius: 6,
        border: `1px solid ${readiness.borderColor}`,
        background: 'var(--o-b0)',
        marginBottom: 24,
        textAlign: 'left',
      }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: readiness.dot, flexShrink: 0 }} />
        <div>
          <div
            className="font-mono-orion"
            style={{ fontSize: 8, letterSpacing: 1.5, textTransform: 'uppercase', color: readiness.color, marginBottom: 4 }}
          >
            {readiness.label}
          </div>
          <div style={{ fontSize: 13, color: 'var(--o-text)', fontWeight: 400 }}>
            {readiness.message}
          </div>
        </div>
      </div>

      {/* Contadores */}
      <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginBottom: 28 }}>
        <div style={{
          textAlign: 'center', padding: '12px 24px',
          background: 'var(--o-b0)', borderRadius: 4, border: '1px solid var(--o-b1)',
        }}>
          <div style={{ fontSize: 22, fontWeight: 400, color: 'var(--o-text)' }}>
            {criticalFilled}/{criticalTotal}
          </div>
          <div
            className="font-mono-orion"
            style={{ fontSize: 8, letterSpacing: 1.5, textTransform: 'uppercase', color: 'var(--o-dim)', marginTop: 4 }}
          >
            críticas
          </div>
        </div>
        <div style={{
          textAlign: 'center', padding: '12px 24px',
          background: 'var(--o-b0)', borderRadius: 4, border: '1px solid var(--o-b1)',
        }}>
          <div style={{ fontSize: 22, fontWeight: 400, color: 'var(--o-text)' }}>
            {recommendedFilled}/{recommendedTotal}
          </div>
          <div
            className="font-mono-orion"
            style={{ fontSize: 8, letterSpacing: 1.5, textTransform: 'uppercase', color: 'var(--o-dim)', marginTop: 4 }}
          >
            recomendadas
          </div>
        </div>
      </div>

      <button className="o-btn o-btn-primary" onClick={onFinish}>
        Ver base de conhecimento →
      </button>
    </div>
  );
}

// ─── Wizard principal ─────────────────────────────────────────

export interface WizardProps {
  rawCategories: KnowledgeCategory[];
  agentConfig:   Partial<AgentConfig>;
  onComplete:    () => void;
  onExit:        () => void;
}

export function CamadaConhecimentoWizard({ rawCategories, agentConfig, onComplete, onExit }: WizardProps) {
  const [niche,    setNiche]    = useState(agentConfig.niche             ?? '');
  const [audience, setAudience] = useState(agentConfig.target_audience  ?? '');
  const [offer,    setOffer]    = useState(agentConfig.offer_description ?? '');

  const [step,       setStep]       = useState(0);
  const [filledKeys, setFilledKeys] = useState<Set<string>>(new Set());

  const criticalCats    = rawCategories.filter(c => c.importance === 'critical');
  const recommendedCats = rawCategories.filter(c => c.importance === 'recommended');
  const contentSteps    = [...criticalCats, ...recommendedCats];
  // Estrutura: passo 0 = contexto | passos 1..N = categorias | passo N+1 = conclusão
  const totalSteps = 1 + contentSteps.length + 1;

  const isContextStep = step === 0;
  const isDoneStep    = step === totalSteps - 1;
  const isContentStep = !isContextStep && !isDoneStep;

  const currentCatIdx = step - 1;
  const currentCatRaw = isContentStep ? contentSteps[currentCatIdx] : null;
  const currentCategory = currentCatRaw
    ? personalizeCategory(currentCatRaw, niche, audience, offer)
    : null;
  const isCriticalStep = currentCatRaw?.importance === 'critical';

  function handleCategorySaved(key: string) {
    setFilledKeys(prev => new Set([...prev, key]));
    setStep(s => s + 1);
  }

  // Cálculo de progresso (contexto conta como 0%, conclusão como 100%)
  const progressPercent = totalSteps > 2
    ? Math.round((step / (totalSteps - 1)) * 100)
    : 0;

  const stepLabel = isContextStep
    ? 'Contexto do negócio'
    : isDoneStep
    ? 'Concluído'
    : isCriticalStep
    ? `Seção crítica ${currentCatIdx + 1} de ${criticalCats.length}`
    : `Seção recomendada ${currentCatIdx - criticalCats.length + 1} de ${recommendedCats.length}`;

  return (
    <div style={{ maxWidth: 620 }}>
      {/* Barra de progresso */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span
            className="font-mono-orion"
            style={{ fontSize: 8, letterSpacing: 2, textTransform: 'uppercase', color: 'var(--o-dim)' }}
          >
            {stepLabel}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {!isDoneStep && (
              <button
                onClick={onExit}
                className="font-mono-orion"
                style={{
                  fontSize: 8, letterSpacing: 1.5, textTransform: 'uppercase',
                  color: 'var(--o-dim)', background: 'none', border: 'none',
                  cursor: 'pointer', padding: 0, textDecoration: 'underline',
                }}
              >
                Preencher depois →
              </button>
            )}
            <span className="font-mono-orion" style={{ fontSize: 8, color: 'var(--o-dim)' }}>
              {step + 1} / {totalSteps}
            </span>
          </div>
        </div>
        <div style={{ height: 2, background: 'var(--o-b1)', borderRadius: 2 }}>
          <div style={{
            height: '100%', background: 'var(--o-active)', borderRadius: 2,
            width: `${progressPercent}%`, transition: 'width 0.3s ease',
          }} />
        </div>
      </div>

      {isContextStep && (
        <StepContext
          niche={niche}       setNiche={setNiche}
          audience={audience} setAudience={setAudience}
          offer={offer}       setOffer={setOffer}
          onContinue={() => setStep(1)}
          onExit={onExit}
        />
      )}

      {currentCategory && (
        <StepCategory
          key={currentCategory.key}
          category={currentCategory}
          isCritical={!!isCriticalStep}
          onSaved={handleCategorySaved}
          onSkip={() => setStep(s => s + 1)}
        />
      )}

      {isDoneStep && (
        <StepDone
          guidedCategories={rawCategories}
          filledKeys={filledKeys}
          onFinish={onComplete}
        />
      )}
    </div>
  );
}
