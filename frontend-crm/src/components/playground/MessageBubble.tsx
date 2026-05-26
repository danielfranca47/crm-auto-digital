import { useState } from "react";
import {
  Bookmark, BookmarkCheck, ChevronDown, ChevronUp,
  ThumbsDown, Minus, ThumbsUp, Star, Loader2,
  Headphones, ImageIcon, Video, FileText, Mic,
  Clock, Keyboard, Layers, Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { PlaygroundDecisionTrace, PlaygroundPreSendMediaItem } from "@/services/api";

export type RatingValue = "ruim" | "regular" | "boa" | "excelente";

export interface ChatMessage {
  id: string;
  role: "lead" | "bot";
  text: string;
  timestamp: string;
  isAutoMessage?: boolean;
  isPhaseAdvance?: boolean;
  decisionTrace?: PlaygroundDecisionTrace;
  motherRoute?: string | null;
  confidence?: number;
  guardrails?: string[];
  selectedForFeedback: boolean;
  preMediaItems?: PlaygroundPreSendMediaItem[];
  rating?: RatingValue;
  ratingComment?: string;
  ratingPending?: boolean;
  humanizationPreview?: {
    delay_s: number;
    typing_s: number;
    total_parts: number;
  };
}

interface MessageBubbleProps {
  message: ChatMessage;
  onToggleFeedback: (id: string) => void;
  onRate: (id: string, rating: RatingValue, comment: string) => void;
}

// ── MediaCard ─────────────────────────────────────────────────────────────────

const MEDIA_ICONS = {
  audio: Headphones,
  myaudio: Mic,
  ptt: Mic,
  image: ImageIcon,
  video: Video,
  pdf: FileText,
} as const;

const MEDIA_LABELS: Record<string, string> = {
  audio: "Áudio",
  myaudio: "Mensagem de voz",
  ptt: "Mensagem de voz",
  image: "Imagem",
  video: "Vídeo",
  pdf: "Documento",
};

function MediaCard({ type, url }: { type: string; url: string }) {
  const Icon = MEDIA_ICONS[type as keyof typeof MEDIA_ICONS] ?? FileText;
  const label = MEDIA_LABELS[type] ?? type;
  const isSimulated = !url || url === "#";
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted border text-sm mb-1">
      <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
      <span className="text-muted-foreground text-xs">{label} simulado</span>
      {!isSimulated && (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-primary underline ml-auto"
        >
          Ver
        </a>
      )}
    </div>
  );
}

// ── Detecta marcador de mídia do lead ─────────────────────────────────────────

function parseLeadMediaMarker(text: string): string | null {
  const m = text.trim().match(/^\{(áudio|audio|imagem|vídeo|video|documento)\}$/i);
  if (!m) return null;
  const raw = m[1].toLowerCase();
  if (raw === "áudio" || raw === "audio") return "audio";
  if (raw === "imagem") return "image";
  if (raw === "vídeo" || raw === "video") return "video";
  if (raw === "documento") return "pdf";
  return null;
}

// ── RatingRow ─────────────────────────────────────────────────────────────────

const RATING_CONFIG: {
  value: RatingValue;
  label: string;
  icon: typeof ThumbsDown;
  activeClass: string;
}[] = [
  { value: "ruim",      label: "Ruim",      icon: ThumbsDown, activeClass: "text-red-500 bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-800" },
  { value: "regular",   label: "Regular",   icon: Minus,      activeClass: "text-orange-500 bg-orange-50 border-orange-200 dark:bg-orange-950 dark:border-orange-800" },
  { value: "boa",       label: "Boa",       icon: ThumbsUp,   activeClass: "text-blue-500 bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800" },
  { value: "excelente", label: "Excelente", icon: Star,       activeClass: "text-green-500 bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800" },
];

