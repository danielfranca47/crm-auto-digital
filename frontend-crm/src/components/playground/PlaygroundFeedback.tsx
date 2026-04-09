import { Download, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { PlaygroundSession } from "./PlaygroundConfigModal";
import type { ChatMessage } from "./MessageBubble";

export type FeedbackTag = "tom" | "qualificação" | "guardrail" | "prompt" | "outro";

export interface FeedbackItem {
  messageId: string;
  messagePreview: string;
  notes: string;
  tags: FeedbackTag[];
}

const TAG_LABELS: Record<FeedbackTag, string> = {
  tom: "Tom",
  qualificação: "Qualificação",
  guardrail: "Guardrail",
  prompt: "Prompt",
  outro: "Outro",
};

const TAG_COLORS: Record<FeedbackTag, string> = {
  tom: "bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-950 dark:text-blue-300",
  qualificação: "bg-purple-100 text-purple-700 border-purple-300 dark:bg-purple-950 dark:text-purple-300",
  guardrail: "bg-red-100 text-red-700 border-red-300 dark:bg-red-950 dark:text-red-300",
  prompt: "bg-green-100 text-green-700 border-green-300 dark:bg-green-950 dark:text-green-300",
  outro: "bg-gray-100 text-gray-700 border-gray-300 dark:bg-gray-800 dark:text-gray-300",
};

interface PlaygroundFeedbackProps {
  session: PlaygroundSession;
  feedbacks: FeedbackItem[];
  messages: ChatMessage[];
  onUpdateNotes: (messageId: string, notes: string) => void;
  onToggleTag: (messageId: string, tag: FeedbackTag) => void;
  onRemove: (messageId: string) => void;
}

export function PlaygroundFeedback({
  session,
  feedbacks,
  messages,
  onUpdateNotes,
  onToggleTag,
  onRemove,
}: PlaygroundFeedbackProps) {
  function exportMarkdown() {
    const lines: string[] = [];
    const date = new Date(session.startedAt).toLocaleString("pt-PT");

    lines.push(`# Playground — Sessão ${date}`);
    lines.push("");
    lines.push("## Configuração");
    lines.push(`- **AI Profile:** ${session.aiProfileName} (ID: ${session.aiProfileId})`);
    if (session.scenarioContext) {
      lines.push(`- **Contexto:** ${session.scenarioContext}`);
    }
    lines.push(`- **Lead ID (sandbox):** ${session.leadId ?? "—"}`);
    lines.push("");
    lines.push("## Conversa");
    lines.push("");

    for (const msg of messages) {
      const time = new Date(msg.timestamp).toLocaleTimeString("pt-PT", {
        hour: "2-digit",
        minute: "2-digit",
      });
      const who = msg.role === "lead" ? "**[Lead]**" : "**[Bot]**";
      lines.push(`${who} ${time}`);
      lines.push(`> ${msg.text.replace(/\n/g, "\n> ")}`);
      if (msg.decisionTrace) {
        const t = msg.decisionTrace;
        lines.push(`>`);
        lines.push(
          `> _Trace: mother_route=${t.mother_route ?? "—"}, effective=${t.effective_route ?? "—"}, confidence=${
            msg.confidence != null ? Math.round(msg.confidence * 100) + "%" : "—"
          }, guardrails=[${(msg.guardrails ?? []).join(", ")}]_`
        );
      }
      lines.push("");
    }

    if (feedbacks.length > 0) {
      lines.push("## Feedbacks Anotados");
      lines.push("");
      feedbacks.forEach((fb, i) => {
        lines.push(`### ${i + 1}. "${fb.messagePreview}"`);
        if (fb.tags.length > 0) {
          lines.push(`**Tags:** ${fb.tags.map((t) => TAG_LABELS[t]).join(", ")}`);
        }
        lines.push(`**Notas:** ${fb.notes || "_(sem notas)_"}`);
        lines.push("");
      });
    }

    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const dateSlug = new Date(session.startedAt)
      .toISOString()
      .slice(0, 16)
      .replace("T", "_")
      .replace(":", "-");
    a.download = `playground-${dateSlug}-output.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header do painel */}
      <div className="px-4 py-3 border-b flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">Feedback</h3>
          <p className="text-xs text-muted-foreground">
            {feedbacks.length === 0
              ? "Clique no ícone 🔖 em respostas do bot para anotar"
              : `${feedbacks.length} mensage${feedbacks.length > 1 ? "ns" : "m"} selecionada${feedbacks.length > 1 ? "s" : ""}`}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={exportMarkdown}
          className="gap-1.5"
        >
          <Download className="h-3.5 w-3.5" />
          Exportar .md
        </Button>
      </div>

      {/* Lista de feedbacks */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {feedbacks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground text-sm px-6 space-y-2">
            <span className="text-3xl">🔖</span>
            <p>Nenhuma mensagem selecionada ainda.</p>
            <p className="text-xs">
              Passe o cursor sobre uma resposta do bot e clique no ícone de marcador para adicionar ao feedback.
            </p>
          </div>
        ) : (
          feedbacks.map((fb) => (
            <Card key={fb.messageId} className="border-amber-200 dark:border-amber-800">
              <CardContent className="p-3 space-y-2">
                {/* Preview da mensagem + botão remover */}
                <div className="flex items-start gap-2">
                  <p className="flex-1 text-xs text-muted-foreground italic line-clamp-2">
                    "{fb.messagePreview}"
                  </p>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5 shrink-0 text-muted-foreground hover:text-destructive"
                    onClick={() => onRemove(fb.messageId)}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>

                {/* Tags */}
                <div className="flex flex-wrap gap-1">
                  {(Object.keys(TAG_LABELS) as FeedbackTag[]).map((tag) => {
                    const active = fb.tags.includes(tag);
                    return (
                      <button
                        key={tag}
                        onClick={() => onToggleTag(fb.messageId, tag)}
                        className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${
                          active
                            ? TAG_COLORS[tag]
                            : "bg-transparent text-muted-foreground border-border hover:border-foreground"
                        }`}
                      >
                        {TAG_LABELS[tag]}
                      </button>
                    );
                  })}
                </div>

                {/* Notas */}
                <Textarea
                  value={fb.notes}
                  onChange={(e) => onUpdateNotes(fb.messageId, e.target.value)}
                  placeholder="Anote o que observou nesta resposta…"
                  rows={3}
                  className="resize-none text-xs"
                />
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
