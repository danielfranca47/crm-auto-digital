import { useState, useCallback, useEffect, type Dispatch, type SetStateAction } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/hooks/use-toast";
import { RefreshCw, ArrowDownToLine, ArrowUpFromLine } from "lucide-react";
import { api, type PlaygroundChatResponse, type PlaygroundAutoItem } from "@/services/api";
import { API_BASE } from "@/lib/api-client";
import { PlaygroundConfigModal, type PlaygroundSession } from "@/components/playground/PlaygroundConfigModal";
import { PlaygroundChat } from "@/components/playground/PlaygroundChat";
import { PlaygroundFeedback, type FeedbackItem, type FeedbackTag } from "@/components/playground/PlaygroundFeedback";
import { type ChatMessage, type RatingValue } from "@/components/playground/MessageBubble";
import { type AgentReportEntry } from "@/components/playground/FeedbackAssistant";

function buildBotMessage(
  text: string,
  res: PlaygroundChatResponse,
  opts: { isFirst: boolean; totalParts: number }
): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role: "bot",
    text,
    timestamp: new Date().toISOString(),
    ...(opts.isFirst ? {
      decisionTrace: res.decision_trace,
      motherRoute: res.decision_trace?.mother_route ?? null,
      confidence: res.mother_decision?.confidence,
      guardrails: res.decision_trace?.guardrails_applied ?? [],
      preMediaItems: res.pre_send_media ?? [],
      humanizationPreview: {
        delay_s: res.simulated_delay_seconds ?? 0,
        typing_s: res.typing_seconds ?? 0,
        total_parts: opts.totalParts,
      },
    } : {}),
    selectedForFeedback: false,
  };
}

async function revealExtraParts(
  extraParts: string[],
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  setLoading: Dispatch<SetStateAction<boolean>>
) {
  for (const part of extraParts) {
    setLoading(true);
    const delayMs = Math.min(Math.max(part.length * 40, 500), 1500);
    await new Promise<void>((r) => setTimeout(r, delayMs));
    setLoading(false);
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "bot",
        text: part,
        timestamp: new Date().toISOString(),
        selectedForFeedback: false,
      },
    ]);
  }
}

async function revealAutoMessages(
  autoItems: PlaygroundAutoItem[],
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  setLoading: Dispatch<SetStateAction<boolean>>
) {
  for (const item of autoItems) {
    setLoading(true);
    await new Promise<void>((r) => setTimeout(r, 600));
    setLoading(false);
    if (item.type === "media") {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "bot",
          text: "",
          timestamp: new Date().toISOString(),
          isAutoMessage: true,
          preMediaItems: [{ media_url: item.media_url, media_type: item.media_type, send_order: 0 }],
          selectedForFeedback: false,
        },
      ]);
    } else {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "bot",
          text: item.content,
          timestamp: new Date().toISOString(),
          isAutoMessage: true,
          selectedForFeedback: false,
        },
      ]);
    }
  }
}

function resolveAutoItems(res: PlaygroundChatResponse): PlaygroundAutoItem[] {
  if (res.auto_items?.length) return res.auto_items;
  return (res.auto_messages ?? []).map((m) => ({ type: "text" as const, content: m }));
}

