import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useToast } from "@/hooks/use-toast";
import {
  api,
  AiProfilePayload,
  AiTemplate,
  KnowledgeItem,
  WhatsappConnectResponse,
  WhatsappQrPayload,
  WhatsappStatusResponse,
} from "@/services/api";
import { useUsage } from "@/hooks/useUsage";
import { AlertCircle, Brain, Clock, FileEdit, FilePlus, RefreshCw, Sparkles, Upload, Wand2 } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const fallbackTemplates: Record<
  string,
  { name: string; description: string; tone: string; goals: string[] }
> = {
  sdr_padrao: {
    name: "SDR Padrão",
    description: "Abordagem consultiva para prospecção e qualificação inicial.",
    tone: "profissional e próximo",
    goals: ["Gerar interesse", "Agendar reuniões", "Nutrir leads frios"],
  },
  consultor_especialista: {
    name: "Consultor Especialista",
    description: "Consultor para vendas high-ticket com foco em discovery profundo.",
    tone: "consultivo e estratégico",
    goals: ["Conduzir discovery", "Mapear dores", "Elevar autoridade"],
  },
  closer_agressivo: {
    name: "Closer Agressivo",
    description: "Closer para low-ticket com senso de urgência controlado.",
    tone: "direto e objetivo",
    goals: ["Gerar urgência", "Objeções rápidas", "Fechar no primeiro contato"],
  },
};

const initialProfileState: AiProfilePayload = {
  template_key: "",
  name: "",
  brand_name: "",
  tone_of_voice: "",
  timezone: "UTC",
  niche: "",
  target_audience: "",
  offer_description: "",
  goals: "",
  custom_instructions: "",
  agent_mode: "agenda",
  identity_mode: "human_agent",
  handoff_policy: "keep_active_notify",
  handoff_custom_text: "",
  requires_handoff: false,
  human_in_loop: false,
  origin_inbound_opener: "",
  origin_outbound_opener: "",
  objection_common: "",
  qualification_score_threshold: 6,
  nurture_vs_discard_rule: "discard",
  warming_social_proof: "",
  warming_session_preview: "",
  offer_pack: null,
  appointment_reminder_offsets: null,
  briefing_enabled: true,
  briefing_channel: "whatsapp",
  briefing_lead_time: 2,
  operator_whatsapp: "",
  buying_signal_keywords: null,
  calendar_integration: "none",
  payment_gateway: null,
};

const goalSuggestions = [
  "Confirmar preço/local antes de sugerir horários",
  "Perguntar 3 informações obrigatórias antes de avançar",
  "Lidar com objeções comuns sem alongar conversa",
  "Encerrar educadamente quando não houver intenção",
  "Não agendar sem confirmação do lead",
];

const allowedExtensions = [".txt", ".csv", ".xlsx"];

function summarizeProfile(profile: AiProfilePayload) {
  const missing: string[] = [];
  ("template_key name brand_name tone_of_voice niche target_audience offer_description goals".split(
    " "
  ) as (keyof AiProfilePayload)[]).forEach((field) => {
    if (!profile[field]?.trim()) missing.push(field);
  });
  return { missing, complete: missing.length === 0 };
}

function toBulletList(goals: string[]) {
  return goals.map((g) => `- ${g}`).join("\n");
}

function formatDate(value?: string | null) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString("pt-BR");
  } catch {
    return value;
  }
}

type AgentModelUi = "agendador_com_humano" | "direto_autonomo" | "hibrido_agendador";

function profileToAgentModelUi(profile: Partial<AiProfilePayload>): AgentModelUi {
  const template = String(profile.template_key || "").toLowerCase();
  if (template === "hybrid_scheduler") return "hibrido_agendador";
  if (template === "closer_agressivo") return "direto_autonomo";
  if (template === "sdr_padrao" || template === "consultor_especialista") return "agendador_com_humano";

  const mode = String(profile.agent_mode || "").toLowerCase();
  const requires = Boolean(profile.requires_handoff);
  const human = Boolean(profile.human_in_loop);

  if (mode === "agendador_com_humano") return "agendador_com_humano";
  if (mode === "direto_autonomo") return "direto_autonomo";
  if (mode === "hibrido_agendador") return "hibrido_agendador";
  if (mode === "consultivo") return "agendador_com_humano";
  if (mode === "direto" || mode === "closer") return "direto_autonomo";
  if (mode === "sdr_scheduler") return "agendador_com_humano";
  if (mode === "agenda") return requires || human ? "agendador_com_humano" : "hibrido_agendador";
  return "hibrido_agendador";
}

function applyAgentModelUi(profile: AiProfilePayload, model: AgentModelUi): AiProfilePayload {
  if (model === "agendador_com_humano") {
    return {
      ...profile,
      template_key: profile.template_key || "sdr_padrao",
      agent_mode: "consultivo",
      requires_handoff: true,
      human_in_loop: true,
    };
  }
  if (model === "direto_autonomo") {
    return {
      ...profile,
      template_key: "closer_agressivo",
      agent_mode: "direto",
      requires_handoff: false,
      human_in_loop: false,
    };
  }
  return {
    ...profile,
    template_key: "hybrid_scheduler",
    agent_mode: "agenda",
    requires_handoff: false,
    human_in_loop: false,
  };
}

function KnowledgeLevel({ count }: { count: number }) {
  const label = count === 0 ? "Vazio" : count <= 3 ? "Básico" : "Enriquecido";
  const variant: "secondary" | "outline" | "default" =
    count === 0 ? "secondary" : count <= 3 ? "outline" : "default";
  return <Badge variant={variant}>{label}</Badge>;
}

