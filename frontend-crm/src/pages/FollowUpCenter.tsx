import { useState, useMemo, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { format, parseISO, differenceInMinutes, isToday, isTomorrow } from "date-fns";
import { ptBR } from "date-fns/locale";
import { api, type FollowUpLead, type FollowUpContract } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Pause, Play, X, Search, AlertCircle, Pencil } from "lucide-react";

// ─── Temperatura ──────────────────────────────────────────────────────────────

type TempKey = "hot" | "warm" | "cold" | "cart_recovery" | "lost" | string;

const TEMP_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  hot:          { label: "Quente",   color: "#F5694E", bg: "rgba(245,105,78,0.1)",   border: "rgba(245,105,78,0.3)"   },
  warm:         { label: "Morno",    color: "#F5A623", bg: "rgba(245,166,35,0.1)",   border: "rgba(245,166,35,0.3)"   },
  cold:         { label: "Frio",     color: "#5B9CF6", bg: "rgba(91,156,246,0.1)",   border: "rgba(91,156,246,0.3)"   },
  cart_recovery:{ label: "Carrinho", color: "#52C4A0", bg: "rgba(82,196,160,0.1)",   border: "rgba(82,196,160,0.3)"   },
  lost:         { label: "Perdido",  color: "#6B6E84", bg: "rgba(107,110,132,0.1)",  border: "rgba(107,110,132,0.25)" },
};

function getTempCfg(key: TempKey) {
  return TEMP_CONFIG[key] ?? TEMP_CONFIG["cold"];
}

// ─── Agente ───────────────────────────────────────────────────────────────────

const AGENT_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  agent_1: { label: "A1", color: "#F0C060", bg: "rgba(240,192,96,0.07)",  border: "rgba(240,192,96,0.3)"  },
  agent_2: { label: "A2", color: "#50D8C8", bg: "rgba(80,216,200,0.07)",  border: "rgba(80,216,200,0.3)"  },
  agent_3: { label: "A3", color: "#B87FFF", bg: "rgba(184,127,255,0.07)", border: "rgba(184,127,255,0.3)" },
};

function getAgentCfg(key: string | null) {
  return AGENT_CONFIG[key ?? ""] ?? { label: key ?? "–", color: "#9295ab", bg: "rgba(146,149,171,0.07)", border: "rgba(146,149,171,0.3)" };
}

// ─── Status helpers ───────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  active:           "Ativo",
  scheduled:        "Programado",
  manually_paused:  "Pausado",
  paused:           "Pausado",
  closed:           "Encerrado",
};

function getStatusClasses(status: string): string {
  switch (status) {
    case "active":    return "text-emerald-400 border-emerald-400/30 bg-emerald-400/10";
    case "scheduled": return "text-violet-400 border-violet-400/30 bg-violet-400/10";
    case "manually_paused":
    case "paused":    return "text-amber-400 border-amber-400/30 bg-amber-400/10";
    default:          return "text-muted-foreground border-border bg-muted/20";
  }
}

// ─── Formatação de data ───────────────────────────────────────────────────────

type Urgency = "overdue" | "now" | "soon" | "normal" | "none";

function formatNextSend(isoStr: string | null | undefined, status: string): { text: string; sub?: string; urgency: Urgency } {
  const isPaused = status === "paused" || status === "manually_paused";
  if (isPaused) {
    const reason = status === "paused" ? "Lead respondeu" : "Pausado manualmente";
    return { text: "Pausado", sub: reason, urgency: "none" };
  }
  if (!isoStr) return { text: "—", urgency: "none" };
  try {
    const dt = parseISO(isoStr);
    const now = new Date();
    const diffMins = differenceInMinutes(dt, now);
    if (diffMins < 0) return { text: "Vencido", sub: format(dt, "d MMM, HH:mm", { locale: ptBR }), urgency: "overdue" };
    if (diffMins < 120) {
      const h = Math.floor(diffMins / 60);
      const m = diffMins % 60;
      const text = h > 0 ? `Em ${h}h ${m}min` : `Em ${m} min`;
      return { text, sub: format(dt, "HH:mm"), urgency: diffMins < 60 ? "now" : "soon" };
    }
    if (isToday(dt))    return { text: `Hoje ${format(dt, "HH:mm")}`,                urgency: "soon"   };
    if (isTomorrow(dt)) return { text: `Amanhã`,  sub: format(dt, "HH:mm"),          urgency: "normal" };
    return { text: format(dt, "d MMM", { locale: ptBR }), sub: format(dt, "HH:mm"), urgency: "normal" };
  } catch {
    return { text: "—", urgency: "none" };
  }
}

