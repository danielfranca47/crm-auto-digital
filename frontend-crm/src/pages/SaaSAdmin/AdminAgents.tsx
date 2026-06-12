import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  RefreshCw,
  ChevronDown,
  User,
  Clock,
  Check,
  ChevronsUpDown,
  MessageSquare,
  ListChecks,
  Repeat2,
  Target,
} from "lucide-react";

// ------------------------------------------------------------------ types --

type AgentStage = {
  key: string;
  label: string;
  description: string;
  sample_questions?: string[];
  tone_rule?: string;
  followup_attempts?: number[];
  followup_outcomes?: Record<string, string>;
};

type AgentModeOverview = {
  key: string;
  name: string;
  description: string;
  canonical_agent_mode: string;
  max_chars?: number;
  response_style?: string;
  default_next_action?: string;
  tone_rule?: string;
  has_warming: boolean;
  has_followup_attempts: boolean;
  has_followup_outcomes: boolean;
  stages: AgentStage[];
};

type UserProfile = {
  user_id: number;
  email?: string;
  name?: string;
  brand_name?: string;
  niche?: string;
  template_key?: string;
  agent_mode?: string;
  presentation_variant?: string;
  hybrid_flow_style?: string;
  offer_pack?: unknown;
  qualification_score_threshold?: number;
  qualification_required_fields?: string[];
  followup_max_attempts?: number;
  has_custom_config: boolean;
};

type UserDetail = {
  user_id: number;
  profile: Record<string, unknown>;
  playbook: {
    key: string;
    name: string;
    description: string;
    canonical_agent_mode: string;
    max_chars?: number;
    response_style?: string;
    tone_rule?: string;
    stages: AgentStage[];
  };
  diff: Record<string, { default: unknown; user: unknown }>;
  has_custom_config: boolean;
  default_qual_fields_for_mode: string[];
};

// --------------------------------------------------------- color helpers --

const MODE_COLORS: Record<string, string> = {
  consultivo: "indigo",
  agenda: "emerald",
  sdr_scheduler: "emerald",
  direto: "rose",
  closer: "rose",
};

function modeColor(mode: string) {
  return MODE_COLORS[mode] ?? "slate";
}

const MODE_BADGE_CLASSES: Record<string, string> = {
  indigo:
    "bg-indigo-900/40 text-indigo-300 border-indigo-700/40",
  emerald:
    "bg-emerald-900/40 text-emerald-300 border-emerald-700/40",
  rose: "bg-rose-900/40 text-rose-300 border-rose-700/40",
  slate:
    "bg-slate-800 text-slate-400 border-slate-700",
};

const MODE_BORDER_CLASSES: Record<string, string> = {
  indigo: "border-indigo-800/40",
  emerald: "border-emerald-800/40",
  rose: "border-rose-800/40",
  slate: "border-slate-700",
};

const STAGE_ICON: Record<string, React.ElementType> = {
  qualification: ListChecks,
  apresentation: MessageSquare,
  followup: Repeat2,
  closing: Target,
};

// ---------------------------------------------------------------- helpers --