export default function AiProfilePage() {
  const { toast } = useToast();
  const { handleError } = useApiErrorHandler();
  const { data: usageData, loading: usageLoading } = useUsage();

  const [templates, setTemplates] = useState<AiTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [profile, setProfile] = useState<AiProfilePayload>(initialProfileState);
  const [agentModelUi, setAgentModelUi] = useState<AgentModelUi>("hibrido_agendador");
  const [profileExists, setProfileExists] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [saving, setSaving] = useState(false);

  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
  const [loadingKnowledge, setLoadingKnowledge] = useState(false);
  const [knowledgeModalOpen, setKnowledgeModalOpen] = useState(false);
  const [knowledgeTab, setKnowledgeTab] = useState("manual");
  const [manualTitle, setManualTitle] = useState("");
  const [manualContent, setManualContent] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [editingItem, setEditingItem] = useState<KnowledgeItem | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [viewItem, setViewItem] = useState<KnowledgeItem | null>(null);

  const [cadenceStr, setCadenceStr] = useState("");
  const [cadenceError, setCadenceError] = useState<string | null>(null);
  const [reminderHour1, setReminderHour1] = useState<string>("24");
  const [reminderHour2, setReminderHour2] = useState<string>("1");
  const [buyingSignalStr, setBuyingSignalStr] = useState("");

  const [whatsappQr, setWhatsappQr] = useState<WhatsappQrPayload | null>(null);
  const [whatsappStatus, setWhatsappStatus] = useState<WhatsappStatusResponse | null>(null);
  const [whatsappPhase, setWhatsappPhase] = useState<"idle" | "connecting" | "connected" | "error">(
    "idle"
  );
  const [whatsappError, setWhatsappError] = useState<string | null>(null);
  const [whatsappLoading, setWhatsappLoading] = useState(false);
  const pollingRef = useRef<number | null>(null);
  const refreshTimeoutRef = useRef<number | null>(null);
  const refreshCountRef = useRef(0);
  const connectDebounceRef = useRef(0);
  const connectLockRef = useRef(false);
  const pollAttemptRef = useRef(0);
  const phaseRef = useRef(whatsappPhase);

  const entitlements = usageData?.entitlements;
  const limits = entitlements?.limits ?? {};
  const maxIa = limits?.max_ia_conversas_monthly;
  const crmSub = entitlements?.products?.find(
    (p) => p?.product_code === "crm" && (p.status ?? "") === "active"
  );
  const isCrmFree = crmSub?.plan_code === "crm_free";
  const isUnlimited = maxIa === null;
  const isUnknown = maxIa === undefined;
  const iaAvailable = isUnlimited || (typeof maxIa === "number" && maxIa > 0);
  const showIaUnavailableBanner = !usageLoading && !!usageData && !isUnknown && !iaAvailable;

  const status = useMemo(() => summarizeProfile(profile), [profile]);
  const previewText = useMemo(() => {
    if (!profile.name && !profile.brand_name) return "Preencha os campos para ver o preview.";
    const intro = `Olá! Eu sou ${profile.name || "seu agente"} da ${profile.brand_name || "sua marca"}.`;
    const tone = profile.tone_of_voice ? `Vou manter um tom ${profile.tone_of_voice}.` : "";
    const offer = profile.offer_description
      ? `Posso te ajudar com ${profile.offer_description.toLowerCase()}.`
      : "";
    const target = profile.target_audience ? `Atendo principalmente ${profile.target_audience}.` : "";
    return `${intro} ${tone} ${offer} ${target}`.trim();
  }, [profile]);

  const exampleReply = useMemo(() => {
    if (!profile.tone_of_voice) return "Defina o tom de voz para gerar uma resposta exemplo.";
    return `Exemplo (${profile.tone_of_voice}): Obrigado pelo interesse! ${
      profile.offer_description
        ? `Temos uma oferta focada em ${profile.offer_description.toLowerCase()}.`
        : "Posso explicar melhor nossa solução."
    }`;
  }, [profile]);

  const mappedTemplates = useMemo(() => {
    if (!templates.length) return Object.entries(fallbackTemplates).map(([key, meta]) => ({
      key,
      name: meta.name,
      description: meta.description,
    }));
    return templates.map((tpl) => ({
      ...tpl,
      name: tpl.name || fallbackTemplates[tpl.key]?.name || tpl.key,
      description: tpl.description ?? fallbackTemplates[tpl.key]?.description,
    }));
  }, [templates]);

  const normalizedWhatsStatus = (whatsappStatus?.status || "").toLowerCase();
  const isWhatsappConnected = normalizedWhatsStatus === "connected";
  const showAdvancedTechnical = import.meta.env.DEV;

  const whatsappStatusLabel = (() => {
    if (whatsappPhase === "error") return "Erro";
    if (isWhatsappConnected) return "Conectado";
    if (whatsappPhase === "connecting") return "Conectando";
    if (whatsappStatus?.status) return whatsappStatus.status;
    return "Não conectado";
  })();

  const whatsappBadgeVariant = isWhatsappConnected
    ? "default"
    : whatsappPhase === "error"
    ? "destructive"
    : "secondary";

  const clearPolling = () => {
    if (pollingRef.current) {
      window.clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const clearRefreshTimeout = () => {
    if (refreshTimeoutRef.current) {
      window.clearTimeout(refreshTimeoutRef.current);
      refreshTimeoutRef.current = null;
    }
  };

  const POLL_BACKOFF_MS = [2000, 4000, 8000, 15000];

  const scheduleStatusPoll = () => {
    clearPolling();
    const attempt = Math.min(pollAttemptRef.current, POLL_BACKOFF_MS.length - 1);
    const waitMs = POLL_BACKOFF_MS[attempt];
    pollingRef.current = window.setTimeout(async () => {
      if (phaseRef.current !== "connecting") return;
      await handleWhatsappStatus(true);
      if (phaseRef.current === "connecting") {
        pollAttemptRef.current += 1;
        scheduleStatusPoll();
      }
    }, waitMs);
  };

  const startPolling = () => {
    pollAttemptRef.current = 0;
    scheduleStatusPoll();
  };

  const scheduleAutoRefresh = () => {
    clearRefreshTimeout();
    refreshTimeoutRef.current = window.setTimeout(async () => {
      if (phaseRef.current !== "connecting") return;
      if (refreshCountRef.current >= 3) return;
      refreshCountRef.current += 1;
      if (import.meta.env.DEV) {
        console.log("WhatsApp auto-refresh QR", { attempt: refreshCountRef.current });
      }
      await handleWhatsappRefreshQr({ auto: true });
    }, 20000);
  };

  const startConnectingFlow = () => {
    setWhatsappPhase("connecting");
    startPolling();
    scheduleAutoRefresh();
  };

  const stopConnectingFlow = () => {
    clearPolling();
    clearRefreshTimeout();
    pollAttemptRef.current = 0;
  };

  async function loadTemplates() {
    setLoadingTemplates(true);
    try {
      const data = await api.core.getAiTemplates();
      setTemplates(data);
    } catch (err) {
      handleError(err, { fallbackMessage: "Falha ao carregar templates." });
    } finally {
      setLoadingTemplates(false);
    }
  }

  async function loadProfile() {
    setLoadingProfile(true);
    try {
      const data = await api.core.getAiProfileMe();
      const loadedProfile = {
        ...initialProfileState,
        ...data,
        briefing_lead_time: typeof data.briefing_lead_time === "number"
          ? Math.round(data.briefing_lead_time / 60)
          : initialProfileState.briefing_lead_time,
      };
      const inferredModel = profileToAgentModelUi(loadedProfile);
      const normalizedLoadedProfile = applyAgentModelUi(loadedProfile, inferredModel);
      setProfile(normalizedLoadedProfile);
      setCadenceStr(Array.isArray(data.followup_cadence) ? data.followup_cadence.join(", ") : "");
      if (Array.isArray(data.appointment_reminder_offsets) && data.appointment_reminder_offsets.length >= 2) {
        setReminderHour1(String(Math.abs(data.appointment_reminder_offsets[0]) / 60));
        setReminderHour2(String(Math.abs(data.appointment_reminder_offsets[1]) / 60));
      } else {
        const isA3 = (data.template_key || "").toLowerCase() === "hybrid_scheduler";
        setReminderHour1("24");
        setReminderHour2(isA3 ? "2" : "1");
      }
      setBuyingSignalStr(Array.isArray(data.buying_signal_keywords) ? data.buying_signal_keywords.join("\n") : "");
      setAgentModelUi(inferredModel);
      setProfileExists(true);
    } catch (err: any) {
      handleError(err, {
        fallbackMessage: "Falha ao carregar perfil de IA.",
        silent: err?.status === 404,
      });
      if ((err as any)?.status === 404) {
        setProfile(initialProfileState);
        setAgentModelUi(profileToAgentModelUi(initialProfileState));
        setProfileExists(false);
      }
    } finally {
      setLoadingProfile(false);
    }
  }

  async function loadKnowledge() {
    setLoadingKnowledge(true);
    try {
      const data = await api.crm.getKnowledgeList();
      setKnowledgeItems(data);
    } catch (err) {
      handleError(err, { fallbackMessage: "Falha ao carregar conhecimento." });
    } finally {
      setLoadingKnowledge(false);
    }
  }

  useEffect(() => {
    loadTemplates();
    loadProfile();
    loadKnowledge();
    handleWhatsappStatus(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => {
      clearPolling();
      clearRefreshTimeout();
    };
  }, []);

  useEffect(() => {
    phaseRef.current = whatsappPhase;
    if (isWhatsappConnected) {
      setWhatsappPhase("connected");
      stopConnectingFlow();
    }
  }, [isWhatsappConnected]);

  useEffect(() => {
    setProfile((prev) => {
      if (prev.agent_mode) return prev;
      const inferred =
        prev.template_key && prev.template_key.startsWith("closer") ? "direto" : "agenda";
      return { ...prev, agent_mode: inferred };
    });
  }, [profile.template_key]);

  useEffect(() => {
    setAgentModelUi(profileToAgentModelUi(profile));
  }, [profile.agent_mode, profile.requires_handoff, profile.human_in_loop]);

  const handleTemplateSelect = (tpl: AiTemplate) => {
    const preset = fallbackTemplates[tpl.key] || fallbackTemplates.sdr_padrao;
    setProfile((prev) => ({
      ...prev,
      template_key: tpl.key,
      tone_of_voice: prev.tone_of_voice || preset.tone,
      goals: prev.goals || toBulletList(preset.goals),
    }));
  };

  async function handleSave() {
    if (saving) return;
    if (!profileExists) {
      const essentials = summarizeProfile(profile);
      if (!essentials.complete) {
        toast({
          title: "Campos obrigatórios",
          description: "Preencha os campos essenciais para criar o perfil.",
          variant: "destructive",
        });
        return;
      }
    }
    // Validar e parsear cadência
    let parsedCadence: number[] | null = null;
    if (cadenceStr.trim()) {
      const parts = cadenceStr.split(",").map((s) => s.trim()).filter(Boolean);
      const nums = parts.map(Number);
      if (nums.some(isNaN) || nums.some((n) => n <= 0)) {
        setCadenceError("Cadência inválida: use números positivos separados por vírgula (ex: 30, 1440, 4320).");
        return;
      }
      const maxAttempts = profile.followup_max_attempts ?? 0;
      if (maxAttempts > 0 && nums.length !== maxAttempts - 1) {
        setCadenceError(`A cadência deve ter exatamente ${maxAttempts - 1} elemento(s) para ${maxAttempts} tentativas.`);
        return;
      }
      parsedCadence = nums;
    }
    setCadenceError(null);

    setSaving(true);
    try {
      const inferredModel = profileToAgentModelUi(profile);
      const normalizedProfile = applyAgentModelUi(profile, inferredModel);
      const h1 = parseInt(reminderHour1, 10);
      const h2 = parseInt(reminderHour2, 10);
      const parsedReminderOffsets = (!isNaN(h1) && h1 > 0 && !isNaN(h2) && h2 > 0)
        ? [-(h1 * 60), -(h2 * 60)]
        : null;
      const parsedBuyingSignals = buyingSignalStr.trim()
        ? buyingSignalStr.split("\n").map((s) => s.trim()).filter(Boolean)
        : null;
      const payload: AiProfilePayload = {
        ...normalizedProfile,
        timezone: normalizedProfile.timezone?.trim() ? normalizedProfile.timezone : "UTC",
        custom_instructions: normalizedProfile.custom_instructions?.trim() || null,
        handoff_custom_text: normalizedProfile.handoff_custom_text?.trim() || null,
        followup_cadence: parsedCadence,
        followup_allowed_hours: normalizedProfile.followup_allowed_hours?.trim() || null,
        appointment_reminder_offsets: parsedReminderOffsets,
        briefing_lead_time: normalizedProfile.briefing_lead_time
          ? normalizedProfile.briefing_lead_time * 60
          : null,
        operator_whatsapp: normalizedProfile.operator_whatsapp?.trim() || null,
        buying_signal_keywords: parsedBuyingSignals,
      };
      const fn = profileExists ? api.core.updateAiProfileMe : api.core.createAiProfile;
      const saved = await fn(payload);
      const savedProfile = { ...initialProfileState, ...saved };
      const savedModel = profileToAgentModelUi(savedProfile);
      setProfile(applyAgentModelUi(savedProfile, savedModel));
      setAgentModelUi(savedModel);
      setProfileExists(true);
      toast({ title: "Perfil salvo", description: "Identidade do agente atualizada." });
    } catch (err) {
      handleError(err, { fallbackMessage: "Falha ao salvar perfil." });
    } finally {
      setSaving(false);
    }
  }

  const normalizeConnectResponse = (data: WhatsappConnectResponse) => {
    setWhatsappStatus((prev) => ({
      ...prev,
      instance_id: data.instance_id,
      status: data.status ?? prev?.status,
    }));
    if (data.qr) {
      setWhatsappQr(data.qr);
    }
    if (import.meta.env.DEV) {
      console.log("WhatsApp connect response", { status: data.status, qrKind: data.qr?.kind });
    }
    if (data.status && data.status.toLowerCase() === "connected") {
      setWhatsappPhase("connected");
      stopConnectingFlow();
    } else {
      startConnectingFlow();
    }
  };

  async function handleWhatsappConnect() {
    const now = Date.now();
    if (whatsappLoading || connectLockRef.current) return;
    if (now - connectDebounceRef.current < 1200) return;
    connectDebounceRef.current = now;
    connectLockRef.current = true;
    setWhatsappLoading(true);
    setWhatsappError(null);
    try {
      refreshCountRef.current = 0;
      pollAttemptRef.current = 0;
      const data = await api.crm.whatsappConnect();
      normalizeConnectResponse(data);
    } catch (err: any) {
      setWhatsappPhase("error");
      setWhatsappError(err?.message || "Falha ao conectar WhatsApp.");
      handleError(err, { fallbackMessage: "Falha ao conectar WhatsApp." });
    } finally {
      setWhatsappLoading(false);
      window.setTimeout(() => {
        connectLockRef.current = false;
      }, 1200);
    }
  }

  async function handleWhatsappStatus(silent = false) {
    try {
      const data = await api.crm.whatsappStatus();
      if (import.meta.env.DEV) {
        console.log("WhatsApp status poll", { status: data.status });
      }
      setWhatsappStatus(data);
      if (data.status && data.status.toLowerCase() === "connected") {
        setWhatsappPhase("connected");
        stopConnectingFlow();
      } else if (phaseRef.current !== "connecting") {
        setWhatsappPhase("idle");
      }
    } catch (err: any) {
      if (err?.status === 404) {
        setWhatsappStatus(null);
        setWhatsappPhase("idle");
        setWhatsappQr(null);
        return;
      }
      if (!silent) {
        setWhatsappPhase("error");
        setWhatsappError(err?.message || "Falha ao consultar status.");
        handleError(err, { fallbackMessage: "Falha ao consultar status." });
      }
    }
  }

  async function handleWhatsappRefreshQr(opts?: { auto?: boolean }) {
    if (whatsappLoading) return;
    setWhatsappLoading(true);
    setWhatsappError(null);
    try {
      const data = await api.crm.whatsappRefreshQr();
      if (import.meta.env.DEV) {
        console.log("WhatsApp QR refresh", { status: data.status, qrKind: data.qr?.kind });
      }
      if (!opts?.auto) {
        refreshCountRef.current = 0;
      }
      normalizeConnectResponse(data);
    } catch (err: any) {
      setWhatsappPhase("error");
      setWhatsappError(err?.message || "Falha ao gerar novo QR.");
      handleError(err, { fallbackMessage: "Falha ao gerar novo QR." });
    } finally {
      setWhatsappLoading(false);
    }
  }

  async function handleCreateManual() {
    if (!manualTitle.trim() || manualContent.trim().length < 20) {
      toast({
        title: "Conteúdo insuficiente",
        description: "Informe um título e pelo menos 20 caracteres de conteúdo.",
        variant: "destructive",
      });
      return;
    }
    setUploading(true);
    try {
      const created = await api.crm.createKnowledgeManual({
        title: manualTitle.trim(),
        content_text: manualContent.trim(),
      });
      setKnowledgeItems((items) => [created, ...items]);
      setManualTitle("");
      setManualContent("");
      setKnowledgeModalOpen(false);
      toast({ title: "Conhecimento adicionado", description: "Conteúdo manual salvo." });
    } catch (err) {
      handleError(err, { fallbackMessage: "Falha ao salvar conhecimento." });
    } finally {
      setUploading(false);
    }
  }

  const validateFile = (file: File) => {
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
    return allowedExtensions.includes(ext);
  };

  async function handleUploadFile() {
    if (!selectedFile) {
      toast({ title: "Selecione um arquivo", variant: "destructive" });
      return;
    }
    if (!validateFile(selectedFile)) {
      toast({
        title: "Formato não suportado",
        description: "Use apenas .txt, .csv ou .xlsx (sem PDF).",
        variant: "destructive",
      });
      return;
    }
    setUploading(true);
    try {
      const created = await api.crm.uploadKnowledgeFile(selectedFile);
      setKnowledgeItems((items) => [created, ...items]);
      setSelectedFile(null);
      setKnowledgeModalOpen(false);
      toast({ title: "Arquivo processado", description: "Conhecimento criado a partir do arquivo." });
    } catch (err) {
      handleError(err, { fallbackMessage: "Falha no upload." });
    } finally {
      setUploading(false);
    }
  }

  async function handleDeleteItem(item: KnowledgeItem) {
    const confirmed = window.confirm(`Remover '${item.title}'?`);
    if (!confirmed) return;
    try {
      await api.crm.deleteKnowledge(item.id);
      setKnowledgeItems((items) => items.filter((k) => k.id !== item.id));
      toast({ title: "Removido", description: "Item excluído com sucesso." });
    } catch (err) {
      handleError(err, { fallbackMessage: "Não foi possível remover o item." });
    }
  }

  function openEdit(item: KnowledgeItem) {
    setEditingItem(item);
    setEditTitle(item.title);
    setEditContent(item.content_text);
  }

  async function handleEditSave() {
    if (!editingItem) return;
    try {
      const updated = await api.crm.updateKnowledge(editingItem.id, {
        title: editTitle,
        content_text: editContent,
      });
      setKnowledgeItems((items) =>
        items.map((k) => (k.id === editingItem.id ? updated : k))
      );
      setEditingItem(null);
      toast({ title: "Item atualizado", description: "Alterações salvas." });
    } catch (err) {
      handleError(err, { fallbackMessage: "Não foi possível atualizar." });
    }
  }

  const knowledgeStatus = <KnowledgeLevel count={knowledgeItems.length} />;
  const qrIsImage =
    !!whatsappQr?.value &&
    (whatsappQr.kind === "url" || whatsappQr.value.startsWith("data:image/"));

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h1 className="text-3xl font-bold tracking-tight">Identidade do Agente</h1>
          </div>
          <p className="text-muted-foreground">
            Configure o comportamento do agente e organize o conhecimento do negócio.
          </p>
          {showIaUnavailableBanner && (
            <Alert className="mt-3 border-orange-400/60 bg-orange-50/40 dark:bg-orange-950/20">
              <AlertCircle className="h-4 w-4" />
              {isCrmFree ? (
                <>
                  <AlertTitle>Conversational AI indisponível</AlertTitle>
                  <AlertDescription>
                    Seu plano atual não inclui o agente conversacional. Ainda assim, você pode
                    configurar o perfil e o conhecimento.{" "}
                    <a className="underline" href="/assinatura">
                      Ver planos
                    </a>.
                  </AlertDescription>
                </>
              ) : (
                <>
                  <AlertTitle>Créditos de Conversational AI esgotados</AlertTitle>
                  <AlertDescription>
                    Seus créditos de conversas mensais foram esgotados.{" "}
                    <a className="underline" href="/assinatura">
                      Comprar créditos
                    </a>.
                  </AlertDescription>
                </>
              )}
            </Alert>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={status.complete ? "default" : "secondary"}>
            {status.complete ? "Perfil completo" : "Perfil incompleto"}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={loadProfile}
            disabled={loadingProfile || loadingTemplates}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${loadingProfile ? "animate-spin" : ""}`} />
            Restaurar
          </Button>
          <Button onClick={handleSave} disabled={saving || loadingTemplates}>
            {saving ? "Salvando..." : "Salvar"}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">Identidade do agente</TabsTrigger>
          <TabsTrigger value="knowledge">Conhecimento do negócio</TabsTrigger>
          <TabsTrigger value="followup">Follow-up</TabsTrigger>
          <TabsTrigger value="apresentacao">Apresentação e agendamento</TabsTrigger>
          <TabsTrigger value="oferta">Oferta e Pagamento</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Modelo do Agente</CardTitle>
              <CardDescription>Escolha o formato de atendimento principal.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-2 md:grid-cols-3">
                <button
                  type="button"
                  className={`rounded-md border p-3 text-left ${agentModelUi === "agendador_com_humano" ? "border-primary bg-primary/5" : ""}`}
                  onClick={() => setProfile((p) => applyAgentModelUi(p, "agendador_com_humano"))}
                >
                  <div className="font-medium">Agendador com humano</div>
                  <p className="text-xs text-muted-foreground">Qualifica e agenda com handoff humano.</p>
                </button>
                <button
                  type="button"
                  className={`rounded-md border p-3 text-left ${agentModelUi === "direto_autonomo" ? "border-primary bg-primary/5" : ""}`}
                  onClick={() => setProfile((p) => applyAgentModelUi(p, "direto_autonomo"))}
                >
                  <div className="font-medium">Direto autônomo</div>
                  <p className="text-xs text-muted-foreground">Foco em fechamento sem handoff.</p>
                </button>
                <button
                  type="button"
                  className={`rounded-md border p-3 text-left ${agentModelUi === "hibrido_agendador" ? "border-primary bg-primary/5" : ""}`}
                  onClick={() => setProfile((p) => applyAgentModelUi(p, "hibrido_agendador"))}
                >
                  <div className="font-medium">Híbrido agendador</div>
                  <p className="text-xs text-muted-foreground">Agenda com autonomia operacional.</p>
                </button>
              </div>

              {showAdvancedTechnical && (
                <details className="rounded-md border p-3">
                  <summary className="cursor-pointer text-sm font-medium">Configurações avançadas (técnico)</summary>
                  <div className="mt-3 space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <Wand2 className="h-4 w-4 text-primary" /> Template / Estilo do agente
                    </div>
                    <div className="grid gap-3 md:grid-cols-3">
                      {loadingTemplates && <p>Carregando templates...</p>}
                      {!loadingTemplates &&
                        mappedTemplates.map((tpl) => (
                          <button
                            key={tpl.key}
                            className={`rounded-lg border p-4 text-left transition hover:border-primary/60 hover:shadow-sm ${
                              profile.template_key === tpl.key ? "border-primary bg-primary/5" : ""
                            }`}
                            onClick={() => handleTemplateSelect(tpl)}
                            type="button"
                          >
                            <div className="flex items-center justify-between">
                              <div className="font-semibold">{tpl.name || tpl.key}</div>
                              {profile.template_key === tpl.key && (
                                <Badge variant="default" className="text-xs">Selecionado</Badge>
                              )}
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground line-clamp-3">
                              {tpl.description || fallbackTemplates[tpl.key]?.description}
                            </p>
                          </button>
                        ))}
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="space-y-2">
                      <Label>Agent Profile Mode</Label>
                      <Select
                        value={profile.agent_mode || "agenda"}
                        onValueChange={(value) =>
                          setProfile((p) => ({ ...p, agent_mode: value as AiProfilePayload["agent_mode"] }))
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Selecione o modo do agente" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="consultivo">Consultivo</SelectItem>
                          <SelectItem value="agenda">Agenda</SelectItem>
                          <SelectItem value="direto">Direto</SelectItem>
                          <SelectItem value="sdr_scheduler">SDR Scheduler (legado)</SelectItem>
                          <SelectItem value="closer">Closer (legado)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Requer handoff humano</Label>
                      <Select
                        value={String(!!profile.requires_handoff)}
                        onValueChange={(value) =>
                          setProfile((p) => ({ ...p, requires_handoff: value === "true" }))
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Selecione" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="false">Não</SelectItem>
                          <SelectItem value="true">Sim</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Human in loop</Label>
                      <Select
                        value={String(!!profile.human_in_loop)}
                        onValueChange={(value) =>
                          setProfile((p) => ({ ...p, human_in_loop: value === "true" }))
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Selecione" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="false">Não</SelectItem>
                          <SelectItem value="true">Sim</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  </div>
                </details>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Identidade e marca</CardTitle>
                <CardDescription>Como o agente se apresenta.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label>Nome do agente</Label>
                  <Input
                    value={profile.name}
                    placeholder="Ex.: Ana, seu copilot de vendas"
                    onChange={(e) => setProfile((p) => ({ ...p, name: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Marca</Label>
                  <Input
                    value={profile.brand_name}
                    placeholder="Ex.: Auto Digital"
                    onChange={(e) => setProfile((p) => ({ ...p, brand_name: e.target.value }))}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Nicho e público</CardTitle>
                <CardDescription>Quem você atende.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label>Fuso horário (timezone)</Label>
                  <Select
                    value={profile.timezone || "UTC"}
                    onValueChange={(value) => setProfile((p) => ({ ...p, timezone: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Selecione o fuso horário" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="UTC">UTC</SelectItem>
                      <SelectItem value="Europe/Lisbon">Europe/Lisbon</SelectItem>
                      <SelectItem value="America/Sao_Paulo">America/Sao_Paulo</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Use o formato IANA (ex.: Europe/Lisbon).
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Nicho</Label>
                  <Input
                    value={profile.niche}
                    placeholder="Ex.: Software B2B para marketing"
                    onChange={(e) => setProfile((p) => ({ ...p, niche: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Público-alvo</Label>
                  <Input
                    value={profile.target_audience}
                    placeholder="Ex.: PMEs de e-commerce"
                    onChange={(e) => setProfile((p) => ({ ...p, target_audience: e.target.value }))}
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Oferta</CardTitle>
                <CardDescription>Explique o que você vende.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <Textarea
                  value={profile.offer_description}
                  placeholder="Ex.: Implementação completa do CRM com onboarding em 14 dias."
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, offer_description: e.target.value }))
                  }
                  rows={4}
                />
                <div className="text-xs text-muted-foreground text-right">
                  {profile.offer_description.length} caracteres
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Tom de voz</CardTitle>
                <CardDescription>Como o agente fala.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <Select
                  value={profile.tone_of_voice}
                  onValueChange={(value) => setProfile((p) => ({ ...p, tone_of_voice: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione um tom" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="consultivo">Consultivo</SelectItem>
                    <SelectItem value="direto">Direto</SelectItem>
                    <SelectItem value="acolhedor">Acolhedor</SelectItem>
                    <SelectItem value="entusiasmado">Entusiasmado</SelectItem>
                    <SelectItem value="profissional e próximo">Profissional e próximo</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  value={profile.tone_of_voice}
                  onChange={(e) => setProfile((p) => ({ ...p, tone_of_voice: e.target.value }))}
                  placeholder="Ou personalize o tom"
                />
              </CardContent>
            </Card>
          </div>

          {/* ── Contexto do Negócio — Qualificação ── */}
          <Card>
            <CardHeader>
              <CardTitle>Contexto do Negócio</CardTitle>
              <CardDescription>Mensagens de abertura por origem e objeção mais comum.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="origin_inbound_opener">
                    <code className="text-xs">origin_inbound_opener</code>
                  </Label>
                  <Badge variant={profile.origin_inbound_opener?.trim() ? "default" : "secondary"}>
                    {profile.origin_inbound_opener?.trim() ? "Configurado" : "Usando default do template"}
                  </Badge>
                </div>
                <Textarea
                  id="origin_inbound_opener"
                  value={profile.origin_inbound_opener ?? ""}
                  placeholder="Oi! Vi que você veio pelo anúncio de X..."
                  onChange={(e) => setProfile((p) => ({ ...p, origin_inbound_opener: e.target.value }))}
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="origin_outbound_opener">
                    <code className="text-xs">origin_outbound_opener</code>
                  </Label>
                  <Badge variant={profile.origin_outbound_opener?.trim() ? "default" : "secondary"}>
                    {profile.origin_outbound_opener?.trim() ? "Configurado" : "Usando default do template"}
                  </Badge>
                </div>
                <Textarea
                  id="origin_outbound_opener"
                  value={profile.origin_outbound_opener ?? ""}
                  placeholder="Oi [Nome], sou assistente da [Empresa]..."
                  onChange={(e) => setProfile((p) => ({ ...p, origin_outbound_opener: e.target.value }))}
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="objection_common">
                    <code className="text-xs">objection_common</code>
                  </Label>
                  <Badge variant={profile.objection_common?.trim() ? "default" : "secondary"}>
                    {profile.objection_common?.trim() ? "Configurado" : "Não configurado"}
                  </Badge>
                </div>
                <Input
                  id="objection_common"
                  value={profile.objection_common ?? ""}
                  placeholder="Preciso pensar mais"
                  onChange={(e) => setProfile((p) => ({ ...p, objection_common: e.target.value }))}
                />
              </div>

              {/* Aquecimento — warming (Tarefa 3.8) */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="warming_social_proof">
                    <code className="text-xs">warming_social_proof</code>
                  </Label>
                  <Badge variant={profile.warming_social_proof?.trim() ? "default" : "secondary"}>
                    {profile.warming_social_proof?.trim() ? "Configurado" : "Não configurado"}
                  </Badge>
                </div>
                <Textarea
                  id="warming_social_proof"
                  value={profile.warming_social_proof ?? ""}
                  placeholder="A Ana, personal trainer como você, dobrou sua agenda em 2 meses"
                  onChange={(e) => setProfile((p) => ({ ...p, warming_social_proof: e.target.value }))}
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="warming_session_preview">
                    <code className="text-xs">warming_session_preview</code>
                  </Label>
                  <Badge variant={profile.warming_session_preview?.trim() ? "default" : "secondary"}>
                    {profile.warming_session_preview?.trim() ? "Configurado" : "Não configurado"}
                  </Badge>
                </div>
                <Textarea
                  id="warming_session_preview"
                  value={profile.warming_session_preview ?? ""}
                  placeholder="Na sessão de 1h vamos mapear seus objetivos e montar seu plano"
                  onChange={(e) => setProfile((p) => ({ ...p, warming_session_preview: e.target.value }))}
                  rows={2}
                />
              </div>
            </CardContent>
          </Card>

          {/* ── Filtros de qualificação ── */}
          <Card>
            <CardHeader>
              <CardTitle>Filtros de qualificação</CardTitle>
              <CardDescription>Defina o score mínimo e o destino de leads não qualificados.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>
                    <code className="text-xs">qualification_score_threshold</code>
                    <span className="ml-2 text-muted-foreground text-xs">Score mínimo para avançar ao agendamento</span>
                  </Label>
                  <Badge variant="outline">
                    {profile.qualification_score_threshold ?? 6}/12 pontos
                  </Badge>
                </div>
                <Slider
                  min={0}
                  max={12}
                  step={1}
                  value={[profile.qualification_score_threshold ?? 6]}
                  onValueChange={([val]) => setProfile((p) => ({ ...p, qualification_score_threshold: val }))}
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>0</span>
                  <span>12</span>
                </div>
              </div>
              <div className="flex items-center justify-between gap-4">
                <div className="space-y-1">
                  <Label>
                    <code className="text-xs">nurture_vs_discard_rule</code>
                  </Label>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <p className="text-xs text-muted-foreground cursor-help underline decoration-dotted">
                          {profile.nurture_vs_discard_rule === "nurture" ? "Nurture passivo" : "Descarte"}
                        </p>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        Nurture: lead vai para lista de reaquecimento futuro. Descarte: arquivado permanentemente.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Descarte</span>
                  <Switch
                    checked={profile.nurture_vs_discard_rule === "nurture"}
                    onCheckedChange={(checked) =>
                      setProfile((p) => ({ ...p, nurture_vs_discard_rule: checked ? "nurture" : "discard" }))
                    }
                  />
                  <span className="text-sm">Nurture passivo</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {(profile.requires_handoff || profile.human_in_loop) && (
            <Card>
              <CardHeader>
                <CardTitle>Atendimento humano (Handoff)</CardTitle>
                <CardDescription>Defina como o agente se identifica e quando aciona um humano.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Modo de identidade</Label>
                  <Select
                    value={profile.identity_mode}
                    onValueChange={(value) =>
                      setProfile((p) => ({ ...p, identity_mode: value as AiProfilePayload["identity_mode"] }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Selecione o modo" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="virtual_assistant">Assistente virtual</SelectItem>
                      <SelectItem value="human_agent">Humano do time</SelectItem>
                      <SelectItem value="user_clone">Clone do usuário</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Define como o agente se apresenta no início das conversas.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Política quando o lead pedir humano</Label>
                  <Select
                    value={profile.handoff_policy}
                    onValueChange={(value) =>
                      setProfile((p) => ({ ...p, handoff_policy: value as AiProfilePayload["handoff_policy"] }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Selecione a política" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="keep_active_notify">Manter bot e notificar</SelectItem>
                      <SelectItem value="disable_bot">Desativar bot para este lead</SelectItem>
                      <SelectItem value="ignore">Ignorar pedido e continuar conversa</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Controla se o bot continua ativo ou entrega para o time humano.
                  </p>
                  {profile.handoff_policy === "ignore" && (
                    <p className="text-xs text-amber-600 dark:text-amber-400">
                      Aviso: &ldquo;ignore&rdquo; impede handoff e o bot continuará respondendo
                      mesmo se o lead pedir humano.
                    </p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label>Texto personalizado de handoff</Label>
                  <Textarea
                    value={profile.handoff_custom_text ?? ""}
                    placeholder="Ex: Vou te conectar com alguém do time agora. Só um instante."
                    onChange={(e) =>
                      setProfile((p) => ({ ...p, handoff_custom_text: e.target.value }))
                    }
                    rows={3}
                  />
                  <p className="text-xs text-muted-foreground">
                    Se preenchido, substitui a mensagem padrão do handoff.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Prioridades do atendimento</CardTitle>
              <CardDescription>Defina prioridades operacionais em formato de bullets.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Textarea
                value={profile.goals}
                placeholder="Use bullets. Ex.:
- Confirmar orçamento antes de sugerir horário
- Coletar os 3 dados obrigatórios"
                onChange={(e) => setProfile((p) => ({ ...p, goals: e.target.value }))}
                rows={4}
              />
              <div className="flex flex-wrap gap-2">
                {goalSuggestions.map((goal) => (
                  <Button
                    key={goal}
                    variant="secondary"
                    size="sm"
                    type="button"
                    onClick={() =>
                      setProfile((p) => ({
                        ...p,
                        goals: p.goals.includes(goal)
                          ? p.goals
                          : `${p.goals ? `${p.goals}
` : ""}${`- ${goal}`}`,
                      }))
                    }
                  >
                    {goal}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Instruções extras</CardTitle>
              <CardDescription>Diretrizes adicionais para o agente.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Textarea
                value={profile.custom_instructions || ""}
                placeholder="Ex.: Sempre responder em português do Brasil e sugerir próximos passos claros."
                onChange={(e) =>
                  setProfile((p) => ({ ...p, custom_instructions: e.target.value }))
                }
                rows={4}
              />
              <div className="text-xs text-muted-foreground text-right">
                {(profile.custom_instructions || "").length} caracteres
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>WhatsApp</CardTitle>
              <CardDescription>Conecte seu número via QR Code para o agente usar.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant={whatsappBadgeVariant}>{whatsappStatusLabel}</Badge>
                {whatsappStatus?.phone_e164 && (
                  <span className="text-sm text-muted-foreground">
                    Telefone: <strong>{whatsappStatus.phone_e164}</strong>
                  </span>
                )}
                {whatsappStatus?.last_updated && (
                  <span className="text-xs text-muted-foreground">
                    Última atualização: {formatDate(whatsappStatus.last_updated)}
                  </span>
                )}
              </div>

              {whatsappError && (
                <Alert variant="destructive">
                  <AlertTitle>Falha na conexão</AlertTitle>
                  <AlertDescription>{whatsappError}</AlertDescription>
                </Alert>
              )}

              {!isWhatsappConnected && whatsappQr?.value && (
                <div className="rounded-md border p-4 space-y-3">
                  <div className="text-sm text-muted-foreground">
                    {whatsappPhase === "connecting" ? "Aguardando scan..." : "Escaneie o QR com o WhatsApp."}
                  </div>
                  {qrIsImage && (
                    <img
                      src={
                        whatsappQr.value.startsWith("data:image/")
                          ? whatsappQr.value
                          : whatsappQr.kind === "url"
                          ? whatsappQr.value
                          : `data:image/png;base64,${whatsappQr.value}`
                      }
                      alt="QR Code do WhatsApp"
                      className="h-56 w-56"
                    />
                  )}
                  {!qrIsImage && (
                    <pre className="whitespace-pre-wrap rounded-md bg-muted p-3 text-xs">
                      {whatsappQr.value}
                    </pre>
                  )}
                </div>
              )}

              {isWhatsappConnected && (
                <div className="rounded-md border border-emerald-200 bg-emerald-50/60 p-3 text-sm text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200">
                  Conectado ✅
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <Button onClick={handleWhatsappConnect} disabled={whatsappLoading || whatsappPhase === "connecting" || connectLockRef.current}>
                  {whatsappLoading ? "Conectando..." : "Criar/Conectar WhatsApp"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => handleWhatsappStatus(false)}
                  disabled={whatsappLoading}
                >
                  Atualizar status
                </Button>
                {!isWhatsappConnected && whatsappQr?.value && (
                  <Button
                    variant="secondary"
                    onClick={() => handleWhatsappRefreshQr()}
                    disabled={whatsappLoading}
                  >
                    Gerar novo QR
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Preview</CardTitle>
              <CardDescription>Simulação local de apresentação e resposta.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
                <div className="text-sm font-semibold text-muted-foreground">Apresentação</div>
                <p className="leading-relaxed">{previewText}</p>
              </div>
              <div className="rounded-lg border bg-muted/30 p-4 space-y-2">
                <div className="text-sm font-semibold text-muted-foreground">Resposta exemplo</div>
                <p className="leading-relaxed">{exampleReply}</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="knowledge" className="space-y-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-primary" />
                <h2 className="text-2xl font-semibold">Conhecimento do negócio</h2>
              </div>
              <p className="text-muted-foreground text-sm">
                Base privada do usuário para alimentar o agente.
              </p>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Status:</span>
                {knowledgeStatus}
              </div>
            </div>
            <Button onClick={() => setKnowledgeModalOpen(true)}>
              <FilePlus className="mr-2 h-4 w-4" /> Adicionar conhecimento
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Itens cadastrados</CardTitle>
              <CardDescription>CRUD completo e upload dedicado (sem PDFs).</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingKnowledge ? (
                <p>Carregando conhecimento...</p>
              ) : knowledgeItems.length === 0 ? (
                <div className="flex flex-col items-start gap-2 rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                  <p>Nenhum conhecimento cadastrado ainda.</p>
                  <Button variant="outline" size="sm" onClick={() => setKnowledgeModalOpen(true)}>
                    <FilePlus className="mr-2 h-4 w-4" /> Adicionar
                  </Button>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Título</TableHead>
                        <TableHead>Tipo</TableHead>
                        <TableHead>Atualizado em</TableHead>
                        <TableHead className="text-right">Ações</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {knowledgeItems.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell className="font-medium">{item.title}</TableCell>
                          <TableCell>
                            <Badge variant={item.source_type === "file" ? "outline" : "secondary"}>
                              {item.source_type}
                            </Badge>
                          </TableCell>
                          <TableCell>{formatDate(item.updated_at)}</TableCell>
                          <TableCell className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setViewItem(item)}
                            >
                              Ver
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => openEdit(item)}>
                              <FileEdit className="mr-1 h-4 w-4" /> Editar
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleDeleteItem(item)}
                            >
                              Remover
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="followup" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-primary" />
                Cadência de Follow-up
              </CardTitle>
              <CardDescription>
                Configure os intervalos e horários de envio automático de follow-up.
                Deixe em branco para usar os valores padrão do plano.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-5 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="followup_max_attempts">Máx. tentativas</Label>
                  <Input
                    id="followup_max_attempts"
                    type="number"
                    min={1}
                    max={10}
                    placeholder="Ex: 4"
                    value={profile.followup_max_attempts ?? ""}
                    onChange={(e) =>
                      setProfile((p) => ({
                        ...p,
                        followup_max_attempts: e.target.value ? Number(e.target.value) : null,
                      }))
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    Número total de mensagens enviadas antes de encerrar o follow-up.
                    Padrão: 4 (SDR) / 3 (híbrido).
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="followup_first_offset">Primeiro offset (minutos)</Label>
                  <Input
                    id="followup_first_offset"
                    type="number"
                    min={1}
                    placeholder="Ex: 30"
                    value={profile.followup_first_offset ?? ""}
                    onChange={(e) =>
                      setProfile((p) => ({
                        ...p,
                        followup_first_offset: e.target.value ? Number(e.target.value) : null,
                      }))
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    Minutos após a transição manual até o 1.º envio automático.
                    Padrão: 30 min (SDR) / 120 min (híbrido).
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="followup_cadence">
                  Cadência (minutos entre envios, separados por vírgula)
                </Label>
                <Input
                  id="followup_cadence"
                  placeholder="Ex: 1440, 4320, 10080"
                  value={cadenceStr}
                  onChange={(e) => {
                    setCadenceStr(e.target.value);
                    setCadenceError(null);
                  }}
                />
                {cadenceError && (
                  <p className="text-xs text-destructive">{cadenceError}</p>
                )}
                <p className="text-xs text-muted-foreground">
                  Intervalo entre cada tentativa em minutos. Deve ter{" "}
                  <strong>máx. tentativas − 1</strong> elemento(s).
                  Sugestões: SDR — 1440, 4320, 10080 | Híbrido — 1440, 2880 | Carrinho — 120, 1440.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="followup_allowed_hours" className="flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" /> Horário permitido (UTC)
                </Label>
                <Input
                  id="followup_allowed_hours"
                  placeholder="Ex: 09:00-18:00"
                  value={profile.followup_allowed_hours ?? ""}
                  onChange={(e) =>
                    setProfile((p) => ({ ...p, followup_allowed_hours: e.target.value }))
                  }
                />
                <p className="text-xs text-muted-foreground">
                  Formato <strong>HH:MM-HH:MM</strong> em UTC. Fora desta janela o follow-up é
                  adiado para o início do próximo período. Deixe vazio para enviar a qualquer hora.
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Seção 4 — Apresentação e agendamento (Tarefa 4.2) */}
        <TabsContent value="apresentacao" className="space-y-4">
          {agentModelUi === "direto_autonomo" ? (
            <Card className="opacity-60">
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground text-center">
                  Não aplicável — Agent 2 não realiza agendamentos.
                </p>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Lembretes de reunião */}
              <Card>
                <CardHeader>
                  <CardTitle>Lembretes de reunião</CardTitle>
                  <CardDescription>
                    Mensagens automáticas enviadas antes do horário agendado.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Label>
                        <code className="text-xs">appointment_reminder_offsets</code>
                      </Label>
                      <Badge variant="secondary">
                        -{reminderHour1}h · -{reminderHour2}h
                      </Badge>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-1">
                        <Label htmlFor="reminder_hour_1">1.º lembrete — horas antes</Label>
                        <Input
                          id="reminder_hour_1"
                          type="number"
                          min={1}
                          placeholder="24"
                          value={reminderHour1}
                          onChange={(e) => setReminderHour1(e.target.value)}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="reminder_hour_2">2.º lembrete — horas antes</Label>
                        <Input
                          id="reminder_hour_2"
                          type="number"
                          min={1}
                          placeholder={agentModelUi === "hibrido_agendador" ? "2" : "1"}
                          value={reminderHour2}
                          onChange={(e) => setReminderHour2(e.target.value)}
                        />
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Default Agent 1: 24h e 1h · Agent 3: 24h e 2h.
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* Dossiê pré-reunião */}
              <Card>
                <CardHeader>
                  <CardTitle>Dossiê pré-reunião</CardTitle>
                  <CardDescription>
                    Briefing automático enviado ao operador antes da reunião.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Label>
                        <code className="text-xs">briefing_enabled</code>
                      </Label>
                      <p className="text-xs text-muted-foreground">
                        Ativar envio automático do dossiê antes da reunião.
                      </p>
                    </div>
                    <Switch
                      checked={profile.briefing_enabled ?? true}
                      onCheckedChange={(v) => setProfile((p) => ({ ...p, briefing_enabled: v }))}
                    />
                  </div>

                  {profile.briefing_enabled && (
                    <>
                      <div className="space-y-2">
                        <Label htmlFor="briefing_channel">
                          <code className="text-xs">briefing_channel</code>
                        </Label>
                        <Select
                          value={profile.briefing_channel ?? "whatsapp"}
                          onValueChange={(v) =>
                            setProfile((p) => ({ ...p, briefing_channel: v as "whatsapp" | "internal" }))
                          }
                        >
                          <SelectTrigger id="briefing_channel">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="whatsapp">WhatsApp</SelectItem>
                            <SelectItem value="internal">Notificação interna</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="briefing_lead_time">
                          <code className="text-xs">briefing_lead_time</code> — horas antes da reunião
                        </Label>
                        <Input
                          id="briefing_lead_time"
                          type="number"
                          min={1}
                          placeholder="2"
                          value={profile.briefing_lead_time ?? ""}
                          onChange={(e) =>
                            setProfile((p) => ({
                              ...p,
                              briefing_lead_time: e.target.value ? Number(e.target.value) : null,
                            }))
                          }
                        />
                      </div>

                      {(profile.briefing_channel ?? "whatsapp") === "whatsapp" && (
                        <div className="space-y-2">
                          <Label htmlFor="operator_whatsapp">
                            <code className="text-xs">operator_whatsapp</code>
                            {profile.briefing_enabled && !(profile.operator_whatsapp?.trim()) ? (
                              <Badge className="ml-2" variant="destructive">Crítico — número não configurado</Badge>
                            ) : profile.operator_whatsapp?.trim() ? (
                              <Badge className="ml-2" variant="default">Configurado</Badge>
                            ) : null}
                          </Label>
                          <Input
                            id="operator_whatsapp"
                            type="tel"
                            placeholder="+55 11 99999-9999"
                            value={profile.operator_whatsapp ?? ""}
                            onChange={(e) =>
                              setProfile((p) => ({ ...p, operator_whatsapp: e.target.value }))
                            }
                          />
                          <p className="text-xs text-muted-foreground">
                            Número do operador que receberá o dossiê pelo WhatsApp.
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Integração de calendário */}
              <Card>
                <CardHeader>
                  <CardTitle>Integração de calendário</CardTitle>
                  <CardDescription>
                    Sincronize reuniões agendadas com seu calendário.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="calendar_integration">
                      <code className="text-xs">calendar_integration</code>
                      {profile.calendar_integration && profile.calendar_integration !== "none" ? (
                        <Badge className="ml-2" variant="default">Integrado</Badge>
                      ) : (
                        <Badge className="ml-2" variant="secondary">Não configurado</Badge>
                      )}
                    </Label>
                    <div className="flex gap-2">
                      <Select
                        value={profile.calendar_integration ?? "none"}
                        onValueChange={(v) =>
                          setProfile((p) => ({
                            ...p,
                            calendar_integration: v as "none" | "google_calendar" | "calendly",
                          }))
                        }
                      >
                        <SelectTrigger id="calendar_integration" className="flex-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">Nenhum</SelectItem>
                          <SelectItem value="google_calendar">Google Calendar</SelectItem>
                          <SelectItem value="calendly">Calendly</SelectItem>
                        </SelectContent>
                      </Select>
                      {profile.calendar_integration && profile.calendar_integration !== "none" && (
                        <Button variant="outline" type="button" disabled>
                          Conectar
                        </Button>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Integração OAuth — em breve.
                    </p>
                  </div>
                </CardContent>
              </Card>

              {/* Sinais de compra — apenas Agent 1 */}
              {agentModelUi === "agendador_com_humano" && (
                <Card>
                  <CardHeader>
                    <CardTitle>Sinais de compra</CardTitle>
                    <CardDescription>
                      Palavras-chave que indicam intenção de contratar. O bot inclui o link de checkout automaticamente ao detectar.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Label htmlFor="buying_signal_keywords">
                        <code className="text-xs">buying_signal_keywords</code>
                      </Label>
                      <Badge variant={buyingSignalStr.trim() ? "default" : "secondary"}>
                        {buyingSignalStr.trim()
                          ? `${buyingSignalStr.split("\n").filter((l) => l.trim()).length} palavras`
                          : "Usando defaults do template"}
                      </Badge>
                    </div>
                    <Textarea
                      id="buying_signal_keywords"
                      placeholder={"quanto custa\nqual o valor\ncomo assino\naceita cartão"}
                      rows={6}
                      value={buyingSignalStr}
                      onChange={(e) => setBuyingSignalStr(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">
                      Uma keyword por linha. Deixe em branco para usar os defaults do template.
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      type="button"
                      onClick={() =>
                        setBuyingSignalStr(
                          [
                            "quanto custa",
                            "qual o valor",
                            "como assino",
                            "qual o contrato",
                            "como faço para contratar",
                            "aceita cartão",
                            "tem parcelamento",
                            "quando começa",
                            "qual o prazo",
                            "me manda a proposta",
                          ].join("\n")
                        )
                      }
                    >
                      Usar defaults do template
                    </Button>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>

        {/* Seção 5 — Oferta e Pagamento (Tarefa 3.6 / 4.3) */}
        <TabsContent value="oferta" className="space-y-4">
          {agentModelUi !== "direto_autonomo" ? (
            <Card className="opacity-60">
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground text-center">
                  Não aplicável ao seu tipo de agente. Esta seção é exclusiva do Agent 2 (Closer Autônomo).
                </p>
              </CardContent>
            </Card>
          ) : (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Mídia do Pitch</CardTitle>
                  <CardDescription>
                    Imagem, vídeo ou áudio enviado automaticamente antes do texto do pitch.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="offer_media_url">
                      URL da mídia
                      {profile.offer_pack?.media_url ? (
                        <Badge className="ml-2" variant="default">Configurado</Badge>
                      ) : (
                        <Badge className="ml-2" variant="secondary">Não configurado</Badge>
                      )}
                    </Label>
                    <Input
                      id="offer_media_url"
                      type="url"
                      placeholder="https://exemplo.com/imagem-produto.jpg"
                      value={profile.offer_pack?.media_url ?? ""}
                      onChange={(e) =>
                        setProfile((p) => ({
                          ...p,
                          offer_pack: { ...(p.offer_pack || {}), media_url: e.target.value || null },
                        }))
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      URL pública acessível. Suporta imagem (JPG, PNG), vídeo (MP4, até 16 MB) e áudio (MP3, OGG).
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="offer_media_type">Tipo de mídia</Label>
                    <Select
                      value={profile.offer_pack?.media_type ?? "image"}
                      onValueChange={(v) =>
                        setProfile((p) => ({
                          ...p,
                          offer_pack: {
                            ...(p.offer_pack || {}),
                            media_type: v as "image" | "video" | "audio",
                          },
                        }))
                      }
                    >
                      <SelectTrigger id="offer_media_type">
                        <SelectValue placeholder="Selecione o tipo" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="image">Imagem</SelectItem>
                        <SelectItem value="video">Vídeo</SelectItem>
                        <SelectItem value="audio">Áudio</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Detalhes da Oferta</CardTitle>
                  <CardDescription>
                    Preço âncora e garantia exibidos no pitch do Agent 2.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="anchor_price">Preço âncora (valor cheio)</Label>
                    <Input
                      id="anchor_price"
                      placeholder="R$ 997"
                      value={profile.offer_pack?.anchor_price ?? ""}
                      onChange={(e) =>
                        setProfile((p) => ({
                          ...p,
                          offer_pack: { ...(p.offer_pack || {}), anchor_price: e.target.value || null },
                        }))
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      Usado no pitch como "De R$997 por apenas R$X". Deixe vazio para não usar preço âncora.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="guarantee_text">Texto da garantia</Label>
                    <Textarea
                      id="guarantee_text"
                      placeholder="7 dias de garantia incondicional"
                      rows={2}
                      value={profile.offer_pack?.guarantee_text ?? ""}
                      onChange={(e) =>
                        setProfile((p) => ({
                          ...p,
                          offer_pack: { ...(p.offer_pack || {}), guarantee_text: e.target.value || null },
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="upsell_message">Mensagem de upsell pós-compra</Label>
                    <Textarea
                      id="upsell_message"
                      placeholder="Parabéns pela sua decisão! Tenho uma oferta especial para complementar..."
                      rows={3}
                      value={profile.offer_pack?.upsell_message ?? ""}
                      onChange={(e) =>
                        setProfile((p) => ({
                          ...p,
                          offer_pack: { ...(p.offer_pack || {}), upsell_message: e.target.value || null },
                        }))
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      Enviada automaticamente após confirmação do pagamento pelo webhook.
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Gateway de Pagamento</CardTitle>
                  <CardDescription>
                    Configure o gateway para receber notificações de pagamento confirmado.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="payment_gateway">
                      Gateway
                      {profile.payment_gateway ? (
                        <Badge className="ml-2" variant="default">Configurado</Badge>
                      ) : (
                        <Badge className="ml-2" variant="destructive">Crítico — não configurado</Badge>
                      )}
                    </Label>
                    <Select
                      value={profile.payment_gateway ?? ""}
                      onValueChange={(v) =>
                        setProfile((p) => ({
                          ...p,
                          payment_gateway: v as AiProfilePayload["payment_gateway"] || null,
                        }))
                      }
                    >
                      <SelectTrigger id="payment_gateway">
                        <SelectValue placeholder="Selecione o gateway" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="hotmart">Hotmart</SelectItem>
                        <SelectItem value="kiwify">Kiwify</SelectItem>
                        <SelectItem value="stripe">Stripe</SelectItem>
                        <SelectItem value="generico">Genérico</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Sem gateway configurado, o fechamento automático não funciona.
                    </p>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={knowledgeModalOpen} onOpenChange={setKnowledgeModalOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>Adicionar conhecimento</DialogTitle>
          </DialogHeader>
          <Tabs value={knowledgeTab} onValueChange={setKnowledgeTab}>
            <TabsList>
              <TabsTrigger value="manual">Texto livre</TabsTrigger>
              <TabsTrigger value="upload">Upload (.txt/.csv/.xlsx)</TabsTrigger>
            </TabsList>
            <TabsContent value="manual" className="space-y-3">
              <div className="space-y-2">
                <Label>Título</Label>
                <Input
                  value={manualTitle}
                  onChange={(e) => setManualTitle(e.target.value)}
                  placeholder="Ex.: Tabela de preços"
                />
              </div>
              <div className="space-y-2">
                <Label>Conteúdo</Label>
                <Textarea
                  value={manualContent}
                  onChange={(e) => setManualContent(e.target.value)}
                  placeholder="Inclua regras, objeções, horários, etc."
                  rows={5}
                />
                <div className="text-xs text-muted-foreground text-right">
                  {manualContent.length} caracteres
                </div>
              </div>
              <DialogFooter>
                <Button onClick={handleCreateManual} disabled={uploading}>
                  {uploading ? "Salvando..." : "Salvar"}
                </Button>
              </DialogFooter>
            </TabsContent>
            <TabsContent value="upload" className="space-y-3">
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                <p>Envie .txt, .csv ou .xlsx. PDF não é suportado no MVP.</p>
              </div>
              <Input
                type="file"
                accept={allowedExtensions.join(",")}
                onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
              />
              {selectedFile && (
                <div className="text-sm text-muted-foreground">
                  Arquivo: {selectedFile.name}
                </div>
              )}
              <DialogFooter>
                <Button onClick={handleUploadFile} disabled={uploading}>
                  <Upload className="mr-2 h-4 w-4" />
                  {uploading ? "Enviando..." : "Enviar"}
                </Button>
              </DialogFooter>
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>

      <Dialog open={!!editingItem} onOpenChange={(open) => !open && setEditingItem(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Editar item</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Título</Label>
              <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Conteúdo</Label>
              <Textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                rows={6}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingItem(null)}>
              Cancelar
            </Button>
            <Button onClick={handleEditSave}>Salvar alterações</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!viewItem} onOpenChange={(open) => !open && setViewItem(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{viewItem?.title}</DialogTitle>
            <p className="text-sm text-muted-foreground">
              {viewItem?.source_type === "file" ? "Arquivo" : "Manual"} · Atualizado em {formatDate(viewItem?.updated_at)}
            </p>
          </DialogHeader>
          <div className="rounded-md border bg-muted/40 p-3 text-sm whitespace-pre-wrap">
            {viewItem?.content_text}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewItem(null)}>
              Fechar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
