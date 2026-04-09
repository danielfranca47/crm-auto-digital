import { useState } from "react";
import { Bookmark, BookmarkCheck, ChevronDown, ChevronUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { PlaygroundDecisionTrace } from "@/services/api";

export interface ChatMessage {
  id: string;
  role: "lead" | "bot";
  text: string;
  timestamp: string;
  decisionTrace?: PlaygroundDecisionTrace;
  motherRoute?: string | null;
  confidence?: number;
  guardrails?: string[];
  selectedForFeedback: boolean;
}

interface MessageBubbleProps {
  message: ChatMessage;
  onToggleFeedback: (id: string) => void;
}

export function MessageBubble({ message, onToggleFeedback }: MessageBubbleProps) {
  const [traceOpen, setTraceOpen] = useState(false);
  const isLead = message.role === "lead";

  const time = new Date(message.timestamp).toLocaleTimeString("pt-PT", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className={`flex ${isLead ? "justify-end" : "justify-start"} mb-3 group`}>
      <div className={`flex flex-col max-w-[75%] ${isLead ? "items-end" : "items-start"}`}>
        {/* Rótulo de quem enviou */}
        <span className="text-xs text-muted-foreground mb-1 px-1">
          {isLead ? "Lead" : "Bot"} · {time}
        </span>

        <div className="flex items-start gap-1">
          {/* Botão de feedback — só para mensagens do bot, à esquerda da bolha */}
          {!isLead && (
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
                : message.selectedForFeedback
                ? "bg-amber-50 border-2 border-amber-300 text-foreground rounded-tl-sm dark:bg-amber-950 dark:border-amber-600"
                : "bg-muted text-foreground rounded-tl-sm"
            }`}
          >
            {message.text}
          </div>
        </div>

        {/* Trace colapsável — só para mensagens do bot com trace */}
        {!isLead && message.decisionTrace && (
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
      </div>
    </div>
  );
}
