import { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { format, parseISO, differenceInSeconds } from "date-fns";
import { ptBR } from "date-fns/locale";
import { api, type FollowUpContract } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  RefreshCw,
  ImageIcon,
  FileText,
  Mic,
  Video,
  Upload,
  ChevronRight,
} from "lucide-react";

// ─── Cores ────────────────────────────────────────────────────────────────────

const TEMP_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  hot:          { label: "Quente",   color: "#F5694E", bg: "rgba(245,105,78,0.12)",  border: "rgba(245,105,78,0.35)"  },
  warm:         { label: "Morno",    color: "#F5A623", bg: "rgba(245,166,35,0.12)",  border: "rgba(245,166,35,0.35)"  },
  cold:         { label: "Frio",     color: "#5B9CF6", bg: "rgba(91,156,246,0.12)",  border: "rgba(91,156,246,0.35)"  },
  cart_recovery:{ label: "Carrinho", color: "#52C4A0", bg: "rgba(82,196,160,0.12)",  border: "rgba(82,196,160,0.35)"  },
  lost:         { label: "Perdido",  color: "#6B6E84", bg: "rgba(107,110,132,0.12)", border: "rgba(107,110,132,0.3)"  },
};
function getTempCfg(key: string | null | undefined) {
  return TEMP_CONFIG[key ?? ""] ?? TEMP_CONFIG["cold"];
}

// ─── Timer regressivo ─────────────────────────────────────────────────────────