function formatTs(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function labelValue(label: string, value: string | number | null | undefined) {
  if (!value && value !== 0) return null;
  return (
    <div className="mb-1">
      <span className="text-xs text-slate-500 uppercase tracking-wide">
        {label}
      </span>
      <p className="text-sm text-slate-300 mt-0.5">{String(value)}</p>
    </div>
  );
}

// ------------------------------------------------------- StageSheet -------

type SheetState = {
  stage: AgentStage;
  modeName: string;
  diff?: Record<string, { default: unknown; user: unknown }>;
};

function StageSheet({
  state,
  onClose,
}: {
  state: SheetState | null;
  onClose: () => void;
}) {
  if (!state) return null;
  const { stage, modeName, diff } = state;
  const Icon = STAGE_ICON[stage.key] ?? MessageSquare;

  return (
    <Sheet open={!!state} onOpenChange={(o) => !o && onClose()}>
      <SheetContent
        side="right"
        className="w-[420px] sm:w-[520px] bg-slate-900 border-slate-700 text-slate-100"
      >
        <SheetHeader className="mb-4">
          <div className="flex items-center gap-2 mb-1">
            <Icon size={16} className="text-slate-400" />
            <span className="text-xs text-slate-500 uppercase tracking-wide">
              {modeName}
            </span>
          </div>
          <SheetTitle className="text-slate-200 text-lg">
            {stage.label}
          </SheetTitle>
          <p className="text-sm text-slate-400">{stage.description}</p>
        </SheetHeader>

        <ScrollArea className="h-[calc(100vh-180px)] pr-1">
          <div className="space-y-5">
            {/* Tom de voz / regra */}
            {stage.tone_rule && (
              <div className="rounded-lg bg-slate-800/60 p-4">
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">
                  Regra de tom
                </p>
                <p className="text-sm text-slate-300 leading-relaxed">
                  {stage.tone_rule}
                </p>
              </div>
            )}

            {/* Perguntas de qualificação */}
            {stage.sample_questions && stage.sample_questions.length > 0 && (
              <div className="rounded-lg bg-slate-800/60 p-4">
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-3">
                  Perguntas de qualificação ({stage.sample_questions.length})
                </p>
                <ol className="space-y-2">
                  {stage.sample_questions.map((q, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-xs text-slate-600 w-5 shrink-0 pt-0.5">
                        {i + 1}.
                      </span>
                      <p className="text-sm text-slate-300 leading-relaxed">{q}</p>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Follow-up: tentativas */}
            {stage.followup_attempts && stage.followup_attempts.length > 0 && (
              <div className="rounded-lg bg-slate-800/60 p-4">
                <p className="text-xs text-slate-500 uppercase tracking-wide mb-2">
                  Tentativas de follow-up (horas após anterior)
                </p>
                <div className="flex flex-wrap gap-2 mt-1">
                  {stage.followup_attempts.map((h, i) => (
                    <Badge
                      key={i}
                      variant="secondary"
                      className="bg-slate-700 text-slate-300 text-xs"
                    >
                      T{i + 1}: {h}h
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Follow-up: outcomes */}
            {stage.followup_outcomes &&
              Object.keys(stage.followup_outcomes).length > 0 && (
                <div className="rounded-lg bg-slate-800/60 p-4">
                  <p className="text-xs text-slate-500 uppercase tracking-wide mb-3">
                    Outcomes de follow-up
                  </p>
                  <div className="space-y-2">
                    {Object.entries(stage.followup_outcomes).map(
                      ([outcome, description]) => (
                        <div key={outcome} className="flex gap-2">
                          <Badge
                            variant="secondary"
                            className="bg-slate-700 text-slate-400 text-xs shrink-0 h-fit mt-0.5"
                          >
                            {outcome}
                          </Badge>
                          <p className="text-sm text-slate-300 leading-relaxed">
                            {description}
                          </p>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}

            {/* Diff de configuração do usuário */}
            {diff && Object.keys(diff).length > 0 && (
              <div className="rounded-lg bg-amber-950/30 border border-amber-800/40 p-4">
                <p className="text-xs text-amber-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                  <span className="inline-block w-2 h-2 rounded-full bg-amber-400" />
                  Campos personalizados deste usuário
                </p>
                <div className="space-y-3">
                  {Object.entries(diff).map(([field, { default: def, user }]) => (
                    <div key={field} className="text-sm">
                      <p className="text-slate-400 font-mono text-xs mb-1">
                        {field}
                      </p>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="rounded bg-slate-800/60 px-2 py-1">
                          <p className="text-[10px] text-slate-600 mb-0.5">
                            Padrão
                          </p>
                          <p className="text-xs text-slate-400">
                            {def === null || def === undefined
                              ? "—"
                              : Array.isArray(def)
                              ? def.join(", ") || "—"
                              : String(def)}
                          </p>
                        </div>
                        <div className="rounded bg-amber-900/30 px-2 py-1">
                          <p className="text-[10px] text-amber-600 mb-0.5">
                            Usuário
                          </p>
                          <p className="text-xs text-amber-300">
                            {user === null || user === undefined
                              ? "—"
                              : Array.isArray(user)
                              ? user.join(", ") || "—"
                              : String(user)}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Nenhum dado relevante */}
            {!stage.tone_rule &&
              (!stage.sample_questions || stage.sample_questions.length === 0) &&
              (!stage.followup_attempts || stage.followup_attempts.length === 0) &&
              (!stage.followup_outcomes ||
                Object.keys(stage.followup_outcomes).length === 0) && (
                <p className="text-sm text-slate-500 text-center py-8">
                  Nenhum dado de configuração específico para este estágio.
                </p>
              )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

// ------------------------------------------------------- StageColumn ------

function StageColumn({
  stage,
  color,
  onClick,
  isCustomized,
}: {
  stage: AgentStage;
  color: string;
  onClick: () => void;
  isCustomized?: boolean;
}) {
  const Icon = STAGE_ICON[stage.key] ?? MessageSquare;
  const hasData =
    stage.tone_rule ||
    (stage.sample_questions && stage.sample_questions.length > 0) ||
    (stage.followup_attempts && stage.followup_attempts.length > 0) ||
    (stage.followup_outcomes && Object.keys(stage.followup_outcomes).length > 0);

  const borderClass =
    MODE_BORDER_CLASSES[color] ?? "border-slate-700";

  return (
    <button
      onClick={onClick}
      className={`flex-1 min-w-[180px] max-w-[240px] rounded-lg border ${borderClass} bg-slate-800/40 p-4 text-left hover:bg-slate-800/70 transition-colors group`}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Icon size={13} className="text-slate-500 mt-0.5" />
          <span className="text-xs font-medium text-slate-300">
            {stage.label}
          </span>
        </div>
        {isCustomized && (
          <Badge className="bg-amber-900/50 text-amber-300 border-amber-700/50 text-[10px] h-4 px-1">
            Personalizado
          </Badge>
        )}
      </div>

      <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed mb-3">
        {stage.description}
      </p>

      {/* Preview data */}
      {stage.sample_questions && stage.sample_questions.length > 0 && (
        <p className="text-[11px] text-slate-600 line-clamp-1">
          {stage.sample_questions.length} perguntas
        </p>
      )}
      {stage.followup_attempts && stage.followup_attempts.length > 0 && (
        <p className="text-[11px] text-slate-600">
          {stage.followup_attempts.length} tentativas
        </p>
      )}
      {!hasData && (
        <p className="text-[11px] text-slate-700">Sem dados específicos</p>
      )}

      <p className="text-[10px] text-slate-600 group-hover:text-slate-400 mt-3 transition-colors">
        Ver detalhes →
      </p>
    </button>
  );
}

// -------------------------------------------------- AgentModeCard ---------

function AgentModeCard({
  mode,
  userDetail,
  onStageClick,
}: {
  mode: AgentModeOverview;
  userDetail?: UserDetail | null;
  onStageClick: (state: SheetState) => void;
}) {
  const color = modeColor(mode.canonical_agent_mode);
  const badgeClass = MODE_BADGE_CLASSES[color] ?? MODE_BADGE_CLASSES.slate;

  // Se há um usuário selecionado e o template dele é este modo, use o playbook do usuário
  const isUserMode =
    userDetail &&
    (userDetail.playbook.key === mode.key ||
      userDetail.playbook.canonical_agent_mode === mode.canonical_agent_mode);

  const stages = isUserMode ? userDetail.playbook.stages : mode.stages;
  const diff = isUserMode ? userDetail.diff : undefined;

  return (
    <AccordionItem
      value={mode.key}
      className="border border-slate-700/60 rounded-lg mb-3 bg-slate-800/30 overflow-hidden data-[state=open]:bg-slate-800/50"
    >
      <AccordionTrigger className="px-5 py-4 hover:no-underline hover:bg-slate-800/40 transition-colors [&[data-state=open]>svg]:rotate-180">
        <div className="flex items-center gap-3 flex-1 text-left">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-semibold text-slate-200">
                {mode.name}
              </span>
              <Badge
                variant="secondary"
                className={`text-[10px] h-4 px-1.5 ${badgeClass}`}
              >
                {mode.canonical_agent_mode}
              </Badge>
              {isUserMode && userDetail?.has_custom_config && (
                <Badge className="bg-amber-900/40 text-amber-300 border-amber-700/40 text-[10px] h-4 px-1.5">
                  config. personalizada
                </Badge>
              )}
            </div>
            <p className="text-xs text-slate-500 line-clamp-1">
              {mode.description}
            </p>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-600 mr-2">
            <span>{stages.length} estágios</span>
            {mode.max_chars && (
              <span>{(mode.max_chars / 1000).toFixed(0)}k chars</span>
            )}
          </div>
        </div>
      </AccordionTrigger>

      <AccordionContent className="px-5 pb-5 pt-0">
        {/* Metadados do modo */}
        <div className="flex flex-wrap gap-2 mb-4">
          {mode.response_style && (
            <Badge
              variant="secondary"
              className="bg-slate-800 text-slate-400 border-slate-700 text-xs"
            >
              estilo: {mode.response_style}
            </Badge>
          )}
          {mode.has_warming && (
            <Badge
              variant="secondary"
              className="bg-slate-800 text-slate-400 border-slate-700 text-xs"
            >
              tem warming
            </Badge>
          )}
          {mode.has_followup_attempts && (
            <Badge
              variant="secondary"
              className="bg-slate-800 text-slate-400 border-slate-700 text-xs"
            >
              follow-up configurado
            </Badge>
          )}
          {isUserMode && (
            <Badge className="bg-indigo-900/40 text-indigo-300 border-indigo-700/40 text-xs">
              visão do usuário selecionado
            </Badge>
          )}
        </div>

        {/* Fluxo de estágios em colunas */}
        <div className="flex gap-3 overflow-x-auto pb-2">
          {stages.map((stage) => {
            const isCustomized = diff ? Object.keys(diff).length > 0 && stage.key === "qualification" : false;
            return (
              <StageColumn
                key={stage.key}
                stage={stage}
                color={color}
                isCustomized={isCustomized}
                onClick={() =>
                  onStageClick({ stage, modeName: mode.name, diff })
                }
              />
            );
          })}
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}

// -------------------------------------------------- UserCombobox ----------

function UserCombobox({
  users,
  selectedId,
  onSelect,
}: {
  users: UserProfile[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
}) {
  const [open, setOpen] = useState(false);

  const selected = selectedId ? users.find((u) => u.user_id === selectedId) : null;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-[280px] justify-between border-slate-700 bg-slate-800/60 text-slate-300 hover:bg-slate-800 hover:text-slate-200 text-sm"
        >
          <div className="flex items-center gap-2 truncate">
            <User size={13} className="text-slate-500 shrink-0" />
            {selected ? (
              <span className="truncate">
                {selected.email || `Usuário #${selected.user_id}`}
              </span>
            ) : (
              <span className="text-slate-500">Selecionar usuário…</span>
            )}
          </div>
          <ChevronsUpDown size={13} className="text-slate-500 shrink-0 ml-2" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[320px] p-0 bg-slate-800 border-slate-700" align="start">
        <Command className="bg-transparent">
          <CommandInput
            placeholder="Buscar usuário..."
            className="text-slate-300 placeholder:text-slate-500 border-slate-700"
          />
          <CommandList>
            <CommandEmpty className="text-slate-500 text-sm py-4 text-center">
              Nenhum usuário encontrado.
            </CommandEmpty>
            <CommandGroup>
              {selectedId && (
                <CommandItem
                  onSelect={() => { onSelect(null); setOpen(false); }}
                  className="text-slate-400 hover:text-slate-200 cursor-pointer"
                >
                  <span className="text-slate-600 text-xs mr-2">✕</span>
                  Limpar seleção
                </CommandItem>
              )}
              {users.map((u) => (
                <CommandItem
                  key={u.user_id}
                  value={`${u.email ?? ""} ${u.name ?? ""} ${u.user_id}`}
                  onSelect={() => { onSelect(u.user_id); setOpen(false); }}
                  className="cursor-pointer text-slate-300 hover:text-slate-100"
                >
                  <Check
                    size={13}
                    className={`mr-2 shrink-0 ${
                      u.user_id === selectedId ? "opacity-100 text-indigo-400" : "opacity-0"
                    }`}
                  />
                  <div className="flex-1 truncate">
                    <p className="text-sm truncate">{u.email || `#${u.user_id}`}</p>
                    <p className="text-xs text-slate-500 truncate">
                      {u.agent_mode ?? "—"} · {u.template_key ?? "—"}
                      {u.has_custom_config && (
                        <span className="text-amber-500 ml-1">· personalizado</span>
                      )}
                    </p>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

// -------------------------------------------------- Main page -------------

export default function AdminAgents() {
  const [sheetState, setSheetState] = useState<SheetState | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  const {
    data: overview,
    isLoading: overviewLoading,
    error: overviewError,
    refetch: refetchOverview,
    dataUpdatedAt: overviewUpdatedAt,
  } = useQuery({
    queryKey: ["admin", "agents", "overview"],
    queryFn: () => api.admin.getAgentsOverview(),
    staleTime: 60_000,
  });

  const { data: usersData, isLoading: usersLoading } = useQuery({
    queryKey: ["admin", "agents", "users"],
    queryFn: () => api.admin.getAgentsUsers(),
    staleTime: 60_000,
  });

  const { data: userDetail, isLoading: userDetailLoading } = useQuery({
    queryKey: ["admin", "agents", "user", selectedUserId],
    queryFn: () => api.admin.getAgentUserDetail(selectedUserId!),
    enabled: selectedUserId !== null,
    staleTime: 30_000,
  });

  const isLoading = overviewLoading || usersLoading;

  const users = usersData?.users ?? [];
  const agentModes = overview?.agent_modes ?? [];

  // Quando há usuário selecionado, mostrar o modo do usuário primeiro; demais ao fundo
  const sortedModes = selectedUserId && userDetail
    ? [
        ...agentModes.filter(
          (m) =>
            m.key === userDetail.playbook.key ||
            m.canonical_agent_mode === userDetail.playbook.canonical_agent_mode
        ),
        ...agentModes.filter(
          (m) =>
            m.key !== userDetail.playbook.key &&
            m.canonical_agent_mode !== userDetail.playbook.canonical_agent_mode
        ),
      ]
    : agentModes;

  const queriedAt = overview?.queried_at
    ? formatTs(overview.queried_at)
    : null;

  return (
    <div className="p-6 max-w-5xl space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-200">
            Agentes e Prompts
          </h1>
          <p className="text-slate-500 text-sm">
            Configuração ao vivo dos agentes — lida do estado real do sistema.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {queriedAt && (
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <Clock size={11} />
              <span>atualizado às {queriedAt}</span>
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetchOverview()}
            disabled={isLoading}
            className="border-slate-700 text-slate-400 hover:bg-slate-800 gap-1.5"
          >
            <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
            Atualizar
          </Button>
        </div>
      </div>

      {/* Filtro por usuário */}
      <div className="flex items-center gap-3">
        <UserCombobox
          users={users}
          selectedId={selectedUserId}
          onSelect={setSelectedUserId}
        />
        {selectedUserId && userDetailLoading && (
          <span className="text-xs text-slate-500">Carregando perfil…</span>
        )}
        {selectedUserId && userDetail && (
          <div className="flex items-center gap-2">
            {userDetail.has_custom_config ? (
              <Badge className="bg-amber-900/40 text-amber-300 border-amber-700/40 text-xs">
                configuração personalizada
              </Badge>
            ) : (
              <Badge
                variant="secondary"
                className="bg-slate-800 text-slate-500 border-slate-700 text-xs"
              >
                usa configuração padrão
              </Badge>
            )}
            <span className="text-xs text-slate-600">
              template: {userDetail.playbook.key}
            </span>
          </div>
        )}
      </div>

      {/* Erro */}
      {overviewError && (
        <div className="rounded-lg bg-red-950/40 border border-red-800/50 px-4 py-3 text-sm text-red-400">
          Erro ao carregar dados dos agentes. Verifique o token admin.
        </div>
      )}

      {/* Loading state */}
      {overviewLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton
              key={i}
              className="h-16 w-full rounded-lg bg-slate-800/60"
            />
          ))}
        </div>
      )}

      {/* Cards de agentes */}
      {!overviewLoading && agentModes.length > 0 && (
        <Accordion type="multiple" className="space-y-0">
          {sortedModes.map((mode) => (
            <AgentModeCard
              key={mode.key}
              mode={mode}
              userDetail={
                selectedUserId && userDetail &&
                (userDetail.playbook.key === mode.key ||
                  userDetail.playbook.canonical_agent_mode === mode.canonical_agent_mode)
                  ? userDetail
                  : null
              }
              onStageClick={setSheetState}
            />
          ))}
        </Accordion>
      )}

      {/* Estado vazio */}
      {!overviewLoading && !overviewError && agentModes.length === 0 && (
        <div className="rounded-lg bg-slate-800/40 border border-slate-700 px-6 py-10 text-center">
          <p className="text-slate-500 text-sm">
            Nenhum agente encontrado. Verifique se os playbooks estão carregados.
          </p>
        </div>
      )}

      {/* Resumo de usuários */}
      {!usersLoading && users.length > 0 && (
        <Card className="bg-slate-800/40 border-slate-700">
          <CardContent className="px-5 py-4">
            <div className="flex items-center justify-between">
              <p className="text-xs text-slate-500 uppercase tracking-wide">
                Usuários com AI profile configurado
              </p>
              <span className="text-sm font-semibold text-slate-300">
                {users.length}
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5 mt-3">
              {users.map((u) => (
                <button
                  key={u.user_id}
                  onClick={() => setSelectedUserId(u.user_id === selectedUserId ? null : u.user_id)}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs transition-colors ${
                    u.user_id === selectedUserId
                      ? "bg-indigo-700 text-indigo-100"
                      : "bg-slate-700 text-slate-400 hover:bg-slate-600 hover:text-slate-200"
                  }`}
                >
                  {u.email ?? `#${u.user_id}`}
                  {u.has_custom_config && (
                    <span className="text-amber-400">·</span>
                  )}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stage drawer */}
      <StageSheet state={sheetState} onClose={() => setSheetState(null)} />
    </div>
  );
}
