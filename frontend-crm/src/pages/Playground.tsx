import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/hooks/use-toast";
import { RefreshCw } from "lucide-react";
import { api } from "@/services/api";
import { PlaygroundConfigModal, type PlaygroundSession } from "@/components/playground/PlaygroundConfigModal";
import { PlaygroundChat } from "@/components/playground/PlaygroundChat";
import { PlaygroundFeedback, type FeedbackItem, type FeedbackTag } from "@/components/playground/PlaygroundFeedback";
import { type ChatMessage } from "@/components/playground/MessageBubble";
import { type AgentReportEntry } from "@/components/playground/FeedbackAssistant";

export default function Playground() {
  const [session, setSession] = useState<PlaygroundSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
  const [agentReport, setAgentReport] = useState<AgentReportEntry[]>([]);
  const [loading, setLoading] = useState(false);

  // ── Handlers de sessão ────────────────────────────────────────────────────

  function handleStart(newSession: PlaygroundSession) {
    setSession(newSession);
    setMessages([]);
    setFeedbacks([]);
    setAgentReport([]);
  }

  function handleNewSession() {
    setSession(null);
    setMessages([]);
    setFeedbacks([]);
    setAgentReport([]);
  }

  // ── Enviar mensagem ────────────────────────────────────────────────────────

  const handleSend = useCallback(
    async (text: string) => {
      if (!session) return;

      // Adiciona mensagem do lead imediatamente
      const leadMsgId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        {
          id: leadMsgId,
          role: "lead",
          text,
          timestamp: new Date().toISOString(),
          selectedForFeedback: false,
        },
      ]);

      setLoading(true);
      try {
        const res = await api.playground.chat({
          ai_profile_id: session.aiProfileId,
          message: text,
          lead_id: session.leadId,
        });

        // Atualiza o lead_id na sessão (na primeira mensagem vem o id criado)
        if (!session.leadId) {
          setSession((s) => s ? { ...s, leadId: res.lead_id } : s);
        }

        // Adiciona resposta do bot
        const botMsgId = crypto.randomUUID();
        setMessages((prev) => [
          ...prev,
          {
            id: botMsgId,
            role: "bot",
            text: res.message_to_send,
            timestamp: new Date().toISOString(),
            decisionTrace: res.decision_trace,
            motherRoute: res.decision_trace?.mother_route ?? null,
            confidence: res.mother_decision?.confidence,
            guardrails: res.decision_trace?.guardrails_applied ?? [],
            selectedForFeedback: false,
          },
        ]);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Erro ao chamar o playground";
        toast({ title: "Erro", description: msg, variant: "destructive" });
      } finally {
        setLoading(false);
      }
    },
    [session]
  );

  // ── Handlers de feedback ──────────────────────────────────────────────────

  const handleToggleFeedback = useCallback((messageId: string) => {
    setMessages((prev) => {
      const updated = prev.map((m) =>
        m.id === messageId ? { ...m, selectedForFeedback: !m.selectedForFeedback } : m
      );
      // Calcula o novo estado de feedbacks baseado no estado atualizado
      const msg = prev.find((m) => m.id === messageId);
      const isNowSelected = updated.find((m) => m.id === messageId)?.selectedForFeedback ?? false;

      setFeedbacks((prevFb) => {
        if (!isNowSelected) {
          return prevFb.filter((f) => f.messageId !== messageId);
        }
        if (prevFb.find((f) => f.messageId === messageId)) return prevFb;
        if (!msg) return prevFb;
        return [
          ...prevFb,
          {
            messageId,
            messagePreview: msg.text.slice(0, 80) + (msg.text.length > 80 ? "…" : ""),
            notes: "",
            tags: [],
          },
        ];
      });

      return updated;
    });
  }, []);

  const handleUpdateNotes = useCallback((messageId: string, notes: string) => {
    setFeedbacks((prev) =>
      prev.map((f) => (f.messageId === messageId ? { ...f, notes } : f))
    );
  }, []);

  const handleToggleTag = useCallback((messageId: string, tag: FeedbackTag) => {
    setFeedbacks((prev) =>
      prev.map((f) => {
        if (f.messageId !== messageId) return f;
        const hasTag = f.tags.includes(tag);
        return {
          ...f,
          tags: hasTag ? f.tags.filter((t) => t !== tag) : [...f.tags, tag],
        };
      })
    );
  }, []);

  const handleRemoveFeedback = useCallback((messageId: string) => {
    setFeedbacks((prev) => prev.filter((f) => f.messageId !== messageId));
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId ? { ...m, selectedForFeedback: false } : m
      )
    );
  }, []);

  const handleAgentReportEntry = useCallback((entry: AgentReportEntry) => {
    setAgentReport((prev) => [...prev, entry]);
  }, []);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      {/* Modal de configuração */}
      <PlaygroundConfigModal open={!session} onStart={handleStart} />

      {/* Layout principal — só visível depois da sessão iniciada */}
      {session && (
        <div className="flex flex-col h-full">
          {/* Barra superior */}
          <div className="flex items-center gap-3 px-4 py-2 border-b bg-background shrink-0">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <span className="text-sm font-medium truncate">{session.aiProfileName}</span>
              {session.leadId && (
                <Badge variant="outline" className="text-xs shrink-0">
                  lead #{session.leadId}
                </Badge>
              )}
              {session.scenarioContext && (
                <span className="text-xs text-muted-foreground truncate hidden sm:block">
                  · {session.scenarioContext}
                </span>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNewSession}
              className="gap-1.5 shrink-0"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Nova sessão
            </Button>
          </div>

          {/* Split view */}
          <div className="flex flex-1 min-h-0">
            {/* Painel esquerdo — Chat */}
            <div className="flex flex-col w-1/2 border-r min-h-0">
              <div className="px-4 py-2 border-b bg-muted/30 shrink-0">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Conversa simulada
                </h3>
              </div>
              <div className="flex-1 min-h-0">
                <PlaygroundChat
                  messages={messages}
                  loading={loading}
                  onSend={handleSend}
                  onToggleFeedback={handleToggleFeedback}
                />
              </div>
            </div>

            {/* Painel direito — Feedback + Assistente */}
            <div className="flex flex-col w-1/2 min-h-0">
              <PlaygroundFeedback
                session={session}
                feedbacks={feedbacks}
                messages={messages}
                agentReportEntries={agentReport}
                onUpdateNotes={handleUpdateNotes}
                onToggleTag={handleToggleTag}
                onRemove={handleRemoveFeedback}
                onAgentReportEntry={handleAgentReportEntry}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