function appendPhaseAdvances(
  phaseAdvances: string[],
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
) {
  if (!phaseAdvances.length) return;
  setMessages((prev) => [
    ...prev,
    ...phaseAdvances.map((label) => ({
      id: crypto.randomUUID(),
      role: "bot" as const,
      text: label,
      timestamp: new Date().toISOString(),
      isPhaseAdvance: true,
      selectedForFeedback: false,
    })),
  ]);
}

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

  // ── Outbound: dispara abertura automática do bot ao iniciar sessão ─────────
  useEffect(() => {
    if (!session || session.scenarioType !== "outbound" || messages.length > 0) return;
    let cancelled = false;

    async function fireOpener() {
      if (!session) return;
      setLoading(true);
      try {
        const res = await api.playground.chat({
          ai_profile_id: session.aiProfileId,
          message: "",
          lead_id: null,
          scenario_type: "outbound",
          is_opener: true,
        });

        if (cancelled) return;

        setSession((s) => s ? { ...s, leadId: res.lead_id } : s);

        const parts = res.message_parts?.length ? res.message_parts : [res.message_to_send];
        const autoItems0 = resolveAutoItems(res);
        if (res.suppress_llm_response) {
          if (autoItems0.length) await revealAutoMessages(autoItems0, setMessages, setLoading);
        } else if (res.phase_trigger_fired && autoItems0.length) {
          await revealAutoMessages(autoItems0, setMessages, setLoading);
          setMessages((prev) => [...prev, buildBotMessage(parts[0], res, { isFirst: true, totalParts: parts.length })]);
          if (parts.length > 1) await revealExtraParts(parts.slice(1), setMessages, setLoading);
        } else {
          setMessages([buildBotMessage(parts[0], res, { isFirst: true, totalParts: parts.length })]);
          if (parts.length > 1) await revealExtraParts(parts.slice(1), setMessages, setLoading);
          if (autoItems0.length) await revealAutoMessages(autoItems0, setMessages, setLoading);
        }
        appendPhaseAdvances(res.phase_advances ?? [], setMessages);
      } catch (err: unknown) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : "Erro ao obter abertura outbound";
        toast({ title: "Erro", description: msg, variant: "destructive" });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fireOpener();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.aiProfileId, session?.scenarioType]);

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
          scenario_type: session.scenarioType,
        });

        // Atualiza o lead_id na sessão (na primeira mensagem vem o id criado)
        if (!session.leadId) {
          setSession((s) => s ? { ...s, leadId: res.lead_id } : s);
        }

        // Adiciona resposta do bot
        const parts = res.message_parts?.length ? res.message_parts : [res.message_to_send];
        const autoItems = resolveAutoItems(res);
        if (res.suppress_llm_response) {
          // LLM suprimida pelo gatilho: apenas mensagens automáticas, sem turno da LLM
          if (autoItems.length) await revealAutoMessages(autoItems, setMessages, setLoading);
        } else if (res.phase_trigger_fired && autoItems.length) {
          // phase_trigger: mensagens automáticas PRIMEIRO, depois LLM
          await revealAutoMessages(autoItems, setMessages, setLoading);
          setMessages((prev) => [...prev, buildBotMessage(parts[0], res, { isFirst: true, totalParts: parts.length })]);
          if (parts.length > 1) await revealExtraParts(parts.slice(1), setMessages, setLoading);
        } else {
          // ordem normal: LLM primeiro, depois auto items
          setMessages((prev) => [...prev, buildBotMessage(parts[0], res, { isFirst: true, totalParts: parts.length })]);
          if (parts.length > 1) await revealExtraParts(parts.slice(1), setMessages, setLoading);
          if (autoItems.length) await revealAutoMessages(autoItems, setMessages, setLoading);
        }
        appendPhaseAdvances(res.phase_advances ?? [], setMessages);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Erro ao chamar o playground";
        toast({ title: "Erro", description: msg, variant: "destructive" });
      } finally {
        setLoading(false);
      }
    },
    [session]
  );

  // ── Enviar áudio gravado no playground ────────────────────────────────────

  const handleSendAudio = useCallback(
    async (blob: Blob) => {
      if (!session) return;

      setLoading(true);
      try {
        const { filename, audio_url } = await api.playground.uploadAudio(blob);
        const audioPlayerUrl = `${API_BASE}${audio_url.replace(/^\/api/, "")}`;

        // Bolha do lead com player reproduzível
        const leadMsgId = crypto.randomUUID();
        setMessages((prev) => [
          ...prev,
          {
            id: leadMsgId,
            role: "lead",
            text: "[Áudio gravado]",
            isAudioMessage: true,
            audioUrl: audioPlayerUrl,
            timestamp: new Date().toISOString(),
            selectedForFeedback: false,
          },
        ]);

        const res = await api.playground.chat({
          ai_profile_id: session.aiProfileId,
          message: "",
          lead_id: session.leadId,
          scenario_type: session.scenarioType,
          message_type: "audio",
          audio_filename: filename,
        });

        if (!session.leadId) {
          setSession((s) => s ? { ...s, leadId: res.lead_id } : s);
        }

        // Atualiza bolha do lead com transcrição (se o backend conseguiu transcrever)
        if (res.transcription) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === leadMsgId ? { ...m, transcription: res.transcription ?? undefined } : m
            )
          );
        }

        const parts = res.message_parts?.length ? res.message_parts : [res.message_to_send];
        const autoItems = resolveAutoItems(res);
        if (res.suppress_llm_response) {
          if (autoItems.length) await revealAutoMessages(autoItems, setMessages, setLoading);
        } else if (res.phase_trigger_fired && autoItems.length) {
          await revealAutoMessages(autoItems, setMessages, setLoading);
          setMessages((prev) => [...prev, buildBotMessage(parts[0], res, { isFirst: true, totalParts: parts.length })]);
          if (parts.length > 1) await revealExtraParts(parts.slice(1), setMessages, setLoading);
        } else {
          setMessages((prev) => [...prev, buildBotMessage(parts[0], res, { isFirst: true, totalParts: parts.length })]);
          if (parts.length > 1) await revealExtraParts(parts.slice(1), setMessages, setLoading);
          if (autoItems.length) await revealAutoMessages(autoItems, setMessages, setLoading);
        }
        appendPhaseAdvances(res.phase_advances ?? [], setMessages);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Erro ao enviar áudio";
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

  // ── Rating de treino ──────────────────────────────────────────────────────

  const handleRate = useCallback(
    async (messageId: string, rating: RatingValue, comment: string) => {
      if (!session) return;

      // Marcar como pending
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, ratingPending: true } : m))
      );

      const msg = messages.find((m) => m.id === messageId);
      const trace = msg?.decisionTrace;

      // Última mensagem do lead antes desta resposta do bot
      const msgIndex = messages.findIndex((m) => m.id === messageId);
      const prevLeadMsg = messages
        .slice(0, msgIndex)
        .reverse()
        .find((m) => m.role === "lead");

      try {
        await api.playground.training({
          ai_profile_id: session.aiProfileId,
          lead_id: session.leadId ?? null,
          agent_mode: trace?.agent_mode ?? null,
          phase: trace?.effective_route ?? trace?.mother_route ?? null,
          mother_route: trace?.mother_route ?? null,
          lead_message: prevLeadMsg?.text ?? null,
          bot_message: msg?.text ?? "",
          rating,
          comment: comment || null,
        });

        setMessages((prev) =>
          prev.map((m) =>
            m.id === messageId
              ? { ...m, rating, ratingComment: comment, ratingPending: false }
              : m
          )
        );
        toast({ title: "Avaliação guardada", description: "O bot aprenderá com este exemplo." });
      } catch {
        setMessages((prev) =>
          prev.map((m) => (m.id === messageId ? { ...m, ratingPending: false } : m))
        );
        toast({ title: "Erro ao guardar avaliação", variant: "destructive" });
      }
    },
    [session, messages]
  );

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
              <Badge
                variant="outline"
                className={`text-xs shrink-0 gap-1 ${
                  session.scenarioType === "outbound"
                    ? "border-amber-500/50 text-amber-600"
                    : "border-blue-500/50 text-blue-600"
                }`}
              >
                {session.scenarioType === "outbound" ? (
                  <ArrowUpFromLine className="h-3 w-3" />
                ) : (
                  <ArrowDownToLine className="h-3 w-3" />
                )}
                {session.scenarioType}
              </Badge>
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
                  scenarioType={session.scenarioType}
                  audioEnabled={session.profileSnapshot.audio_transcription_enabled ?? false}
                  onSend={handleSend}
                  onSendAudio={handleSendAudio}
                  onToggleFeedback={handleToggleFeedback}
                  onRate={handleRate}
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
