import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { AlertTriangle, Info, CheckCircle2, XCircle, Mic, ImageIcon, Video, MessageSquare, Zap } from "lucide-react";
import { api, SpyAgentModule, SpyAgentSample } from "@/services/api";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

const MODULES: { id: SpyAgentModule; label: string; description: string }[] = [
  {
    id: "facts",
    label: "Complementação de Fatos",
    description: "Extrai informações objetivas do negócio (nicho, oferta, público-alvo) das conversas.",
  },
  {
    id: "identity",
    label: "Identidade e Tom",
    description: "Aprende o estilo de comunicação, tom de voz e uso de emojis do vendedor.",
  },
  {
    id: "strategy",
    label: "Estratégia de Vendas",
    description: "Analisa como as vendas são conduzidas para recomendar o melhor tipo de agente.",
  },
];

const OBSERVATION_OPTIONS = [
  { days: 0,  label: "24 horas", badge: "Teste" },
  { days: 7,  label: "7 dias",   badge: "Rápido" },
  { days: 14, label: "14 dias",  badge: "Padrão", recommended: true },
  { days: 30, label: "30 dias",  badge: "Completo" },
  { days: 60, label: "60 dias",  badge: "Estendido" },
];

interface SpyAgentSetupProps {
  sample: SpyAgentSample | null;
  onStarted: () => void;
}