function useCountdown(targetIso: string | null | undefined) {
  const [secs, setSecs] = useState<number | null>(null);

  useEffect(() => {
    if (!targetIso) { setSecs(null); return; }
    const update = () => {
      try {
        const diff = differenceInSeconds(parseISO(targetIso), new Date());
        setSecs(Math.max(0, diff));
      } catch {
        setSecs(null);
      }
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [targetIso]);

  if (secs === null) return null;
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// ─── Sequência de tentativas ──────────────────────────────────────────────────

function SequenceMap({ contract }: { contract: FollowUpContract | null }) {
  if (!contract) return <p className="text-xs text-muted-foreground">Contrato indisponível.</p>;

  const attempts = contract.attempts ?? 0;
  const max = contract.max_attempts ?? 4;
  const variant = contract.followup_variant ?? "—";

  const labels = [
    "Urgência inicial",
    "Facilitação",
    "Remoção de objeção",
    "Última tentativa",
    "Reengajamento",
  ];

  return (
    <div>
      <p
        className="font-mono text-[9px] tracking-[2.5px] uppercase mb-3"
        style={{ color: "#6b6e84" }}
      >
        Cadência — {variant}
      </p>
      <div className="flex flex-col">
        {Array.from({ length: max }, (_, i) => {
          const isDone = i < attempts;
          const isCurrent = i === attempts;
          const isFuture = i > attempts;
          return (
            <div key={i} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div
                  className="w-[9px] h-[9px] rounded-full flex-shrink-0 mt-[3px]"
                  style={
                    isDone
                      ? { background: "#4ade80" }
                      : isCurrent
                      ? { background: "#7c6af7", boxShadow: "0 0 0 3px rgba(124,106,247,.25)" }
                      : { background: "#21222e", border: "1.5px solid rgba(255,255,255,0.12)" }
                  }
                />
                {i < max - 1 && (
                  <div
                    className="w-px flex-1 min-h-[18px] my-[3px]"
                    style={
                      isDone
                        ? { background: "rgba(255,255,255,0.12)" }
                        : { borderLeft: "1px dashed rgba(255,255,255,0.12)" }
                    }
                  />
                )}
              </div>
              <div className="flex-1 pb-[14px]">
                <p className="font-mono text-[9px] tracking-[0.5px] text-muted-foreground mb-[1px]">
                  Tentativa {i + 1}
                </p>
                <p
                  className="text-xs font-medium"
                  style={{ color: isCurrent ? "#e8eaf0" : "#9295ab" }}
                >
                  {labels[i] ?? `Tentativa ${i + 1}`}
                  {isCurrent && (
                    <span className="ml-2 text-[10px]" style={{ color: "#7c6af7" }}>
                      ✦ você está aqui
                    </span>
                  )}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      <div
        className="rounded-lg p-3 mt-2 text-xs"
        style={{ background: "#13141a", border: "1px solid rgba(255,255,255,0.06)" }}
      >
        <p
          className="font-mono text-[9px] tracking-[2px] uppercase mb-2"
          style={{ color: "#6b6e84" }}
        >
          Configurado no AI Profile
        </p>
        <div className="flex justify-between py-[3px]">
          <span style={{ color: "#9295ab" }}>Máx. tentativas</span>
          <span className="font-medium">{max}</span>
        </div>
        <div className="flex justify-between py-[3px]">
          <span style={{ color: "#9295ab" }}>Variant</span>
          <span className="font-medium">{variant}</span>
        </div>
        <div className="flex justify-between py-[3px]">
          <span style={{ color: "#9295ab" }}>Tentativas feitas</span>
          <span className="font-medium">{attempts}</span>
        </div>
      </div>
    </div>
  );
}

// ─── Painel de contexto ───────────────────────────────────────────────────────

function ContextPanel({ contract }: { contract: FollowUpContract | null }) {
  if (!contract) return <p className="text-xs text-muted-foreground">Contrato indisponível.</p>;
  const temp = contract.temperature ?? "—";
  const cfg = getTempCfg(temp);

  const rows: Array<{ key: string; val: string | null | undefined }> = [
    { key: "Temperatura", val: temp !== "—" ? cfg.label : "—" },
    { key: "Objetivo", val: contract.followup_goal ?? "—" },
    { key: "Reunião ocorreu", val: contract.meeting_or_session_happened === "yes" ? "Sim" : contract.meeting_or_session_happened ? "Não" : "—" },
    { key: "Resultado", val: contract.outcome ?? "—" },
    { key: "Variant", val: contract.followup_variant ?? "—" },
    { key: "Origem", val: contract.trigger === "auto_inactivity" ? "Automático (inatividade)" : "Manual" },
  ];

  return (
    <div>
      <p
        className="font-mono text-[9px] tracking-[2.5px] uppercase mb-3"
        style={{ color: "#6b6e84" }}
      >
        Dados do follow-up
      </p>
      {rows.map((r) => (
        <div key={r.key} className="flex justify-between py-[4px] text-xs border-b" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
          <span style={{ color: "#9295ab" }}>{r.key}</span>
          <span
            className="font-medium text-right"
            style={r.key === "Temperatura" && temp !== "—" ? { color: cfg.color } : undefined}
          >
            {r.val ?? "—"}
          </span>
        </div>
      ))}

      {contract.operator_note && (
        <div
          className="mt-4 rounded-lg p-3 text-xs leading-relaxed"
          style={{
            background: "#1a1b24",
            border: "1px solid rgba(255,255,255,0.06)",
            borderLeft: "3px solid #F5A623",
          }}
        >
          <p
            className="font-mono text-[9px] tracking-[1px] uppercase mb-1"
            style={{ color: "#F5A623" }}
          >
            Nota do operador
          </p>
          <p style={{ color: "#9295ab" }}>{contract.operator_note}</p>
        </div>
      )}
    </div>
  );
}

// ─── Preview WhatsApp ─────────────────────────────────────────────────────────

function PhonePreview({
  contactName,
  companyName,
  text,
}: {
  contactName: string | null;
  companyName: string;
  text: string;
}) {
  const name = contactName || companyName;
  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");

  const preview = text.length > 120 ? text.slice(0, 120) + "…" : text;
  const timeStr = format(new Date(), "HH:mm");

  return (
    <div>
      <p className="text-[11px] text-center mb-2" style={{ color: "#6b6e84" }}>
        Como aparecerá no WhatsApp do lead
      </p>
      <div
        className="rounded-xl overflow-hidden"
        style={{ border: "1px solid rgba(255,255,255,0.06)", background: "#1a1b24" }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-2 px-3 py-2 border-b"
          style={{ background: "#21222e", borderColor: "rgba(255,255,255,0.06)" }}
        >
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold flex-shrink-0"
            style={{ background: "rgba(245,105,78,.2)", color: "#F5694E" }}
          >
            {initials}
          </div>
          <div>
            <p className="text-xs font-medium">{name}</p>
            <p className="text-[10px]" style={{ color: "#6b6e84" }}>online</p>
          </div>
        </div>
        {/* Body */}
        <div className="p-3 min-h-[120px] flex flex-col gap-2">
          {/* Preview bubble (dashed = not sent yet) */}
          <div
            className="max-w-[85%] self-end rounded-[10px] rounded-br-[3px] px-3 py-2 text-xs leading-[1.55]"
            style={{
              background: "rgba(124,106,247,0.12)",
              border: "1px dashed rgba(124,106,247,0.35)",
              color: "#e8eaf0",
            }}
          >
            <p style={{ whiteSpace: "pre-wrap" }}>{preview || "(mensagem vazia)"}</p>
            <p className="text-[9px] mt-1 text-right" style={{ color: "rgba(124,106,247,.8)" }}>
              prévia · {timeStr}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Painel direito com abas ──────────────────────────────────────────────────

type PanelTab = "preview" | "sequence" | "context";

function RightPanel({
  contract,
  contactName,
  companyName,
  messageText,
}: {
  contract: FollowUpContract | null;
  contactName: string | null;
  companyName: string;
  messageText: string;
}) {
  const [tab, setTab] = useState<PanelTab>("preview");

  const tabs: Array<{ id: PanelTab; label: string }> = [
    { id: "preview", label: "Prévia" },
    { id: "sequence", label: "Sequência" },
    { id: "context", label: "Contexto" },
  ];

  return (
    <div
      className="flex flex-col h-full overflow-y-auto"
      style={{ padding: "24px 20px 80px", background: "#13141a" }}
    >
      {/* Tab bar */}
      <div
        className="flex gap-0 rounded-lg mb-4 p-[3px]"
        style={{ background: "#1a1b24" }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "flex-1 text-[11px] py-[5px] px-[6px] rounded-md transition-colors",
              tab === t.id
                ? "text-foreground font-medium"
                : "text-muted-foreground hover:text-foreground"
            )}
            style={tab === t.id ? { background: "#13141a" } : undefined}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "preview" && (
        <PhonePreview contactName={contactName} companyName={companyName} text={messageText} />
      )}
      {tab === "sequence" && <SequenceMap contract={contract} />}
      {tab === "context" && <ContextPanel contract={contract} />}
    </div>
  );
}

// ─── Seção de mídia ───────────────────────────────────────────────────────────

type MediaType = "image" | "doc" | "audio" | "video" | null;

const MEDIA_OPTS: Array<{ type: Exclude<MediaType, null>; icon: React.ReactNode; label: string; accept: string; hint: string }> = [
  { type: "image",  icon: <ImageIcon className="w-5 h-5" />, label: "Imagem",    accept: "image/png,image/jpeg,image/gif",                          hint: "PNG, JPG ou GIF · máx 16MB"     },
  { type: "doc",    icon: <FileText  className="w-5 h-5" />, label: "Documento", accept: ".pdf,.doc,.docx",                                         hint: "PDF, DOC, DOCX · máx 100MB"    },
  { type: "audio",  icon: <Mic       className="w-5 h-5" />, label: "Áudio",     accept: "audio/mpeg,audio/ogg,audio/mp4",                          hint: "MP3, OGG, M4A · máx 16MB"      },
  { type: "video",  icon: <Video     className="w-5 h-5" />, label: "Vídeo",     accept: "video/mp4,video/quicktime",                               hint: "MP4, MOV · máx 16MB"           },
];

function MediaSection({
  leadId,
  onMediaUploaded,
}: {
  leadId: number;
  onMediaUploaded: (url: string, type: string) => void;
}) {
  const [selected, setSelected] = useState<MediaType>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function handleTypeClick(type: Exclude<MediaType, null>) {
    if (selected === type) { setSelected(null); return; }
    setSelected(type);
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const res = await api.followUps.uploadMedia(leadId, file);
      onMediaUploaded(res.media_url, selected ?? "image");
      toast.success("Mídia enviada com sucesso");
    } catch {
      toast.error("Falha ao enviar mídia");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const currentOpt = MEDIA_OPTS.find((o) => o.type === selected);

  return (
    <div>
      <p className="text-sm font-medium mb-3">
        Adicionar mídia{" "}
        <span className="text-xs font-normal text-muted-foreground">
          opcional — enviada junto com a mensagem
        </span>
      </p>
      <div className="grid grid-cols-4 gap-2 mb-3">
        {MEDIA_OPTS.map((opt) => (
          <button
            key={opt.type}
            onClick={() => handleTypeClick(opt.type)}
            className={cn(
              "flex flex-col items-center gap-1 rounded-lg py-3 px-2 border text-center transition-colors",
              selected === opt.type
                ? "border-violet-500/40 bg-violet-500/10 text-violet-400"
                : "border-border bg-card hover:bg-muted/50 text-muted-foreground hover:text-foreground"
            )}
          >
            {opt.icon}
            <span className="text-[11px]">{opt.label}</span>
          </button>
        ))}
      </div>

      {selected && currentOpt && (
        <div
          onClick={() => fileRef.current?.click()}
          className={cn(
            "rounded-lg border border-dashed p-6 text-center cursor-pointer transition-colors",
            uploading ? "opacity-60 pointer-events-none" : "hover:border-violet-500/40 hover:bg-violet-500/5"
          )}
          style={{ borderColor: "rgba(255,255,255,0.12)" }}
        >
          <Upload className="w-6 h-6 mx-auto mb-2 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            {uploading ? "Enviando…" : "Arraste o arquivo aqui ou clique para selecionar"}
          </p>
          <p className="text-[11px] text-muted-foreground mt-1">{currentOpt.hint}</p>
          <input
            ref={fileRef}
            type="file"
            accept={currentOpt.accept}
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
      )}
    </div>
  );
}

// ─── Modal de confirmação ─────────────────────────────────────────────────────

function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  confirmVariant,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  confirmVariant: "destructive" | "default";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div
        className="rounded-xl p-6 w-full max-w-sm shadow-2xl"
        style={{ background: "#13141a", border: "1px solid rgba(255,255,255,0.1)" }}
      >
        <h3 className="text-sm font-semibold mb-2">{title}</h3>
        <p className="text-xs text-muted-foreground mb-5">{description}</p>
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancelar
          </Button>
          <Button
            size="sm"
            variant={confirmVariant}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Variáveis dinâmicas ───────────────────────────────────────────────────────

const VARS = [
  { label: "{nome_lead}",      value: "{{nome_lead}}"      },
  { label: "{nome_empresa}",   value: "{{nome_empresa}}"   },
  { label: "{valor_proposta}", value: "{{valor_proposta}}"  },
  { label: "{dor_principal}",  value: "{{dor_principal}}"  },
  { label: "{nome_vendedor}",  value: "{{nome_vendedor}}"  },
  { label: "{link_proposta}",  value: "{{link_proposta}}"  },
];

// ─── Página principal ─────────────────────────────────────────────────────────

export default function FollowUpEdit() {
  const { leadId } = useParams<{ leadId: string }>();
  const navigate = useNavigate();
  const id = Number(leadId);

  // Load
  const { data, isLoading, isError } = useQuery({
    queryKey: ["followup-edit", id],
    queryFn: () => api.followUps.getScheduledMessage(id),
    enabled: !isNaN(id),
    staleTime: 30_000,
  });

  // Textarea state
  const [messageText, setMessageText] = useState("");
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [mediaType, setMediaType] = useState<string | null>(null);
  const [charWarn, setCharWarn] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Confirm dialogs
  const [confirmOpen, setConfirmOpen] = useState<null | "cancel" | "pause" | "send-now">(null);

  // Populate textarea once loaded
  useEffect(() => {
    if (!data) return;
    const saved = data.scheduled_message;
    if (saved && "content" in saved && saved.content) {
      setMessageText(saved.content);
      setMediaUrl(saved.media_url ?? null);
      setMediaType(saved.media_type ?? null);
    }
  }, [data]);

  function handleTextChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setMessageText(val);
    setCharWarn(val.length > 3500);
  }

  function insertVar(v: string) {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const next = messageText.slice(0, start) + v + messageText.slice(end);
    setMessageText(next);
    setTimeout(() => {
      ta.focus();
      ta.selectionStart = ta.selectionEnd = start + v.length;
    }, 0);
  }

  // Timer
  const countdown = useCountdown(data?.next_followup_at);

  // Mutations
  const saveMutation = useMutation({
    mutationFn: () =>
      api.followUps.saveScheduledMessage(id, {
        content: messageText,
        media_url: mediaUrl,
        media_type: mediaType,
      }),
    onSuccess: () => toast.success("Mensagem salva"),
    onError: () => toast.error("Falha ao salvar"),
  });

  const regenMutation = useMutation({
    mutationFn: () => api.followUps.regenerate(id),
    onSuccess: (res) => {
      setMessageText(res.content);
      toast.success("Mensagem regerada pelo LLM");
    },
    onError: () => toast.error("Falha ao regerar mensagem"),
  });

  const sendNowMutation = useMutation({
    mutationFn: () =>
      api.followUps.sendNow(id, { content: messageText, media_url: mediaUrl, media_type: mediaType }),
    onSuccess: () => {
      toast.success("Mensagem enviada via WhatsApp");
      navigate("/follow-ups");
    },
    onError: () => toast.error("Falha ao enviar mensagem"),
  });

  const pauseMutation = useMutation({
    mutationFn: () => api.followUps.pause(id),
    onSuccess: () => {
      toast.success("Follow-up pausado");
      navigate("/follow-ups");
    },
    onError: () => toast.error("Falha ao pausar"),
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.followUps.cancel(id),
    onSuccess: () => {
      toast.success("Follow-up cancelado");
      navigate("/follow-ups");
    },
    onError: () => toast.error("Falha ao cancelar"),
  });

  const isBusy =
    saveMutation.isPending ||
    regenMutation.isPending ||
    sendNowMutation.isPending ||
    pauseMutation.isPending ||
    cancelMutation.isPending;

  const contract = data?.contract ?? null;
  const temp = contract?.temperature ?? "warm";
  const tempCfg = getTempCfg(temp);
  const attempts = contract?.attempts ?? 0;
  const maxAttempts = contract?.max_attempts ?? 4;
  const companyName = data?.companyName ?? "";
  const contactName = data?.contactName ?? null;
  const agentType = data?.agent_type ?? null;
  const displayName = contactName || companyName;
  const initials = displayName
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");

  if (isError) {
    return (
      <div className="flex items-center justify-center min-h-screen text-muted-foreground text-sm">
        Erro ao carregar follow-up. <button className="ml-2 underline" onClick={() => navigate("/follow-ups")}>Voltar</button>
      </div>
    );
  }

  return (
    <div
      className="flex flex-col min-h-screen"
      style={{ background: "#0c0d10", color: "#e8eaf0", fontFamily: "'DM Sans', sans-serif" }}
    >
      {/* ── Top nav ── */}
      <nav
        className="h-[54px] flex items-center justify-between px-7 sticky top-0 z-50 border-b"
        style={{ background: "#13141a", borderColor: "rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center gap-4">
          <button
            className="flex items-center gap-1.5 text-xs rounded-lg px-2.5 py-1.5 border transition-colors hover:text-foreground"
            style={{ color: "#9295ab", borderColor: "rgba(255,255,255,0.06)", background: "transparent" }}
            onClick={() => navigate("/follow-ups")}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Central de Follow-ups
          </button>
          <div className="flex items-center gap-1.5 text-xs" style={{ color: "#6b6e84" }}>
            <span style={{ color: "#9295ab" }}>Follow-up</span>
            <ChevronRight className="w-3 h-3" />
            <span style={{ color: "#e8eaf0", fontWeight: 500 }}>
              {isLoading ? "Carregando…" : `${displayName} — Tentativa ${attempts + 1}`}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="text-xs px-3.5 py-1.5 rounded-lg border transition-colors hover:text-foreground"
            style={{ color: "#9295ab", borderColor: "rgba(255,255,255,0.12)", background: "transparent" }}
            onClick={() => navigate(`/`)}
          >
            Ver no Kanban
          </button>
        </div>
      </nav>

      {/* ── Timer banner ── */}
      {data?.next_followup_at && countdown !== null && (
        <div
          className="flex items-center gap-3 px-7 py-2.5 border-b"
          style={{ background: "#13141a", borderColor: "rgba(245,105,78,0.3)" }}
        >
          <span className="relative flex h-[7px] w-[7px] flex-shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-[7px] w-[7px] bg-red-500" />
          </span>
          <p className="text-[13px] flex-1">
            Esta mensagem está <strong>programada para envio</strong> automaticamente em:
          </p>
          <span
            className="font-mono text-sm font-medium min-w-[60px]"
            style={{ color: "#F5694E" }}
          >
            {countdown}
          </span>
          <span className="text-xs underline cursor-pointer" style={{ color: "#9295ab" }}>
            Edite agora ou deixe o LLM enviar como está
          </span>
        </div>
      )}

      {/* ── Main layout ── */}
      <div className="flex flex-1 overflow-hidden" style={{ minHeight: "calc(100vh - 108px)" }}>
        {/* ── Left: editor ── */}
        <div
          className="flex-1 overflow-y-auto px-8 py-7 pb-24 border-r"
          style={{ borderColor: "rgba(255,255,255,0.06)" }}
        >
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-14 rounded-xl" />
              <Skeleton className="h-32 rounded-xl" />
              <Skeleton className="h-8 w-48" />
            </div>
          ) : (
            <>
              {/* Lead context strip */}
              <div
                className="flex items-center gap-3 rounded-xl px-4 py-3 mb-6 border"
                style={{ background: "#13141a", borderColor: "rgba(255,255,255,0.06)" }}
              >
                <div
                  className="w-[38px] h-[38px] rounded-lg flex items-center justify-center text-[13px] font-semibold flex-shrink-0"
                  style={{ background: tempCfg.bg, color: tempCfg.color }}
                >
                  {initials}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{displayName}</p>
                  <p className="text-xs truncate" style={{ color: "#9295ab" }}>
                    {agentType ?? "—"} · {contract?.followup_goal ?? "—"}
                  </p>
                </div>
                <div className="flex gap-1.5 flex-wrap justify-end">
                  {temp && temp !== "—" && (
                    <span
                      className="text-[10px] px-2 py-[3px] rounded font-mono"
                      style={{ color: tempCfg.color, background: tempCfg.bg, border: `1px solid ${tempCfg.border}` }}
                    >
                      {tempCfg.label}
                    </span>
                  )}
                  {agentType && (
                    <span
                      className="text-[10px] px-2 py-[3px] rounded font-mono"
                      style={{ color: "#F0C060", background: "rgba(240,192,96,0.07)", border: "1px solid rgba(240,192,96,0.3)" }}
                    >
                      {agentType.toUpperCase()}
                    </span>
                  )}
                  {contract?.followup_goal && (
                    <span
                      className="text-[10px] px-2 py-[3px] rounded font-mono"
                      style={{ color: "#9295ab", background: "#1a1b24", border: "1px solid rgba(255,255,255,0.12)" }}
                    >
                      {contract.followup_goal}
                    </span>
                  )}
                </div>
              </div>

              {/* Operator note */}
              {contract?.operator_note && (
                <div
                  className="rounded-lg px-3.5 py-2.5 mb-5 text-xs leading-relaxed"
                  style={{
                    background: "#1a1b24",
                    border: "1px solid rgba(255,255,255,0.06)",
                    borderLeft: "3px solid #F5A623",
                    color: "#9295ab",
                  }}
                >
                  <strong
                    className="block mb-1 font-mono text-[9px] tracking-[1px] uppercase"
                    style={{ color: "#F5A623" }}
                  >
                    Nota do operador
                  </strong>
                  {contract.operator_note}
                </div>
              )}

              {/* Editor header */}
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h2 className="text-[17px] font-semibold" style={{ fontFamily: "'Syne', sans-serif" }}>
                    Mensagem — Tentativa {attempts + 1} de {maxAttempts}
                  </h2>
                  <p className="text-xs mt-0.5" style={{ color: "#9295ab" }}>
                    Gerada automaticamente com base no seu AI Profile
                    {temp !== "—" ? ` + temperatura ${tempCfg.label}` : ""}
                  </p>
                </div>
                <button
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors disabled:opacity-60"
                  style={{
                    color: "#7c6af7",
                    background: "rgba(124,106,247,0.12)",
                    border: "1px solid rgba(124,106,247,0.3)",
                    whiteSpace: "nowrap",
                  }}
                  onClick={() => regenMutation.mutate()}
                  disabled={regenMutation.isPending}
                >
                  <RefreshCw className={cn("w-3.5 h-3.5", regenMutation.isPending && "animate-spin")} />
                  {regenMutation.isPending ? "Gerando…" : "Regerar com LLM"}
                </button>
              </div>

              {/* LLM tag */}
              <span
                className="inline-flex items-center gap-1 font-mono text-[9px] tracking-[1.5px] uppercase px-2 py-1 rounded mb-2.5"
                style={{
                  color: "#7c6af7",
                  background: "rgba(124,106,247,0.12)",
                  border: "1px solid rgba(124,106,247,0.3)",
                }}
              >
                ✦ Gerada pelo LLM · Baseada no AI Profile
              </span>

              {/* Textarea */}
              <textarea
                ref={textareaRef}
                className="w-full min-h-[160px] rounded-xl px-4 py-4 text-sm leading-relaxed resize-y transition-colors outline-none focus:ring-1 focus:ring-violet-500/50"
                style={{
                  background: "#13141a",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#e8eaf0",
                  fontFamily: "'DM Sans', sans-serif",
                }}
                placeholder="Escreva ou edite a mensagem de follow-up…"
                value={messageText}
                onChange={handleTextChange}
              />

              {/* Char count */}
              <div className="flex items-center justify-between mt-1.5 mb-5">
                <span
                  className={cn("font-mono text-[10px]", charWarn ? "text-amber-400" : "text-muted-foreground")}
                >
                  {messageText.length} caracteres
                </span>
                <span className="text-[11px] text-muted-foreground">
                  WhatsApp — até ~4000 caracteres recomendados
                </span>
              </div>

              {/* Variable pills */}
              <div className="mb-5">
                <p className="text-[11px] text-muted-foreground mb-2">Inserir variável dinâmica</p>
                <div className="flex flex-wrap gap-1.5">
                  {VARS.map((v) => (
                    <button
                      key={v.value}
                      onClick={() => insertVar(v.value)}
                      className="font-mono text-[11px] px-2.5 py-1 rounded border transition-colors hover:text-violet-400"
                      style={{
                        color: "#9295ab",
                        background: "#1a1b24",
                        borderColor: "rgba(255,255,255,0.12)",
                      }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(124,106,247,0.35)";
                        (e.currentTarget as HTMLButtonElement).style.background = "rgba(124,106,247,0.1)";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(255,255,255,0.12)";
                        (e.currentTarget as HTMLButtonElement).style.background = "#1a1b24";
                      }}
                    >
                      {v.label}
                    </button>
                  ))}
                </div>
              </div>

              <hr style={{ borderColor: "rgba(255,255,255,0.06)", margin: "20px 0" }} />

              {/* Media section */}
              <MediaSection
                leadId={id}
                onMediaUploaded={(url, type) => {
                  setMediaUrl(url);
                  setMediaType(type);
                  toast.info(`Mídia selecionada: ${url.split("/").pop()}`);
                }}
              />

              {mediaUrl && (
                <div
                  className="mt-3 flex items-center gap-2 rounded-lg px-3 py-2 text-xs"
                  style={{ background: "#1a1b24", border: "1px solid rgba(255,255,255,0.08)" }}
                >
                  <span style={{ color: "#9295ab" }}>Mídia anexada:</span>
                  <span className="flex-1 truncate font-mono" style={{ color: "#7c6af7" }}>
                    {mediaUrl.split("/").pop()}
                  </span>
                  <button
                    className="text-muted-foreground hover:text-red-400"
                    onClick={() => { setMediaUrl(null); setMediaType(null); }}
                  >
                    ✕
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* ── Right: context panel ── */}
        <div className="w-[380px] flex-shrink-0 overflow-hidden">
          <RightPanel
            contract={contract}
            contactName={contactName}
            companyName={companyName}
            messageText={messageText}
          />
        </div>
      </div>

      {/* ── Bottom action bar ── */}
      <div
        className="fixed bottom-0 left-0 right-0 z-40 flex items-center gap-2.5 px-8 py-3.5 border-t"
        style={{ background: "#0c0d10", borderColor: "rgba(255,255,255,0.08)" }}
      >
        {/* Danger: cancel */}
        <button
          className="text-[13px] px-5 py-2.5 rounded-[9px] border font-medium transition-colors disabled:opacity-60"
          style={{ color: "#F5694E", background: "rgba(245,105,78,0.08)", borderColor: "rgba(245,105,78,0.3)" }}
          onClick={() => setConfirmOpen("cancel")}
          disabled={isBusy}
        >
          ✕ Cancelar follow-up
        </button>

        <div className="flex-1 flex items-center gap-2 justify-end">
          {/* Pause */}
          <button
            className="text-[13px] px-5 py-2.5 rounded-[9px] border font-medium transition-colors disabled:opacity-60 hover:text-foreground"
            style={{ color: "#9295ab", background: "transparent", borderColor: "rgba(255,255,255,0.12)" }}
            onClick={() => setConfirmOpen("pause")}
            disabled={isBusy}
          >
            ⏸ Pausar follow-up
          </button>

          {/* Save only */}
          <button
            className="text-[13px] px-5 py-2.5 rounded-[9px] border font-medium transition-colors disabled:opacity-60 hover:text-foreground"
            style={{ color: "#9295ab", background: "#1a1b24", borderColor: "rgba(255,255,255,0.12)" }}
            onClick={() => saveMutation.mutate()}
            disabled={isBusy || !messageText.trim()}
          >
            {saveMutation.isPending ? "Salvando…" : "💾 Salvar sem enviar agora"}
          </button>

          {/* Send now */}
          <button
            className="text-[13px] px-5 py-2.5 rounded-[9px] border font-medium transition-colors disabled:opacity-60"
            style={{ color: "#4ade80", background: "rgba(74,222,128,0.1)", borderColor: "rgba(74,222,128,0.3)" }}
            onClick={() => setConfirmOpen("send-now")}
            disabled={isBusy || !messageText.trim()}
          >
            ⚡ Enviar agora
          </button>

          {/* Save and schedule */}
          <button
            className="text-[13px] px-5 py-2.5 rounded-[9px] border font-medium transition-colors disabled:opacity-60 text-white"
            style={{ background: "#7c6af7", borderColor: "#7c6af7" }}
            onClick={() => saveMutation.mutate()}
            disabled={isBusy || !messageText.trim()}
          >
            {saveMutation.isPending ? "Salvando…" : "✓ Salvar e manter agendamento"}
          </button>
        </div>
      </div>

      {/* ── Confirm dialogs ── */}
      <ConfirmDialog
        open={confirmOpen === "cancel"}
        title="Cancelar follow-up?"
        description={`${displayName} não receberá mais mensagens automáticas de follow-up. Esta ação não pode ser desfeita.`}
        confirmLabel="Sim, cancelar"
        confirmVariant="destructive"
        onConfirm={() => { setConfirmOpen(null); cancelMutation.mutate(); }}
        onCancel={() => setConfirmOpen(null)}
      />
      <ConfirmDialog
        open={confirmOpen === "pause"}
        title="Pausar follow-up?"
        description="O follow-up será pausado manualmente. Você poderá retomá-lo a qualquer momento na Central de Follow-ups."
        confirmLabel="Pausar"
        confirmVariant="default"
        onConfirm={() => { setConfirmOpen(null); pauseMutation.mutate(); }}
        onCancel={() => setConfirmOpen(null)}
      />
      <ConfirmDialog
        open={confirmOpen === "send-now"}
        title="Enviar agora?"
        description={`A mensagem será enviada imediatamente para ${displayName} via WhatsApp. A tentativa será contabilizada.`}
        confirmLabel="Enviar agora"
        confirmVariant="default"
        onConfirm={() => { setConfirmOpen(null); sendNowMutation.mutate(); }}
        onCancel={() => setConfirmOpen(null)}
      />
    </div>
  );
}
