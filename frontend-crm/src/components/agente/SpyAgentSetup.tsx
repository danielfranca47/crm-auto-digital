import { useState, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { AlertTriangle, Info, CheckCircle2, Phone, QrCode, Mic, ImageIcon, Video, MessageSquare, Zap, Loader2, Trash2, RefreshCw } from "lucide-react";
import { api, SpyAgentModule, SpyAgentSample, WhatsappConnectResponse } from "@/services/api";
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
  const [connectingInstance, setConnectingInstance] = useState(false);
  const [pendingConnect, setPendingConnect] = useState<WhatsappConnectResponse | null>(null);
  const [qrExpired, setQrExpired] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const qrTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Limpa timers ao desmontar
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (qrTimeoutRef.current) clearTimeout(qrTimeoutRef.current);
    };
  }, []);

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (qrTimeoutRef.current) { clearTimeout(qrTimeoutRef.current); qrTimeoutRef.current = null; }
  };

  const startPolling = (instanceId: string) => {
    stopPolling();
    // Expira QR após 90s
    qrTimeoutRef.current = setTimeout(() => {
      setQrExpired(true);
      stopPolling();
    }, 90_000);

    pollRef.current = setInterval(async () => {
      try {
        const status = await api.crm.whatsappStatus();
        if (status.status === "connected") {
          stopPolling();
          await api.spyAgent.setInstanceConfig(instanceId);
          queryClient.invalidateQueries({ queryKey: ["spy-instance-config"] });
          setPendingConnect(null);
          toast({ title: "Fone de observação conectado!", description: "WhatsApp escaneado com sucesso." });
        }
      } catch {
        // ignora erros pontuais no polling
      }
    }, 3_000);
  };

  const { data: instanceConfig, isLoading: instanceLoading } = useQuery({
    queryKey: ["spy-instance-config"],
    queryFn: () => api.spyAgent.getInstanceConfig(),
  });

  const toggleModule = (id: SpyAgentModule) => {
    setSelectedModules((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]
    );
  };

  const handleConnectSpyInstance = async () => {
    setConnectingInstance(true);
    setQrExpired(false);
    try {
      const resp = await api.crm.whatsappConnect();
      if (resp.qr?.value) {
        setPendingConnect(resp);
        startPolling(resp.instance_id);
      } else {
        // Já conectado — salva direto
        await api.spyAgent.setInstanceConfig(resp.instance_id);
        queryClient.invalidateQueries({ queryKey: ["spy-instance-config"] });
        toast({ title: "Fone de observação configurado!", description: "Instância já conectada." });
      }
    } catch {
      toast({ title: "Erro ao conectar fone espião", variant: "destructive" });
    } finally {
      setConnectingInstance(false);
    }
  };

  const handleRefreshQr = async () => {
    if (!pendingConnect) return;
    setQrExpired(false);
    setConnectingInstance(true);
    try {
      const resp = await api.crm.whatsappRefreshQr();
      setPendingConnect(resp);
      startPolling(resp.instance_id);
    } catch {
      toast({ title: "Erro ao renovar QR code", variant: "destructive" });
    } finally {
      setConnectingInstance(false);
    }
  };

  const handleCancelConnect = () => {
    stopPolling();
    setPendingConnect(null);
    setQrExpired(false);
  };

  const getQrSrc = (qr: WhatsappConnectResponse["qr"]): string | null => {
    if (!qr?.value) return null;
    if (qr.kind === "url") return qr.value;
    if (qr.kind === "base64") return `data:image/png;base64,${qr.value}`;
    // "text": pode ser data URI (data:image/...) ou base64 puro sem padding correto
    if (qr.value.startsWith("data:image")) return qr.value;
    if (qr.value.length > 80) return `data:image/png;base64,${qr.value}`;
    return null;
  };

  const handleRemoveSpyInstance = async () => {
    try {
      await api.spyAgent.removeInstanceConfig();
      queryClient.invalidateQueries({ queryKey: ["spy-instance-config"] });
      toast({ title: "Instância espiã removida" });
    } catch {
      toast({ title: "Erro ao remover instância", variant: "destructive" });
    }
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
        spy_instance_id: instanceConfig?.configured ? instanceConfig.spy_instance_id ?? undefined : undefined,
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

      {/* Fone de observação (instância espiã) */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Fone de observação</h3>
        <p className="text-xs text-muted-foreground">
          Conecte um telefone diferente do seu CRM. O agente observará as conversas desse fone sem interferir no seu pipeline.
        </p>
        {instanceLoading ? (
          <div className="flex items-center gap-2 p-3 rounded-lg border border-border">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Verificando...</span>
          </div>
        ) : instanceConfig?.configured ? (
          <div className="flex items-center justify-between p-3 rounded-lg border border-green-500/30 bg-green-500/5">
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-green-500 shrink-0" />
              <div>
                <p className="text-xs font-medium">
                  {instanceConfig.phone_e164 ?? instanceConfig.spy_instance_id}
                </p>
                <p className="text-[10px] text-muted-foreground capitalize">
                  {instanceConfig.connection_status ?? "verificando..."}
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-destructive"
              onClick={handleRemoveSpyInstance}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        ) : pendingConnect ? (
          <div className="rounded-lg border border-border bg-muted/20 p-4 space-y-3">
            {qrExpired ? (
              <div className="flex flex-col items-center gap-3 py-2">
                <p className="text-xs text-muted-foreground text-center">QR code expirado. Gere um novo.</p>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" className="gap-1.5" onClick={handleRefreshQr} disabled={connectingInstance}>
                    {connectingInstance ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                    Novo QR code
                  </Button>
                  <Button size="sm" variant="ghost" onClick={handleCancelConnect}>Cancelar</Button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium">Escaneie com o WhatsApp do fone a observar:</p>
                  <Button size="sm" variant="ghost" className="h-6 px-2 text-xs text-muted-foreground" onClick={handleCancelConnect}>
                    Cancelar
                  </Button>
                </div>
                {(() => {
                  const src = getQrSrc(pendingConnect.qr);
                  return src ? (
                    <div className="flex flex-col items-center gap-2">
                      <img
                        src={src}
                        alt="QR Code WhatsApp"
                        className="w-48 h-48 rounded border border-border bg-white object-contain"
                      />
                      <div className="text-[10px] text-muted-foreground text-center space-y-0.5">
                        <p>1. Abra o WhatsApp no celular que deseja observar</p>
                        <p>2. Vá em Menu → Aparelhos conectados</p>
                        <p>3. Escaneie este código</p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                        <span className="text-[10px] text-muted-foreground">Aguardando leitura...</span>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-2 py-2">
                      <p className="text-xs text-muted-foreground">QR code em formato não suportado.</p>
                      <Button size="sm" variant="outline" className="gap-1.5" onClick={handleRefreshQr} disabled={connectingInstance}>
                        <RefreshCw className="h-3.5 w-3.5" /> Tentar novamente
                      </Button>
                    </div>
                  );
                })()}
              </>
            )}
          </div>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="w-full gap-2"
            onClick={handleConnectSpyInstance}
            disabled={connectingInstance}
          >
            {connectingInstance
              ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Conectando...</>
              : <><QrCode className="h-3.5 w-3.5" /> Conectar fone de observação</>}
          </Button>
        )}
        {!instanceConfig?.configured && !pendingConnect && !instanceLoading && (
          <p className="text-xs text-muted-foreground">
            Sem fone configurado o agente analisará o histórico do CRM existente.
          </p>
        )}
      </div>

      <Separator />

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
            { icon: <Video className="h-3.5 w-3.5 text-yellow-500" />, label: "Vídeo", note: "Texto acompanhante capturado" },
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