function urgencyColor(u: Urgency): string {
  switch (u) {
    case "overdue":
    case "now":  return "text-red-400";
    case "soon": return "text-amber-400";
    default:     return "text-foreground";
  }
}

// ─── Attempt dots ─────────────────────────────────────────────────────────────

function AttemptDots({ attempts, max }: { attempts: number; max: number }) {
  const dots = Array.from({ length: max }, (_, i) => {
    if (i < attempts) return "done";
    if (i === attempts) return "next";
    return "empty";
  });
  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-[3px]">
        {dots.map((type, i) => (
          <div
            key={i}
            className={cn("w-[7px] h-[7px] rounded-full", {
              "bg-violet-500":                          type === "done",
              "bg-violet-500/40 border border-violet-500": type === "next",
              "bg-muted border border-border":         type === "empty",
            })}
          />
        ))}
      </div>
      <span className="font-mono text-[10px] text-muted-foreground">{attempts}/{max}</span>
    </div>
  );
}

// ─── Notification banner ──────────────────────────────────────────────────────

function NotificationBanner({ leads, onView }: { leads: FollowUpLead[]; onView: (lead: FollowUpLead) => void }) {
  const autopaused = leads.filter((l) => l.followup_status === "paused");
  if (autopaused.length === 0) return null;
  const first = autopaused[0];
  return (
    <div
      className="flex items-center gap-3 rounded-lg px-4 py-3 mb-4"
      style={{ background: "rgba(245,105,78,0.06)", border: "1px solid rgba(245,105,78,0.25)" }}
    >
      <span className="relative flex h-2 w-2 flex-shrink-0">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
      </span>
      <p className="text-sm flex-1">
        <span style={{ color: "#F5694E" }} className="font-semibold">
          {first.companyName}
        </span>{" "}
        respondeu ao follow-up — bot pausado automaticamente. Ação necessária.
        {autopaused.length > 1 && (
          <span className="text-muted-foreground ml-1">(+{autopaused.length - 1} mais)</span>
        )}
      </p>
      <button
        className="text-xs underline whitespace-nowrap"
        style={{ color: "#F5694E" }}
        onClick={() => onView(first)}
      >
        Ver →
      </button>
    </div>
  );
}

// ─── Stats bar ────────────────────────────────────────────────────────────────

function StatsBar({ stats, loading }: { stats?: { total_active: number; hot_active: number; urgent_count: number; replied_today: number }; loading: boolean }) {
  const cards = [
    { label: "Em andamento", value: stats?.total_active ?? 0, sub: "follow-ups ativos", highlight: false },
    { label: "Quentes ativos", value: stats?.hot_active ?? 0, sub: "Prioridade máxima", highlight: "hot" as const },
    { label: "Envio em < 2h", value: stats?.urgent_count ?? 0, sub: "Aguardam atenção", highlight: "accent" as const },
    { label: "Pausados hoje", value: stats?.replied_today ?? 0, sub: "Lead respondeu", highlight: false },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-6">
      {cards.map((c) => (
        <div
          key={c.label}
          className="rounded-xl p-4 border bg-card"
          style={
            c.highlight === "hot"
              ? { borderColor: "rgba(245,105,78,0.3)" }
              : c.highlight === "accent"
              ? { borderColor: "rgba(124,106,247,0.3)" }
              : undefined
          }
        >
          <p className="text-[11px] font-mono tracking-wider uppercase text-muted-foreground mb-1">{c.label}</p>
          {loading ? (
            <Skeleton className="h-7 w-12 mb-1" />
          ) : (
            <p
              className="font-bold text-2xl mb-0.5"
              style={
                c.highlight === "hot"
                  ? { color: "#F5694E" }
                  : c.highlight === "accent"
                  ? { color: "#7c6af7" }
                  : undefined
              }
            >
              {c.value}
            </p>
          )}
          <p className="text-[11px] text-muted-foreground">{c.sub}</p>
        </div>
      ))}
    </div>
  );
}

// ─── Drawer ───────────────────────────────────────────────────────────────────

