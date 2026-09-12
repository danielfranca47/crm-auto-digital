import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ChevronLeft, ChevronRight, MessageSquareOff, Phone, Users, UserCog } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ManageCollaboratorsDialog } from "@/components/ManageCollaboratorsDialog";
import { ARCHIVED_COLUMNS, KANBAN_COLUMNS } from "@/data/mockData";
import { api, type CollabMonitorConversation, type LeadMessage } from "@/services/api";

const CONVERSATIONS_PAGE_SIZE = 20;
const MESSAGES_PAGE_SIZE = 30;
const STALE_THRESHOLD_OPTIONS = [1, 3, 6, 12, 24];

const STAGE_LOOKUP = new Map(
  [...KANBAN_COLUMNS, ...ARCHIVED_COLUMNS].map((column) => [column.id, { label: column.title, color: column.color }])
);

function isAwaitingResponse(
  conversation: Pick<CollabMonitorConversation, "last_message_from" | "last_message_at">,
  thresholdHours: number
): boolean {
  if (conversation.last_message_from !== "inbound" || !conversation.last_message_at) return false;
  const elapsed = Date.now() - new Date(conversation.last_message_at).getTime();
  return Number.isFinite(elapsed) && elapsed > thresholdHours * 60 * 60 * 1000;
}

function hoursSince(value: string): number {
  return Math.max(1, Math.floor((Date.now() - new Date(value).getTime()) / (60 * 60 * 1000)));
}

function StageChip({ category }: { category?: string | null }) {
  const stage = category ? STAGE_LOOKUP.get(category) : undefined;
  if (!stage) return null;
  return (
    <span
      className="text-[10px] px-1.5 h-4 rounded-full font-medium shrink-0 inline-flex items-center"
      style={{ backgroundColor: `${stage.color}26`, color: stage.color }}
    >
      {stage.label}
    </span>
  );
}

function StaleChip({ hours }: { hours: number }) {
  return (
    <span className="text-[10px] px-1.5 h-4 rounded-full font-medium shrink-0 inline-flex items-center gap-1 bg-destructive/10 text-destructive">
      <AlertTriangle className="h-2.5 w-2.5" />
      Sem resposta há {hours}h
    </span>
  );
}

function Pager({
  page,
  hasMore,
  onPrev,
  onNext,
  className = "",
}: {
  page: number;
  hasMore: boolean;
  onPrev: () => void;
  onNext: () => void;
  className?: string;
}) {
  return (
    <div className={`flex items-center justify-between gap-2 px-2 py-1.5 ${className}`}>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 px-2 text-xs"
        disabled={page === 0}
        onClick={onPrev}
      >
        <ChevronLeft className="h-3.5 w-3.5 mr-1" />
        Anterior
      </Button>
      <span className="text-[11px] text-muted-foreground">Página {page + 1}</span>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 px-2 text-xs"
        disabled={!hasMore}
        onClick={onNext}
      >
        Próxima
        <ChevronRight className="h-3.5 w-3.5 ml-1" />
      </Button>
    </div>
  );
}

function getInitials(name?: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase() || "?";
}

