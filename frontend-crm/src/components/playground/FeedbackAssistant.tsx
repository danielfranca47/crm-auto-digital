import { useRef, useState, KeyboardEvent } from "react";
import { Loader2, Send, CheckCircle, XCircle, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/hooks/use-toast";
import {
  api,
  type FeedbackAssistPreviousAttempt,
  type AiProfilePayload,
} from "@/services/api";
import type { PlaygroundSession } from "./PlaygroundConfigModal";
import type { FeedbackItem } from "./PlaygroundFeedback";
import type { ChatMessage } from "./MessageBubble";

// ── Tipos internos ────────────────────────────────────────────────────────────

interface ProposedUpdate {
  fieldsToUpdate: Record<string, unknown>;
  fieldsCurrentValues: Record<string, unknown>;
  confirmed: boolean | null; // null=pendente, true=aplicado, false=ignorado
}

interface AssistantMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  proposedUpdate?: ProposedUpdate;
  isExportRequired?: boolean;
}

export interface AgentReportEntry {
  attemptNumber: number;
  timestamp: string;
  userQuestion: string;
  analysis: string;
  fieldsChanged: Record<string, { from: unknown; to: unknown }> | null;
  outcome: "applied" | "declined" | "no_change" | "export_required";
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface FeedbackAssistantProps {
  session: PlaygroundSession;
  feedbacks: FeedbackItem[];
  messages: ChatMessage[];
  onAgentReportEntry: (entry: AgentReportEntry) => void;
  onExportRequested: () => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatFieldValue(val: unknown): string {
  if (val === null || val === undefined) return "—";
  if (Array.isArray(val)) return val.join(", ") || "—";
  if (typeof val === "object") return JSON.stringify(val);
  return String(val);
}

// ── Componente ────────────────────────────────────────────────────────────────

export function FeedbackAssistant({
  session,
  feedbacks,
  messages,
  onAgentReportEntry,
  onExportRequested,
}: FeedbackAssistantProps) {
  const [chatHistory, setChatHistory] = useState<AssistantMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [attemptNumber, setAttemptNumber] = useState(1);
  const [previousAttempts, setPreviousAttempts] = useState<FeedbackAssistPreviousAttempt[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  function scrollToBottom() {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: AssistantMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    setChatHistory((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    scrollToBottom();

    try {
      const res = await api.playground.feedbackAssist({
        ai_profile_id: session.aiProfileId,
        conversation_messages: messages.map((m) => ({
          role: m.role,
          text: m.text,
          timestamp: m.timestamp,
          motherRoute: m.motherRoute ?? null,
          confidence: m.confidence,
          guardrails: m.guardrails ?? [],
          decisionTrace: m.decisionTrace,
        })),
        feedback_items: feedbacks.map((f) => ({
          messageId: f.messageId,
          messagePreview: f.messagePreview,
          notes: f.notes,
          tags: f.tags,
        })),
        user_question: text,
        attempt_number: attemptNumber,
        previous_attempts: previousAttempts,
      });

      const assistantMsg: AssistantMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: res.explanation,
        timestamp: new Date().toISOString(),
        isExportRequired: res.action === "export_required",
        proposedUpdate:
          res.action === "update_profile" && res.fields_to_update
            ? {
                fieldsToUpdate: res.fields_to_update,
                fieldsCurrentValues: res.fields_current_values ?? {},
                confirmed: null,
              }
            : undefined,
      };

      setChatHistory((prev) => [...prev, assistantMsg]);

      // Registar tentativa anterior para contexto futuro
      if (res.action !== "export_required") {
        const prevAttempt: FeedbackAssistPreviousAttempt = {
          attempt_number: attemptNumber,
          user_question: text,
          analysis: res.analysis,
          fields_changed: null,
          outcome: res.action === "update_profile" ? "applied" : "no_change",
          timestamp: new Date().toISOString(),
        };
        setPreviousAttempts((prev) => [...prev, prevAttempt]);
      }

      setAttemptNumber((n) => n + 1);
      scrollToBottom();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao contactar o assistente";
      toast({ title: "Erro", description: msg, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function handleConfirm(msgId: string, fieldsToUpdate: Record<string, unknown>, fieldsCurrentValues: Record<string, unknown>) {
    try {
      await api.core.updateAiProfileMe(fieldsToUpdate as Partial<AiProfilePayload>);

      // Marca como aplicado na bolha
      setChatHistory((prev) =>
        prev.map((m) =>
          m.id === msgId && m.proposedUpdate
            ? { ...m, proposedUpdate: { ...m.proposedUpdate, confirmed: true } }
            : m
        )
      );

      // Registar no agentReport
      const fieldsChanged: Record<string, { from: unknown; to: unknown }> = {};
      for (const [field, newVal] of Object.entries(fieldsToUpdate)) {
        fieldsChanged[field] = { from: fieldsCurrentValues[field], to: newVal };
      }
      onAgentReportEntry({
        attemptNumber: attemptNumber - 1,
        timestamp: new Date().toISOString(),
        userQuestion: chatHistory.findLast((m) => m.role === "user")?.content ?? "",
        analysis: "",
        fieldsChanged,
        outcome: "applied",
      });

      // Atualizar previousAttempts com fields_changed
      setPreviousAttempts((prev) => {
        const updated = [...prev];
        if (updated.length > 0) {
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            fields_changed: fieldsChanged,
            outcome: "applied",
          };
        }
        return updated;
      });

      toast({
        title: "Perfil atualizado",
        description: "Testa novamente no chat para verificar o comportamento.",
      });
    } catch {
      toast({ title: "Erro ao aplicar", description: "Não foi possível atualizar o perfil.", variant: "destructive" });
    }
  }

  function handleDecline(msgId: string) {
    setChatHistory((prev) =>
      prev.map((m) =>
        m.id === msgId && m.proposedUpdate
          ? { ...m, proposedUpdate: { ...m.proposedUpdate, confirmed: false } }
          : m
      )
    );
    onAgentReportEntry({
      attemptNumber: attemptNumber - 1,
      timestamp: new Date().toISOString(),
      userQuestion: chatHistory.findLast((m) => m.role === "user")?.content ?? "",
      analysis: "",
      fieldsChanged: null,
      outcome: "declined",
    });
    setPreviousAttempts((prev) => {
      const updated = [...prev];
      if (updated.length > 0) {
        updated[updated.length - 1] = { ...updated[updated.length - 1], outcome: "declined" };
      }
      return updated;
    });
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* Área de chat */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {chatHistory.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground text-sm px-6 space-y-2">
            <span className="text-3xl">🤖</span>
            <p className="font-medium">Assistente de configuração</p>
            <p className="text-xs">
              Descreva o comportamento que observou. O assistente analisa o perfil
              configurado e sugere ajustes — ou explica se requer correção de código.
            </p>
          </div>
        ) : (
          chatHistory.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div className={`max-w-[85%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col gap-1`}>
                <span className="text-xs text-muted-foreground px-1">
                  {msg.role === "user" ? "Você" : "Assistente"} ·{" "}
                  {new Date(msg.timestamp).toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" })}
                </span>

                {/* Bolha da mensagem */}
                <div
                  className={`rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap break-words ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground rounded-tr-sm"
                      : "bg-muted text-foreground rounded-tl-sm"
                  }`}
                >
                  {msg.content}
                </div>

                {/* Card de alterações sugeridas */}
                {msg.proposedUpdate && msg.proposedUpdate.confirmed === null && (
                  <Card className="border-amber-200 dark:border-amber-800 w-full mt-1">
                    <CardContent className="p-3 space-y-2">
                      <p className="text-xs font-semibold text-amber-700 dark:text-amber-400">
                        Alterações sugeridas no perfil:
                      </p>
                      <div className="space-y-1">
                        {Object.entries(msg.proposedUpdate.fieldsToUpdate).map(([field, newVal]) => (
                          <div key={field} className="grid grid-cols-[1fr_auto_1fr] gap-1 items-center text-xs">
                            <span className="font-mono text-muted-foreground truncate">{field}</span>
                            <span className="text-muted-foreground">→</span>
                            <span className="font-medium text-green-700 dark:text-green-400 truncate">
                              {formatFieldValue(newVal)}
                            </span>
                          </div>
                        ))}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Valor atual:{" "}
                        {Object.entries(msg.proposedUpdate.fieldsCurrentValues)
                          .map(([f, v]) => `${f}=${formatFieldValue(v)}`)
                          .join(", ")}
                      </p>
                      <div className="flex gap-2 pt-1">
                        <Button
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() =>
                            handleConfirm(
                              msg.id,
                              msg.proposedUpdate!.fieldsToUpdate,
                              msg.proposedUpdate!.fieldsCurrentValues
                            )
                          }
                        >
                          Confirmar e aplicar
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-xs"
                          onClick={() => handleDecline(msg.id)}
                        >
                          Ignorar
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Estado após confirmação */}
                {msg.proposedUpdate?.confirmed === true && (
                  <div className="flex items-center gap-1.5 text-xs text-green-600 dark:text-green-400 px-1">
                    <CheckCircle className="h-3.5 w-3.5" />
                    Aplicado — testa novamente no chat para verificar
                  </div>
                )}
                {msg.proposedUpdate?.confirmed === false && (
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground px-1">
                    <XCircle className="h-3.5 w-3.5" />
                    Sugestão ignorada
                  </div>
                )}

                {/* Botão de export quando export_required */}
                {msg.isExportRequired && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-1 gap-1.5 h-7 text-xs"
                    onClick={onExportRequested}
                  >
                    <Download className="h-3 w-3" />
                    Exportar relatório completo
                  </Button>
                )}

                {/* Badge de tentativas */}
                {msg.role === "assistant" && !msg.isExportRequired && (
                  <Badge variant="outline" className="text-xs self-start px-1.5 h-4">
                    tentativa {msg.isExportRequired ? "—" : attemptNumber - 1}/3
                  </Badge>
                )}
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 bg-muted rounded-2xl rounded-tl-sm px-3 py-2 text-sm text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Analisando…
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t p-3 flex gap-2 items-end bg-background">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Descreva o comportamento observado… (Enter para enviar)"
          rows={2}
          className="flex-1 resize-none text-sm min-h-[44px] max-h-28"
          disabled={loading}
        />
        <Button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          size="icon"
          className="shrink-0 h-[44px] w-[44px]"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}