type DrawerAction = "pause" | "resume" | "cancel" | null;

function buildTimeline(contract: FollowUpContract) {
  const { attempts, max_attempts, last_followup_at, next_followup_at } = contract;
  const items: Array<{ label: string; title: string; status: "sent" | "pending" | "future" }> = [];
  for (let i = 0; i < max_attempts; i++) {
    if (i < attempts) {
      const label = last_followup_at && i === attempts - 1
        ? `Enviada · ${tryFormat(last_followup_at)}`
        : `Tentativa ${i + 1} · Enviada`;
      items.push({ label, title: `Tentativa ${i + 1}`, status: "sent" });
    } else if (i === attempts && next_followup_at) {
      items.push({
        label: `Programada · ${tryFormat(next_followup_at)}`,
        title: `Tentativa ${i + 1}`,
        status: "pending",
      });
    } else {
      items.push({ label: `Prevista`, title: `Tentativa ${i + 1}`, status: "future" });
    }
  }
  return items;
}

function tryFormat(iso: string): string {
  try {
    return format(parseISO(iso), "d MMM, HH:mm", { locale: ptBR });
  } catch {
    return iso;
  }
}

function LeadDrawer({
  lead,
  open,
  onClose,
  onAction,
  actionLoading,
}: {
  lead: FollowUpLead | null;
  open: boolean;
  onClose: () => void;
  onAction: (action: DrawerAction, lead: FollowUpLead) => void;
  actionLoading: boolean;
}) {
  const navigate = useNavigate();
  if (!lead) return null;
  const contract = lead.followup_contract;
  const status = lead.followup_status ?? "";
  const tempKey = (contract?.temperature ?? "cold") as TempKey;
  const tempCfg = getTempCfg(tempKey);
  const agentCfg = getAgentCfg(lead.agent_type);
  const timeline = contract ? buildTimeline(contract) : [];
  const nextSend = formatNextSend(lead.next_followup_at, status);

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="right" className="w-[380px] p-0 overflow-y-auto flex flex-col">
        <SheetHeader className="px-5 py-4 border-b flex flex-row items-center gap-3 space-y-0">
          <div className="flex-1 min-w-0">
            <SheetTitle className="text-sm font-semibold truncate">{lead.companyName}</SheetTitle>
            {lead.contactName && <p className="text-xs text-muted-foreground truncate">{lead.contactName}</p>}
          </div>
          <div
            className="flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full border shrink-0"
            style={{ color: tempCfg.color, background: tempCfg.bg, borderColor: tempCfg.border }}
          >
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: tempCfg.color }} />
            {tempCfg.label}
          </div>
        </SheetHeader>

        {/* Details */}
        <div className="px-5 py-4 border-b space-y-1.5">
          <p className="text-[9px] font-mono tracking-widest uppercase text-muted-foreground mb-2">Detalhes</p>
          {[
            ["Agente", agentCfg.label],
            ["Status", STATUS_LABELS[status] ?? status],
            ["Tentativa", contract ? `${contract.attempts} de ${contract.max_attempts}` : "—"],
            ["Próximo envio", nextSend.text + (nextSend.sub ? ` · ${nextSend.sub}` : "")],
            contract?.followup_goal ? ["Objetivo", contract.followup_goal] : null,
          ].filter(Boolean).map(([k, v]) => (
            <div key={k as string} className="flex justify-between text-xs py-0.5">
              <span className="text-muted-foreground">{k as string}</span>
              <span className="font-medium">{v as string}</span>
            </div>
          ))}
          {contract?.operator_note && (
            <div className="mt-3 rounded-lg px-3 py-2.5 bg-muted/30 text-xs text-muted-foreground leading-relaxed">
              <span className="block text-[9px] font-mono tracking-widest uppercase text-muted-foreground mb-1">Nota do operador</span>
              {contract.operator_note}
            </div>
          )}
        </div>

        {/* Timeline */}
        {timeline.length > 0 && (
          <div className="px-5 py-4 border-b flex-1">
            <p className="text-[9px] font-mono tracking-widest uppercase text-muted-foreground mb-4">Linha do tempo</p>
            <div className="flex flex-col">
              {timeline.map((item, i) => {
                const isLast = i === timeline.length - 1;
                const dotCls = item.status === "sent" ? "bg-emerald-500" : item.status === "pending" ? "bg-violet-400/60 border border-violet-400" : "bg-muted border border-border";
                return (
                  <div key={i} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <div className={cn("w-2 h-2 rounded-full mt-1 shrink-0", dotCls)} />
                      {!isLast && (
                        <div className={cn("w-px flex-1 min-h-[20px] my-1", item.status === "sent" ? "bg-border" : "border-l border-dashed border-border")} />
                      )}
                    </div>
                    <div className="flex-1 pb-4">
                      <p className="text-[9px] font-mono text-muted-foreground mb-0.5">{item.label}</p>
                      <p className="text-xs font-medium">{item.title}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="px-5 py-4 flex flex-col gap-2 border-t mt-auto">
          {status === "scheduled" && (
            <Button
              className="justify-start gap-2 w-full bg-violet-600 hover:bg-violet-700 text-white"
              onClick={() => { onClose(); navigate(`/follow-ups/${lead.id}/edit`); }}
            >
              <Pencil className="w-4 h-4" />
              Editar mensagem agendada
            </Button>
          )}
          {(status === "active" || status === "scheduled") && (
            <Button
              variant="outline"
              className="justify-start gap-2 w-full"
              onClick={() => onAction("pause", lead)}
              disabled={actionLoading}
            >
              <Pause className="w-4 h-4" />
              Pausar follow-up
            </Button>
          )}
          {status === "manually_paused" && (
            <Button
              className="justify-start gap-2 w-full bg-violet-600 hover:bg-violet-700 text-white"
              onClick={() => onAction("resume", lead)}
              disabled={actionLoading}
            >
              <Play className="w-4 h-4" />
              Retomar follow-up
            </Button>
          )}
          {status === "paused" && (
            <div className="flex items-center gap-2 rounded-lg px-3 py-2.5 bg-amber-400/10 border border-amber-400/25 text-xs text-amber-400">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>Lead respondeu — requer ação manual antes de retomar.</span>
            </div>
          )}
          {status !== "closed" && (
            <Button
              variant="outline"
              className="justify-start gap-2 w-full text-red-400 border-red-400/30 bg-red-400/5 hover:bg-red-400/15 hover:text-red-400"
              onClick={() => onAction("cancel", lead)}
              disabled={actionLoading}
            >
              <X className="w-4 h-4" />
              Cancelar follow-up
            </Button>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

// ─── Confirm modal ────────────────────────────────────────────────────────────

type ModalType = "pause" | "resume" | "cancel" | null;

const MODAL_CONFIG = {
  pause:  { title: "Pausar follow-up",   desc: "O próximo envio agendado será cancelado. Você poderá retomar o follow-up manualmente a qualquer momento.", confirm: "Pausar", variant: "outline" as const },
  resume: { title: "Retomar follow-up",  desc: "O follow-up será reativado e o próximo envio será agendado de acordo com a cadência configurada.", confirm: "Retomar", variant: "default" as const },
  cancel: { title: "Cancelar follow-up", desc: "O follow-up será encerrado permanentemente. O lead permanece no Kanban mas não receberá mais mensagens automáticas. Esta ação não pode ser desfeita.", confirm: "Cancelar definitivamente", variant: "destructive" as const },
};

function ConfirmModal({
  type,
  lead,
  open,
  onClose,
  onConfirm,
  loading,
}: {
  type: ModalType;
  lead: FollowUpLead | null;
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  loading: boolean;
}) {
  if (!type || !lead) return null;
  const cfg = MODAL_CONFIG[type];
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{cfg.title}</DialogTitle>
          <DialogDescription asChild>
            <div>
              <div className="rounded-lg bg-muted/40 px-3 py-2 mb-3 text-sm space-y-1">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Lead</span>
                  <span className="font-medium">{lead.companyName}</span>
                </div>
                {lead.followup_contract && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Tentativa</span>
                    <span className="font-medium">{lead.followup_contract.attempts} de {lead.followup_contract.max_attempts}</span>
                  </div>
                )}
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">{cfg.desc}</p>
            </div>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose} disabled={loading}>Voltar</Button>
          <Button variant={cfg.variant} onClick={onConfirm} disabled={loading}>
            {loading ? "Aguarde..." : cfg.confirm}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Table row ────────────────────────────────────────────────────────────────

function FollowUpRow({
  lead,
  onClick,
  onPause,
  onResume,
  onCancel,
  actionLoading,
}: {
  lead: FollowUpLead;
  onClick: () => void;
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
  actionLoading: boolean;
}) {
  const contract = lead.followup_contract;
  const status = lead.followup_status ?? "";
  const tempKey = (contract?.temperature ?? "cold") as TempKey;
  const tempCfg = getTempCfg(tempKey);
  const agentCfg = getAgentCfg(lead.agent_type);
  const nextSend = formatNextSend(lead.next_followup_at, status);

  return (
    <div
      className="grid items-center gap-2 px-4 py-3 border-b last:border-0 cursor-pointer hover:bg-muted/30 transition-colors"
      style={{ gridTemplateColumns: "2fr 80px 100px 120px 130px 100px 100px" }}
      onClick={onClick}
    >
      {/* Lead */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0"
          style={{ background: tempCfg.bg, color: tempCfg.color }}
        >
          {(lead.companyName ?? "?").slice(0, 2).toUpperCase()}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{lead.companyName}</p>
          <p className="text-xs text-muted-foreground truncate">{lead.contactName ?? "—"}</p>
        </div>
      </div>

      {/* Agent */}
      <div>
        <span
          className="text-[9px] font-mono tracking-wide uppercase px-1.5 py-0.5 rounded border"
          style={{ color: agentCfg.color, background: agentCfg.bg, borderColor: agentCfg.border }}
        >
          {agentCfg.label}
        </span>
      </div>

      {/* Temperatura */}
      <div className="flex items-center gap-1.5 text-xs font-medium">
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: tempCfg.color }} />
        <span style={{ color: tempCfg.color }}>{tempCfg.label}</span>
      </div>

      {/* Tentativa */}
      <div>
        {contract ? (
          <AttemptDots attempts={contract.attempts} max={contract.max_attempts} />
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </div>

      {/* Próximo envio */}
      <div className="flex flex-col gap-0.5">
        <span className={cn("text-sm font-medium", urgencyColor(nextSend.urgency))}>{nextSend.text}</span>
        {nextSend.sub && <span className="text-xs text-muted-foreground">{nextSend.sub}</span>}
      </div>

      {/* Status */}
      <div>
        <span className={cn("inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full border", getStatusClasses(status))}>
          <span className="w-1.5 h-1.5 rounded-full bg-current" />
          {STATUS_LABELS[status] ?? status}
        </span>
      </div>

      {/* Actions */}
      <div
        className="flex items-center gap-1 justify-end"
        onClick={(e) => e.stopPropagation()}
      >
        {(status === "active" || status === "scheduled") && (
          <button
            className="w-7 h-7 rounded-md border border-border hover:bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
            title="Pausar"
            onClick={onPause}
            disabled={actionLoading}
          >
            <Pause className="w-3.5 h-3.5" />
          </button>
        )}
        {status === "manually_paused" && (
          <button
            className="w-7 h-7 rounded-md border border-violet-400/30 bg-violet-400/10 hover:bg-violet-400/20 flex items-center justify-center text-violet-400 transition-colors"
            title="Retomar"
            onClick={onResume}
            disabled={actionLoading}
          >
            <Play className="w-3.5 h-3.5" />
          </button>
        )}
        <button
          className="w-7 h-7 rounded-md border border-border hover:border-red-400/40 hover:bg-red-400/10 flex items-center justify-center text-muted-foreground hover:text-red-400 transition-colors"
          title="Cancelar"
          onClick={onCancel}
          disabled={actionLoading}
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

type StatusFilter = "all" | "active" | "scheduled" | "manually_paused" | "paused";
type AgentFilter  = "all" | "agent_1" | "agent_2" | "agent_3";
type TempFilter   = "all" | "hot" | "warm" | "cold" | "cart_recovery";

export default function FollowUpCenter() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();

  // ── Filters ─────────────────────────────────────────────────────────────────
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [agentFilter,  setAgentFilter]  = useState<AgentFilter>("all");
  const [tempFilter,   setTempFilter]   = useState<TempFilter>("all");
  const [search,       setSearch]       = useState("");

  // ── Drawer / modal state ─────────────────────────────────────────────────────
  const [drawerLead, setDrawerLead] = useState<FollowUpLead | null>(null);
  const [modalAction, setModalAction] = useState<ModalType>(null);
  const [modalLead, setModalLead] = useState<FollowUpLead | null>(null);

  // ── Data fetching ────────────────────────────────────────────────────────────
  const { data: leads = [], isLoading: leadsLoading } = useQuery({
    queryKey: ["followups-active"],
    queryFn: () => api.followUps.listActive(),
    refetchInterval: 30_000,
  });

  // Auto-open drawer when navigated from a badge click (?leadId=)
  useEffect(() => {
    const paramLeadId = searchParams.get("leadId");
    if (!paramLeadId || leads.length === 0) return;
    const target = leads.find((l) => String(l.id) === paramLeadId);
    if (target) setDrawerLead(target);
  }, [searchParams, leads]);

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["followups-stats"],
    queryFn: () => api.followUps.getStats(),
    refetchInterval: 30_000,
  });

  // ── Mutations ────────────────────────────────────────────────────────────────
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["followups-active"] });
    queryClient.invalidateQueries({ queryKey: ["followups-stats"] });
  };

  const pauseMutation = useMutation({
    mutationFn: (id: number) => api.followUps.pause(id),
    onSuccess: () => { toast.success("Follow-up pausado."); invalidate(); closeModal(); setDrawerLead(null); },
    onError: (e: any) => toast.error(e?.message ?? "Erro ao pausar"),
  });

  const resumeMutation = useMutation({
    mutationFn: (id: number) => api.followUps.resume(id),
    onSuccess: (_, id) => {
      toast.success("Follow-up retomado.");
      invalidate();
      closeModal();
      // update drawer lead if open
      queryClient.invalidateQueries({ queryKey: ["followups-active"] });
      setDrawerLead(null);
    },
    onError: (e: any) => toast.error(e?.message ?? "Erro ao retomar"),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: number) => api.followUps.cancel(id),
    onSuccess: () => { toast.success("Follow-up cancelado."); invalidate(); closeModal(); setDrawerLead(null); },
    onError: (e: any) => toast.error(e?.message ?? "Erro ao cancelar"),
  });

  const actionLoading = pauseMutation.isPending || resumeMutation.isPending || cancelMutation.isPending;

  // ── Action handlers ──────────────────────────────────────────────────────────
  function openModal(action: ModalType, lead: FollowUpLead) {
    setModalAction(action);
    setModalLead(lead);
  }
  function closeModal() {
    setModalAction(null);
    setModalLead(null);
  }
  function handleDrawerAction(action: DrawerAction, lead: FollowUpLead) {
    if (!action) return;
    openModal(action, lead);
  }
  function handleConfirm() {
    if (!modalLead || !modalAction) return;
    if (modalAction === "pause")  pauseMutation.mutate(modalLead.id);
    if (modalAction === "resume") resumeMutation.mutate(modalLead.id);
    if (modalAction === "cancel") cancelMutation.mutate(modalLead.id);
  }

  // ── Filtering ────────────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    return leads.filter((lead) => {
      const status = lead.followup_status ?? "";
      const contract = lead.followup_contract;
      const temp = (contract?.temperature ?? "").toLowerCase();
      const agent = lead.agent_type ?? "";
      const name = (lead.companyName + " " + (lead.contactName ?? "")).toLowerCase();

      if (statusFilter !== "all" && status !== statusFilter) return false;
      if (agentFilter  !== "all" && agent !== agentFilter) return false;
      if (tempFilter   !== "all" && temp  !== tempFilter)  return false;
      if (search && !name.includes(search.toLowerCase())) return false;
      return true;
    });
  }, [leads, statusFilter, agentFilter, tempFilter, search]);

  // ── Status tab counts ────────────────────────────────────────────────────────
  const counts = useMemo(() => {
    const c = { all: leads.length, active: 0, scheduled: 0, paused: 0, manually_paused: 0 };
    leads.forEach((l) => {
      const s = l.followup_status ?? "";
      if (s === "active")          c.active++;
      if (s === "scheduled")       c.scheduled++;
      if (s === "paused")          c.paused++;
      if (s === "manually_paused") c.manually_paused++;
    });
    return c;
  }, [leads]);

  const pausedCount = counts.paused + counts.manually_paused;

  return (
    <div className="flex-1 p-6 md:p-8 max-w-screen-xl mx-auto">
      {/* Page header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Central de Follow-ups</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {counts.all} follow-up{counts.all !== 1 ? "s" : ""} em andamento
            {pausedCount > 0 && ` · ${pausedCount} aguardam ação`}
          </p>
        </div>
      </div>

      {/* Stats */}
      <StatsBar stats={stats} loading={statsLoading} />

      {/* Notification banner */}
      <NotificationBanner leads={leads} onView={(lead) => setDrawerLead(lead)} />

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {/* Status tabs */}
        <div className="flex gap-0.5 bg-muted/50 rounded-lg p-1 border">
          {(
            [
              { key: "all",              label: `Todos (${counts.all})` },
              { key: "active",           label: `Ativos (${counts.active})` },
              { key: "scheduled",        label: `Prog. (${counts.scheduled})` },
              { key: "manually_paused",  label: `Pausados (${counts.manually_paused + counts.paused})` },
            ] as { key: StatusFilter; label: string }[]
          ).map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setStatusFilter(key === "manually_paused" ? "manually_paused" : key)}
              className={cn(
                "text-xs px-3 py-1.5 rounded-md transition-colors whitespace-nowrap",
                statusFilter === key
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="w-px h-5 bg-border mx-1" />

        {/* Agent filter */}
        <Select value={agentFilter} onValueChange={(v) => setAgentFilter(v as AgentFilter)}>
          <SelectTrigger className="w-40 h-8 text-xs">
            <SelectValue placeholder="Todos os agentes" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos os agentes</SelectItem>
            <SelectItem value="agent_1">Agente 1 — Alto Ticket</SelectItem>
            <SelectItem value="agent_2">Agente 2 — Low Ticket</SelectItem>
            <SelectItem value="agent_3">Agente 3 — Híbrido</SelectItem>
          </SelectContent>
        </Select>

        {/* Temperature filter */}
        <Select value={tempFilter} onValueChange={(v) => setTempFilter(v as TempFilter)}>
          <SelectTrigger className="w-36 h-8 text-xs">
            <SelectValue placeholder="Temperatura" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Temperatura</SelectItem>
            <SelectItem value="hot">Quente</SelectItem>
            <SelectItem value="warm">Morno</SelectItem>
            <SelectItem value="cold">Frio</SelectItem>
            <SelectItem value="cart_recovery">Carrinho</SelectItem>
          </SelectContent>
        </Select>

        {/* Search */}
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
          <Input
            className="pl-8 h-8 text-xs"
            placeholder="Buscar lead..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border bg-card overflow-hidden">
        {/* Header */}
        <div
          className="grid px-4 py-2.5 border-b bg-muted/30 text-[10px] font-mono tracking-widest uppercase text-muted-foreground"
          style={{ gridTemplateColumns: "2fr 80px 100px 120px 130px 100px 100px" }}
        >
          <span>Lead</span>
          <span>Agente</span>
          <span>Temperatura</span>
          <span>Tentativa</span>
          <span>Próximo envio</span>
          <span>Status</span>
          <span />
        </div>

        {/* Rows */}
        {leadsLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-3 border-b last:border-0">
              <Skeleton className="w-8 h-8 rounded-lg" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-3 w-40" />
                <Skeleton className="h-2.5 w-28" />
              </div>
              <Skeleton className="h-5 w-12" />
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-5 w-20" />
            </div>
          ))
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground">
            <p className="text-3xl mb-3">📭</p>
            <p className="font-medium text-sm">Nenhum follow-up encontrado</p>
            <p className="text-xs mt-1">Tente ajustar os filtros</p>
          </div>
        ) : (
          filtered.map((lead) => (
            <FollowUpRow
              key={lead.id}
              lead={lead}
              onClick={() => setDrawerLead(lead)}
              onPause={() => openModal("pause", lead)}
              onResume={() => openModal("resume", lead)}
              onCancel={() => openModal("cancel", lead)}
              actionLoading={actionLoading}
            />
          ))
        )}
      </div>

      {/* Detail drawer */}
      <LeadDrawer
        lead={drawerLead}
        open={drawerLead !== null}
        onClose={() => setDrawerLead(null)}
        onAction={handleDrawerAction}
        actionLoading={actionLoading}
      />

      {/* Confirm modal */}
      <ConfirmModal
        type={modalAction}
        lead={modalLead}
        open={modalAction !== null}
        onClose={closeModal}
        onConfirm={handleConfirm}
        loading={actionLoading}
      />
    </div>
  );
}
