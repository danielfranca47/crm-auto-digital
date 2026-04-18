import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { WizardProgress } from "./WizardProgress";
import { api } from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { Plus, Trash2, ArrowRight, ArrowLeft, Zap } from "lucide-react";

interface PriceItem {
  name: string;
  price: string;
  description: string;
}

interface WizardState {
  brand_name: string;
  is_service: boolean | null;
  niche: string;
  avg_ticket: string;
  price_items: PriceItem[];
  offer_description: string;
  target_audience: string;
}

const STEPS = [
  "Empresa",
  "Tipo",
  "Ticket",
  "Preços",
  "Oferta",
  "Público",
  "Pronto",
];

const INITIAL: WizardState = {
  brand_name: "",
  is_service: null,
  niche: "",
  avg_ticket: "",
  price_items: [{ name: "", price: "", description: "" }],
  offer_description: "",
  target_audience: "",
};

interface OnboardingWizardProps {
  onComplete?: () => void;
}

export function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const [step, setStep] = useState(0);
  const [state, setState] = useState<WizardState>(INITIAL);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();
  const navigate = useNavigate();

  const update = (patch: Partial<WizardState>) =>
    setState((s) => ({ ...s, ...patch }));

  const canNext = (): boolean => {
    if (step === 0) return state.brand_name.trim().length > 0;
    if (step === 1) return state.is_service !== null && state.niche.trim().length > 0;
    if (step === 2) return state.avg_ticket.trim().length > 0;
    if (step === 3) return state.price_items.some((i) => i.name.trim());
    if (step === 4) return state.offer_description.trim().length > 0;
    if (step === 5) return state.target_audience.trim().length > 0;
    return true;
  };

  const addPriceItem = () =>
    update({ price_items: [...state.price_items, { name: "", price: "", description: "" }] });

  const removePriceItem = (idx: number) =>
    update({ price_items: state.price_items.filter((_, i) => i !== idx) });

  const updatePriceItem = (idx: number, patch: Partial<PriceItem>) =>
    update({
      price_items: state.price_items.map((item, i) =>
        i === idx ? { ...item, ...patch } : item
      ),
    });

  const handleFinish = async (goToSpyAgent: boolean) => {
    setSaving(true);
    try {
      const offerItems = state.price_items
        .filter((i) => i.name.trim())
        .map((i) => ({ name: i.name, price: i.price, description: i.description }));

      await api.core.patchAiProfileMe({
        brand_name: state.brand_name,
        niche: state.niche,
        offer_description: state.offer_description,
        target_audience: state.target_audience,
        offer_pack: {
          is_service: state.is_service,
          is_product: !state.is_service,
          avg_ticket: state.avg_ticket,
          items: offerItems,
        } as any,
      });

      toast({ title: "Informações salvas com sucesso." });
      if (onComplete) onComplete();

      if (goToSpyAgent) {
        navigate("/spy-agent");
      } else {
        navigate("/ai-profile");
      }
    } catch {
      toast({ title: "Erro ao salvar", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="w-full max-w-xl mx-auto">
      <WizardProgress steps={STEPS} currentStep={step} />

      {/* Step 0 — Nome da empresa */}
      {step === 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Como se chama sua empresa?</h2>
          <p className="text-sm text-muted-foreground">
            Este nome será usado pelo bot ao se apresentar.
          </p>
          <div className="space-y-1">
            <Label>Nome da empresa</Label>
            <Input
              placeholder="Ex: Clínica Bem Viver"
              value={state.brand_name}
              onChange={(e) => update({ brand_name: e.target.value })}
              autoFocus
            />
          </div>
        </div>
      )}

      {/* Step 1 — Tipo + nicho */}
      {step === 1 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">O que você vende?</h2>
          <div className="grid grid-cols-2 gap-3">
            {(["Serviço", "Produto"] as const).map((label) => {
              const isSvc = label === "Serviço";
              const selected = state.is_service === isSvc;
              return (
                <Card
                  key={label}
                  onClick={() => update({ is_service: isSvc })}
                  className={`cursor-pointer transition-all border-2 ${
                    selected ? "border-primary bg-primary/5" : "border-border"
                  }`}
                >
                  <CardContent className="p-4 text-center">
                    <p className="font-semibold">{label}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {isSvc ? "Consultoria, clínica, agência..." : "Físico, digital, assinatura..."}
                    </p>
                    {selected && <Badge className="mt-2 text-xs">Selecionado</Badge>}
                  </CardContent>
                </Card>
              );
            })}
          </div>
          <div className="space-y-1">
            <Label>Nicho / setor</Label>
            <Input
              placeholder="Ex: Clínica odontológica, SaaS B2B, Moda feminina..."
              value={state.niche}
              onChange={(e) => update({ niche: e.target.value })}
            />
          </div>
        </div>
      )}

      {/* Step 2 — Ticket médio */}
      {step === 2 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Qual é o ticket médio?</h2>
          <p className="text-sm text-muted-foreground">
            Valor aproximado por venda ou contrato. Isso ajuda o agente a calibrar a abordagem.
          </p>
          <div className="space-y-1">
            <Label>Ticket médio</Label>
            <Input
              placeholder="Ex: R$ 1.500, R$ 300/mês, $200 USD..."
              value={state.avg_ticket}
              onChange={(e) => update({ avg_ticket: e.target.value })}
              autoFocus
            />
          </div>
        </div>
      )}

      {/* Step 3 — Tabela de preços */}
      {step === 3 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Seus planos ou produtos</h2>
          <p className="text-sm text-muted-foreground">
            Adicione os itens que você oferece. O bot usará essas informações para apresentar a oferta.
          </p>
          <div className="space-y-3">
            {state.price_items.map((item, idx) => (
              <Card key={idx} className="p-3">
                <div className="grid grid-cols-2 gap-2 mb-2">
                  <div className="space-y-1">
                    <Label className="text-xs">Nome</Label>
                    <Input
                      placeholder="Ex: Plano Básico"
                      value={item.name}
                      onChange={(e) => updatePriceItem(idx, { name: e.target.value })}
                      className="h-8 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Preço</Label>
                    <div className="flex gap-1">
                      <Input
                        placeholder="R$ 299/mês"
                        value={item.price}
                        onChange={(e) => updatePriceItem(idx, { price: e.target.value })}
                        className="h-8 text-sm"
                      />
                      {state.price_items.length > 1 && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 shrink-0"
                          onClick={() => removePriceItem(idx)}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Descrição (opcional)</Label>
                  <Input
                    placeholder="O que está incluso..."
                    value={item.description}
                    onChange={(e) => updatePriceItem(idx, { description: e.target.value })}
                    className="h-8 text-sm"
                  />
                </div>
              </Card>
            ))}
            <Button variant="outline" size="sm" onClick={addPriceItem} className="w-full">
              <Plus className="h-4 w-4 mr-1" /> Adicionar item
            </Button>
          </div>
        </div>
      )}

      {/* Step 4 — Descrição da oferta */}
      {step === 4 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Descreva sua oferta</h2>
          <p className="text-sm text-muted-foreground">
            O que você oferece e qual o principal benefício para o cliente?
          </p>
          <div className="space-y-1">
            <Label>Descrição da oferta</Label>
            <Textarea
              placeholder="Ex: Oferecemos tratamentos odontológicos completos com foco em estética e saúde bucal. Nossa clínica usa tecnologia de ponta e atende por plano ou particular."
              value={state.offer_description}
              onChange={(e) => update({ offer_description: e.target.value })}
              rows={5}
              autoFocus
            />
          </div>
        </div>
      )}

      {/* Step 5 — Público-alvo */}
      {step === 5 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Quem é seu cliente ideal?</h2>
          <p className="text-sm text-muted-foreground">
            Descreva o perfil de quem costuma comprar de você.
          </p>
          <div className="space-y-1">
            <Label>Perfil do cliente</Label>
            <Textarea
              placeholder="Ex: Adultos entre 25-45 anos, classe média, que se preocupam com aparência e têm renda para investir em saúde bucal."
              value={state.target_audience}
              onChange={(e) => update({ target_audience: e.target.value })}
              rows={4}
              autoFocus
            />
          </div>
        </div>
      )}

      {/* Step 6 — Conclusão */}
      {step === 6 && (
        <div className="space-y-6">
          <div className="text-center space-y-2">
            <div className="text-4xl">🎯</div>
            <h2 className="text-xl font-semibold">Pronto! O que você quer fazer agora?</h2>
            <p className="text-sm text-muted-foreground">
              Suas informações básicas estão salvas. Escolha como continuar a configuração.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-3">
            <Card
              className="cursor-pointer border-2 border-primary/60 hover:border-primary hover:bg-primary/5 transition-all"
              onClick={() => !saving && handleFinish(true)}
            >
              <CardContent className="p-4 flex gap-3 items-start">
                <Zap className="h-5 w-5 text-primary mt-0.5 shrink-0" />
                <div>
                  <p className="font-semibold text-sm">Ativar Agente Espião</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    O sistema observa suas conversas reais e aprende sozinho como configurar o agente.
                    Recomendado para quem já usa o WhatsApp com clientes.
                  </p>
                  <Badge variant="secondary" className="mt-2 text-xs">Configuração automática</Badge>
                </div>
              </CardContent>
            </Card>
            <Card
              className="cursor-pointer border-2 border-border hover:border-muted-foreground/60 transition-all"
              onClick={() => !saving && handleFinish(false)}
            >
              <CardContent className="p-4 flex gap-3 items-start">
                <ArrowRight className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
                <div>
                  <p className="font-semibold text-sm">Configurar manualmente</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Acesse o AI Profile e preencha todos os detalhes do agente por conta própria.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Navegação */}
      {step < 6 && (
        <div className="flex justify-between mt-8">
          <Button
            variant="ghost"
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 0}
          >
            <ArrowLeft className="h-4 w-4 mr-1" /> Voltar
          </Button>
          <Button onClick={() => setStep((s) => s + 1)} disabled={!canNext()}>
            {step === 5 ? "Finalizar" : "Próximo"} <ArrowRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
}