function formatTimestamp(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ConversationListItem({
  conversation,
  active,
  onSelect,
  staleThresholdHours,
}: {
  conversation: CollabMonitorConversation;
  active: boolean;
  onSelect: () => void;
  staleThresholdHours: number;
}) {
  const displayName = conversation.contact_name || conversation.phone || "Sem nome";
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full text-left px-3 py-2.5 flex items-start gap-2.5 border-b border-border/50 transition-colors ${
        active ? "bg-muted" : "hover:bg-muted/50"
      }`}
    >
      <Avatar className="h-10 w-10 shrink-0">
        <AvatarFallback className="text-xs font-medium">
          {getInitials(displayName)}
        </AvatarFallback>
      </Avatar>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-medium truncate">{displayName}</p>
          <span className="text-[10px] text-muted-foreground shrink-0">
            {formatTimestamp(conversation.last_message_at)}
          </span>
        </div>
        <div className="flex items-center justify-between gap-2 mt-0.5">
          <p className="text-xs text-muted-foreground truncate">
            {conversation.last_message_preview || "Sem mensagens ainda"}
          </p>
          {conversation.msg_count > 0 && (
            <Badge variant="secondary" className="text-[10px] px-1.5 h-4 shrink-0">
              {conversation.msg_count}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1.5 flex-wrap mt-1">
          <StageChip category={conversation.category} />
          {isAwaitingResponse(conversation, staleThresholdHours) && conversation.last_message_at && (
            <StaleChip hours={hoursSince(conversation.last_message_at)} />
          )}
        </div>
        {conversation.collaborator_name && (
          <p className="text-[10px] text-muted-foreground/80 truncate mt-0.5">
            via {conversation.collaborator_name}
          </p>
        )}
      </div>
    </button>
  );
}

function MessageBubble({ message }: { message: LeadMessage }) {
  const fromCollaborator = message.model === "human_agent";
  return (
    <div className={`flex ${fromCollaborator ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap break-words ${
          fromCollaborator
            ? "bg-primary text-primary-foreground rounded-br-sm"
            : "bg-muted rounded-bl-sm"
        }`}
      >
        <p>{message.body}</p>
        <p
          className={`text-[10px] mt-1 text-right ${
            fromCollaborator ? "text-primary-foreground/70" : "text-muted-foreground"
          }`}
        >
          {formatTimestamp(message.createdAt)}
        </p>
      </div>
    </div>
  );
}

export default function CollabMonitorInbox() {
  const queryClient = useQueryClient();
  const [instanceFilter, setInstanceFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<"active" | "all">("active");
  const [selectedLeadId, setSelectedLeadId] = useState<number | null>(null);
  const [manageOpen, setManageOpen] = useState(false);
  const [conversationPage, setConversationPage] = useState(0);
  const [messagePage, setMessagePage] = useState(0);

  function handleInstanceFilterChange(value: string) {
    setInstanceFilter(value);
    setConversationPage(0);
  }

  function handleStatusFilterChange(value: string) {
    setStatusFilter(value === "all" ? "all" : "active");
    setConversationPage(0);
  }

  function handleSelectConversation(leadId: number) {
    setSelectedLeadId(leadId);
    setMessagePage(0);
  }

  const { data: conversationsPage, isLoading: conversationsLoading } = useQuery({
    queryKey: ["collab-monitor-conversations", instanceFilter, statusFilter, conversationPage],
    queryFn: () =>
      api.crm.collabMonitorConversations(
        instanceFilter === "all" ? undefined : instanceFilter,
        { limit: CONVERSATIONS_PAGE_SIZE, offset: conversationPage * CONVERSATIONS_PAGE_SIZE },
        statusFilter
      ),
  });
  const conversations = conversationsPage?.items ?? [];

  const { data: settings } = useQuery({
    queryKey: ["collab-monitor-settings"],
    queryFn: () => api.crm.collabMonitorGetSettings(),
  });
  const staleThresholdHours = settings?.stale_threshold_hours ?? 3;

  const updateThresholdMutation = useMutation({
    mutationFn: (hours: number) => api.crm.collabMonitorUpdateSettings(hours),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["collab-monitor-settings"] }),
  });

  function handleCollaboratorsChanged() {
    queryClient.invalidateQueries({ queryKey: ["collab-monitor-conversations"] });
    queryClient.invalidateQueries({ queryKey: ["collab-monitor-instances-filter"] });
  }

  const { data: allInstances } = useQuery({
    queryKey: ["collab-monitor-instances-filter"],
    queryFn: () => api.crm.collabMonitorList(),
  });

  const collaborators = useMemo(
    () =>
      (allInstances ?? []).map((i) => ({
        instance_id: i.instance_id,
        name: i.collaborator_name || i.instance_id,
      })),
    [allInstances]
  );

  const selectedConversation = useMemo(
    () => conversations.find((c) => c.lead_id === selectedLeadId) ?? null,
    [conversations, selectedLeadId]
  );

  const { data: messagesData, isLoading: messagesLoading } = useQuery({
    queryKey: ["lead-messages", selectedLeadId, messagePage],
    queryFn: () =>
      api.assistenteIA.mensagens(selectedLeadId as number, false, {
        limit: MESSAGES_PAGE_SIZE,
        offset: messagePage * MESSAGES_PAGE_SIZE,
      }),
    enabled: !!selectedLeadId,
  });

  const orderedMessages = useMemo(() => {
    const messages = messagesData?.messages ?? [];
    return [...messages].reverse();
  }, [messagesData]);

  return (
    <div className="h-[calc(100vh-3rem)] flex flex-col">
      <div className="border-b bg-background px-4 h-14 flex items-center gap-3 shrink-0">
        <Users className="h-5 w-5 text-primary" />
        <h1 className="font-semibold">Monitoramento</h1>
        <span className="text-xs text-muted-foreground">
          Conversas capturadas dos WhatsApps de colaboradores monitorados
        </span>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-muted-foreground whitespace-nowrap">Alertar sem resposta após</span>
          <Select
            value={String(staleThresholdHours)}
            onValueChange={(value) => updateThresholdMutation.mutate(Number(value))}
          >
            <SelectTrigger className="h-9 text-sm w-20">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STALE_THRESHOLD_OPTIONS.map((hours) => (
                <SelectItem key={hours} value={String(hours)}>
                  {hours}h
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setManageOpen(true)}
          >
            <UserCog className="h-4 w-4 mr-1.5" />
            Gerenciar colaboradores
          </Button>
        </div>
      </div>

      <ManageCollaboratorsDialog
        open={manageOpen}
        onOpenChange={setManageOpen}
        onChanged={handleCollaboratorsChanged}
      />

      <div className="flex-1 flex min-h-0">
        {/* Coluna esquerda: lista de conversas */}
        <div className="w-full max-w-xs border-r flex flex-col shrink-0">
          <div className="p-2 border-b space-y-2">
            <Select value={instanceFilter} onValueChange={handleInstanceFilterChange}>
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder="Filtrar por colaborador" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os colaboradores</SelectItem>
                {collaborators.map((c) => (
                  <SelectItem key={c.instance_id} value={c.instance_id}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={handleStatusFilterChange}>
              <SelectTrigger className="h-9 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="active">Só ativas</SelectItem>
                <SelectItem value="all">Todo histórico</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex-1 overflow-y-auto min-w-0">
            {conversationsLoading && (
              <div className="p-3 space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            )}

            {!conversationsLoading && conversations.length === 0 && (
              <div className="p-6 text-center text-sm text-muted-foreground">
                Nenhuma conversa monitorada ainda.
              </div>
            )}

            {!conversationsLoading &&
              conversations.map((c) => (
                <ConversationListItem
                  key={c.lead_id}
                  conversation={c}
                  active={c.lead_id === selectedLeadId}
                  onSelect={() => handleSelectConversation(c.lead_id)}
                  staleThresholdHours={staleThresholdHours}
                />
              ))}
          </div>

          {!conversationsLoading && (conversations.length > 0 || conversationPage > 0) && (
            <Pager
              page={conversationPage}
              hasMore={conversationsPage?.has_more ?? false}
              onPrev={() => setConversationPage((p) => Math.max(0, p - 1))}
              onNext={() => setConversationPage((p) => p + 1)}
              className="border-t shrink-0"
            />
          )}
        </div>

        {/* Coluna direita: conversa selecionada */}
        <div className="flex-1 flex flex-col min-w-0">
          {!selectedConversation && (
            <div className="flex-1 flex flex-col items-center justify-center gap-2 text-muted-foreground">
              <MessageSquareOff className="h-10 w-10" />
              <p className="text-sm">Selecione uma conversa à esquerda</p>
            </div>
          )}

          {selectedConversation && (
            <>
              <div className="border-b px-4 h-14 flex items-center gap-2.5 shrink-0">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="text-xs">
                    {getInitials(selectedConversation.contact_name)}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">
                    {selectedConversation.contact_name || selectedConversation.phone || "Sem nome"}
                  </p>
                  <p className="text-xs text-muted-foreground truncate flex items-center gap-1">
                    <Phone className="h-3 w-3" />
                    {selectedConversation.phone || "—"}
                    {selectedConversation.collaborator_name && (
                      <span> · monitorado por {selectedConversation.collaborator_name}</span>
                    )}
                  </p>
                </div>
              </div>

              {selectedConversation.category && (
                <div className="border-b px-4 py-1.5 flex items-center gap-2 text-xs shrink-0 bg-muted/40">
                  <span
                    className="h-1.5 w-1.5 rounded-full shrink-0"
                    style={{ backgroundColor: STAGE_LOOKUP.get(selectedConversation.category)?.color }}
                  />
                  <span className="text-muted-foreground">
                    Estágio classificado pela IA:{" "}
                    <span className="font-medium text-foreground">
                      {STAGE_LOOKUP.get(selectedConversation.category)?.label ?? selectedConversation.category}
                    </span>
                  </span>
                  {isAwaitingResponse(selectedConversation, staleThresholdHours) && selectedConversation.last_message_at && (
                    <span className="ml-auto flex items-center gap-1 text-destructive font-medium shrink-0">
                      <AlertTriangle className="h-3 w-3" />
                      Sem resposta há {hoursSince(selectedConversation.last_message_at)}h
                    </span>
                  )}
                </div>
              )}

              {!messagesLoading && (orderedMessages.length > 0 || messagePage > 0) && (
                <Pager
                  page={messagePage}
                  hasMore={messagesData?.has_more ?? false}
                  onPrev={() => setMessagePage((p) => Math.max(0, p - 1))}
                  onNext={() => setMessagePage((p) => p + 1)}
                  className="border-b shrink-0"
                />
              )}

              <div className="flex-1 overflow-y-auto min-w-0">
                <div className="p-4 space-y-2">
                  {messagesLoading && (
                    <div className="space-y-2">
                      <Skeleton className="h-10 w-2/3" />
                      <Skeleton className="h-10 w-1/2 ml-auto" />
                      <Skeleton className="h-10 w-2/3" />
                    </div>
                  )}

                  {!messagesLoading && orderedMessages.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      Nenhuma mensagem registrada para esta conversa.
                    </p>
                  )}

                  {!messagesLoading &&
                    orderedMessages.map((m) => <MessageBubble key={m.id} message={m} />)}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
