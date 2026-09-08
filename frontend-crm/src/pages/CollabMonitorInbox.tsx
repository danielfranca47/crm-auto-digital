import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquareOff, Phone, Users, UserCog } from "lucide-react";
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
import { api, type CollabMonitorConversation, type LeadMessage } from "@/services/api";

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
}: {
  conversation: CollabMonitorConversation;
  active: boolean;
  onSelect: () => void;
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
  const [selectedLeadId, setSelectedLeadId] = useState<number | null>(null);
  const [manageOpen, setManageOpen] = useState(false);

  const { data: conversations, isLoading: conversationsLoading } = useQuery({
    queryKey: ["collab-monitor-conversations", instanceFilter],
    queryFn: () =>
      api.crm.collabMonitorConversations(instanceFilter === "all" ? undefined : instanceFilter),
  });

  function handleCollaboratorsChanged() {
    queryClient.invalidateQueries({ queryKey: ["collab-monitor-conversations"] });
  }

  const collaborators = useMemo(() => {
    const seen = new Map<string, string>();
    for (const c of conversations ?? []) {
      if (!seen.has(c.instance_id)) {
        seen.set(c.instance_id, c.collaborator_name || c.instance_id);
      }
    }
    return Array.from(seen.entries()).map(([instance_id, name]) => ({ instance_id, name }));
  }, [conversations]);

  const selectedConversation = useMemo(
    () => (conversations ?? []).find((c) => c.lead_id === selectedLeadId) ?? null,
    [conversations, selectedLeadId]
  );

  const { data: messagesData, isLoading: messagesLoading } = useQuery({
    queryKey: ["lead-messages", selectedLeadId],
    queryFn: () => api.assistenteIA.mensagens(selectedLeadId as number, false),
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
        <Button
          size="sm"
          variant="outline"
          className="ml-auto"
          onClick={() => setManageOpen(true)}
        >
          <UserCog className="h-4 w-4 mr-1.5" />
          Gerenciar colaboradores
        </Button>
      </div>

      <ManageCollaboratorsDialog
        open={manageOpen}
        onOpenChange={setManageOpen}
        onChanged={handleCollaboratorsChanged}
      />

      <div className="flex-1 flex min-h-0">
        {/* Coluna esquerda: lista de conversas */}
        <div className="w-full max-w-xs border-r flex flex-col shrink-0">
          <div className="p-2 border-b">
            <Select value={instanceFilter} onValueChange={setInstanceFilter}>
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
          </div>

          <div className="flex-1 overflow-y-auto min-w-0">
            {conversationsLoading && (
              <div className="p-3 space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            )}

            {!conversationsLoading && (conversations ?? []).length === 0 && (
              <div className="p-6 text-center text-sm text-muted-foreground">
                Nenhuma conversa monitorada ainda.
              </div>
            )}

            {!conversationsLoading &&
              (conversations ?? []).map((c) => (
                <ConversationListItem
                  key={c.lead_id}
                  conversation={c}
                  active={c.lead_id === selectedLeadId}
                  onSelect={() => setSelectedLeadId(c.lead_id)}
                />
              ))}
          </div>
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