export function SpyAgentSetup({ sample, onStarted }: SpyAgentSetupProps) {
  const [selectedModules, setSelectedModules] = useState<SpyAgentModule[]>(["facts", "identity", "strategy"]);
  const [observationDays, setObservationDays] = useState(14);
  const [useOptimizedStrategy, setUseOptimizedStrategy] = useState(true);
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const toggleModule = (id: SpyAgentModule) => {
    setSelectedModules((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]
    );
  };

  const handleStart = async () => {
    if (selectedModules.length === 0) {
      toast({ title: "Selecione pelo menos um módulo", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      await api.spyAgent.start({
        modules: selectedModules,
        observation_days: observationDays,
        use_optimized_strategy: useOptimizedStrategy,
      });
      toast({ title: "Agente Espião ativado!", description: "O período de observação começou." });
      onStarted();
    } catch {
      toast({ title: "Erro ao ativar o Agente Espião", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const strategyModuleEnabled = selectedModules.includes("strategy");

  return (
    <div className="space-y-6">
      {/* Dados disponíveis */}
      {sample && (
        <Card className={cn("border", sample.has_enough_data ? "border-green-500/30 bg-green-500/5" : "border-yellow-500/30 bg-yellow-500/5")}>
          <CardContent className="p-3 flex items-center gap-3">
            {sample.has_enough_data
              ? <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
              : <AlertTriangle className="h-4 w-4 text-yellow-500 shrink-0" />}
            <p className="text-xs">
              {sample.has_enough_data
                ? <><strong>{sample.leads_count} leads</strong> com <strong>{sample.messages_count} mensagens</strong> disponíveis para análise.</>
                : <>Poucas conversas disponíveis ({sample.leads_count} leads, {sample.messages_count} msgs). Quanto mais conversas, melhor a análise.</>}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Módulos */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">O que o agente deve aprender?</h3>
        <p className="text-xs text-muted-foreground">Selecione os módulos de aprendizado.</p>
        {MODULES.map((mod) => (
          <div
            key={mod.id}
            onClick={() => toggleModule(mod.id)}
            className={cn(
              "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
              selectedModules.includes(mod.id) ? "border-primary/60 bg-primary/5" : "border-border hover:border-muted-foreground/40"
            )}
          >
            <Checkbox
              checked={selectedModules.includes(mod.id)}
              onCheckedChange={() => toggleModule(mod.id)}
              className="mt-0.5"
              onClick={(e) => e.stopPropagation()}
            />
            <div>
              <p className="text-sm font-medium">{mod.label}</p>
              <p className="text-xs text-muted-foreground">{mod.description}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Estratégia M3 */}
      {strategyModuleEnabled && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Como aprender a estratégia?</h3>
          <div className="grid grid-cols-2 gap-2">
            {[
              {
                value: true,
                icon: <Zap className="h-4 w-4 text-primary" />,
                badge: "Recomendado",
                title: "Estratégia do sistema",
                desc: "Usamos as melhores práticas de vendas do Orion. Ideal para quem ainda está estruturando seu processo.",
              },
              {
                value: false,
                icon: <AlertTriangle className="h-4 w-4 text-yellow-500" />,
                badge: "Avançado",
                title: "Aprender com minhas conversas",
                desc: "O sistema copia a forma como você já vende. Use apenas se seu processo de vendas já é maduro.",
              },
            ].map((opt) => (
              <Card
                key={String(opt.value)}
                onClick={() => setUseOptimizedStrategy(opt.value)}
                className={cn(
                  "cursor-pointer border-2 transition-all",
                  useOptimizedStrategy === opt.value ? "border-primary bg-primary/5" : "border-border"
                )}
              >
                <CardContent className="p-3 space-y-1.5">
                  <div className="flex items-center gap-1.5">
                    {opt.icon}
                    <Badge variant={opt.value ? "default" : "outline"} className="text-xs">{opt.badge}</Badge>
                  </div>
                  <p className="text-xs font-semibold">{opt.title}</p>
                  <p className="text-xs text-muted-foreground leading-relaxed">{opt.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          {!useOptimizedStrategy && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
              <AlertTriangle className="h-4 w-4 text-yellow-600 shrink-0 mt-0.5" />
              <p className="text-xs text-yellow-700 dark:text-yellow-400">
                Atenção: se suas conversas ainda não refletem um processo de vendas eficiente, o agente
                pode aprender comportamentos que reduzem o desempenho. Em dúvida, use "Estratégia do sistema".
              </p>
            </div>
          )}
        </div>
      )}

      {/* Período de observação */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Período de observação</h3>
        <p className="text-xs text-muted-foreground">
          O agente observa passivamente suas conversas durante este período — sem custo adicional.
          Ao término, a análise é iniciada automaticamente.
        </p>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {OBSERVATION_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              onClick={() => setObservationDays(opt.days)}
              className={cn(
                "relative flex flex-col items-center justify-center rounded-lg border p-2.5 text-xs transition-colors",
                observationDays === opt.days
                  ? "border-primary bg-primary/5 text-primary"
                  : "border-border text-muted-foreground hover:border-muted-foreground/60"
              )}
            >
              {opt.recommended && (
                <span className="absolute -top-2 left-1/2 -translate-x-1/2 text-[9px] bg-primary text-primary-foreground px-1.5 py-0.5 rounded-full whitespace-nowrap">
                  Padrão
                </span>
              )}
              <span className="font-semibold">{opt.label}</span>
              <span className="text-[10px] opacity-70">{opt.badge}</span>
            </button>
          ))}
        </div>
      </div>

      <Separator />

      {/* Orientações de mídia */}
      <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Info className="h-4 w-4 text-muted-foreground shrink-0" />
          <p className="text-sm font-semibold">Como obter o melhor resultado</p>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2">
          {[
            { icon: <MessageSquare className="h-3.5 w-3.5 text-green-500" />, label: "Texto", note: "Analisado automaticamente" },
            { icon: <Mic className="h-3.5 w-3.5 text-green-500" />, label: "Áudio", note: "Transcrito e analisado" },
            { icon: <ImageIcon className="h-3.5 w-3.5 text-green-500" />, label: "Imagem", note: "Interpretada visualmente" },
            { icon: <Video className="h-3.5 w-3.5 text-yellow-500" />, label: "Vídeo", note: "Não analisado" },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-2">
              {item.icon}
              <span className="text-xs">
                <strong>{item.label}</strong>{" "}
                <span className="text-muted-foreground">— {item.note}</span>
              </span>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          💡 Se você costuma enviar <strong>vídeos</strong> nas conversas, escreva uma mensagem de texto
          logo após descrevendo o conteúdo. Assim o agente consegue capturar a informação.
          Quanto mais conversas completas você tiver durante o período, mais precisa será a análise.
        </p>
      </div>

      <Button
        className="w-full"
        size="lg"
        onClick={handleStart}
        disabled={loading || selectedModules.length === 0}
      >
        {loading ? "Ativando..." : "Iniciar Observação"}
      </Button>
    </div>
  );
}