function RatingRow({
  message,
  onRate,
}: {
  message: ChatMessage;
  onRate: (id: string, rating: RatingValue, comment: string) => void;
}) {
  const [draft, setDraft] = useState<RatingValue | null>(null);
  const [comment, setComment] = useState("");

  const saved = message.rating;
  const pending = message.ratingPending;
  const active = saved ?? draft;
  const needsComment = active && active !== "excelente";

  function handleSelect(r: RatingValue) {
    if (saved) return; // readonly após guardar
    setDraft(r);
    if (r === "excelente") {
      onRate(message.id, r, "");
    }
  }

  function handleSave() {
    if (!draft || draft === "excelente") return;
    onRate(message.id, draft, comment);
  }

  const capturedMode = message.decisionTrace?.agent_mode;

  return (
    <div className="mt-2 ml-8 space-y-1.5">
      {capturedMode && (
        <p className="text-xs text-muted-foreground">
          Modo capturado: <span className="font-mono bg-muted px-1 rounded">{capturedMode}</span>
        </p>
      )}
      <div className="flex items-center gap-1">
        {RATING_CONFIG.map(({ value, label, icon: Icon, activeClass }) => {
          const isActive = active === value;
          return (
            <button
              key={value}
              disabled={!!saved || pending}
              onClick={() => handleSelect(value)}
              title={label}
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full border transition-colors ${
                isActive
                  ? activeClass
                  : "text-muted-foreground border-border hover:border-foreground bg-transparent"
              } ${saved ? "cursor-default opacity-80" : "cursor-pointer"}`}
            >
              {pending && isActive ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Icon className="h-3 w-3" />
              )}
              <span className="hidden sm:inline">{label}</span>
            </button>
          );
        })}
      </div>

      {/* Textarea de comentário — só para ratings que não são excelente e ainda não guardados */}
      {!saved && draft && draft !== "excelente" && (
        <div className="flex flex-col gap-1">
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="O que poderia melhorar nesta resposta?"
            rows={2}
            className="resize-none text-xs"
          />
          <Button size="sm" className="self-end h-7 text-xs" onClick={handleSave} disabled={pending}>
            {pending ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
            Guardar avaliação
          </Button>
        </div>
      )}

      {/* Comentário guardado (readonly) */}
      {saved && message.ratingComment && (
        <p className="text-xs text-muted-foreground italic">
          "{message.ratingComment}"
        </p>
      )}
    </div>
  );
}

// ── MessageBubble ─────────────────────────────────────────────────────────────

export function MessageBubble({ message, onToggleFeedback, onRate }: MessageBubbleProps) {
  const [traceOpen, setTraceOpen] = useState(false);
  const isLead = message.role === "lead";

  if (message.isPhaseAdvance) {
    return (
      <div className="flex justify-center my-2">
        <span className="flex items-center gap-1.5 text-xs text-violet-500 bg-violet-50 border border-violet-200 rounded-full px-3 py-1 dark:bg-violet-950 dark:border-violet-800">
          <Zap className="h-3 w-3" />
          Fase avançada → {message.text}
        </span>
      </div>
    );
  }

  const time = new Date(message.timestamp).toLocaleTimeString("pt-PT", {
    hour: "2-digit",
    minute: "2-digit",
  });

  // Detecta se a mensagem do lead é um marcador de mídia
  const leadMediaType = isLead ? parseLeadMediaMarker(message.text) : null;

  return (
    <div className={`flex ${isLead ? "justify-end" : "justify-start"} mb-3 group`}>
      <div className={`flex flex-col max-w-[75%] ${isLead ? "items-end" : "items-start"}`}>
        {/* Rótulo de quem enviou */}
        <span className="text-xs text-muted-foreground mb-1 px-1 flex items-center gap-1">
          {isLead ? "Lead" : message.isAutoMessage ? (
            <><Zap className="h-3 w-3 text-violet-400" /><span className="text-violet-400">Fluxo de Venda</span></>
          ) : "Bot"}
          {" · "}{time}
        </span>

        <div className="flex items-start gap-1">
          {/* Botão de feedback — só para mensagens do bot (não automáticas) */}
          {!isLead && !message.isAutoMessage && (
            <Button
              variant="ghost"
              size="icon"
              className={`h-7 w-7 shrink-0 mt-1 opacity-0 group-hover:opacity-100 transition-opacity ${
                message.selectedForFeedback ? "opacity-100 text-amber-500" : "text-muted-foreground"
              }`}
              onClick={() => onToggleFeedback(message.id)}
              title={message.selectedForFeedback ? "Remover do feedback" : "Adicionar ao feedback"}
            >
              {message.selectedForFeedback ? (
                <BookmarkCheck className="h-4 w-4" />
              ) : (
                <Bookmark className="h-4 w-4" />
              )}
            </Button>
          )}

          {/* Bolha da mensagem */}
          <div
            className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words ${
              isLead
                ? "bg-primary text-primary-foreground rounded-tr-sm"
                : message.isAutoMessage
                ? "bg-violet-50 border border-violet-200 text-foreground rounded-tl-sm dark:bg-violet-950 dark:border-violet-800"
                : message.selectedForFeedback
                ? "bg-amber-50 border-2 border-amber-300 text-foreground rounded-tl-sm dark:bg-amber-950 dark:border-amber-600"
                : "bg-muted text-foreground rounded-tl-sm"
            }`}
          >
            {/* Cards de mídia do bot (pre_send_media) */}
            {!isLead && message.preMediaItems && message.preMediaItems.length > 0 && (
              <div className="mb-2">
                {message.preMediaItems.map((item, i) => (
                  <MediaCard key={i} type={item.media_type} url={item.media_url} />
                ))}
              </div>
            )}

            {/* Conteúdo da mensagem — card de mídia para lead, texto para os demais */}
            {leadMediaType ? (
              <MediaCard type={leadMediaType} url="#" />
            ) : (
              message.text
            )}
          </div>
        </div>

        {/* Trace colapsável — só para mensagens do bot (não automáticas) com trace */}
        {!isLead && !message.isAutoMessage && message.decisionTrace && (
          <div className="mt-1 ml-8">
            <button
              onClick={() => setTraceOpen((o) => !o)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {traceOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              Ver trace
              {message.motherRoute && (
                <Badge variant="outline" className="text-xs h-4 px-1 ml-1">
                  {message.motherRoute}
                </Badge>
              )}
              {typeof message.confidence === "number" && (
                <span className="text-muted-foreground">
                  {Math.round(message.confidence * 100)}%
                </span>
              )}
              {message.guardrails && message.guardrails.length > 0 && (
                <Badge variant="destructive" className="text-xs h-4 px-1">
                  {message.guardrails.length} guardrail{message.guardrails.length > 1 ? "s" : ""}
                </Badge>
              )}
            </button>

            {traceOpen && (
              <pre className="mt-1 text-xs bg-muted rounded-md p-2 overflow-auto max-h-40 text-muted-foreground">
                {JSON.stringify(message.decisionTrace, null, 2)}
              </pre>
            )}
          </div>
        )}

        {/* Preview de humanização — badges com delay/typing/bolhas */}
        {!isLead && message.humanizationPreview && (
          (message.humanizationPreview.delay_s > 0 ||
           message.humanizationPreview.typing_s > 0 ||
           message.humanizationPreview.total_parts > 1) && (
            <div className="mt-1 ml-8 flex flex-wrap gap-1">
              {message.humanizationPreview.delay_s > 0 && (
                <Badge variant="outline" className="text-xs gap-1 text-muted-foreground">
                  <Clock className="h-2.5 w-2.5" />
                  {message.humanizationPreview.delay_s}s delay
                </Badge>
              )}
              {message.humanizationPreview.typing_s > 0 && (
                <Badge variant="outline" className="text-xs gap-1 text-muted-foreground">
                  <Keyboard className="h-2.5 w-2.5" />
                  {message.humanizationPreview.typing_s}s digitando
                </Badge>
              )}
              {message.humanizationPreview.total_parts > 1 && (
                <Badge variant="outline" className="text-xs gap-1 text-muted-foreground">
                  <Layers className="h-2.5 w-2.5" />
                  {message.humanizationPreview.total_parts} bolhas
                </Badge>
              )}
            </div>
          )
        )}

        {/* Linha de rating — só para mensagens do bot (não automáticas) */}
        {!isLead && !message.isAutoMessage && (
          <RatingRow message={message} onRate={onRate} />
        )}
      </div>
    </div>
  );
}
