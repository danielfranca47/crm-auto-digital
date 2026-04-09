import { useEffect, useRef, useState, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Send } from "lucide-react";
import { MessageBubble, type ChatMessage } from "./MessageBubble";

interface PlaygroundChatProps {
  messages: ChatMessage[];
  loading: boolean;
  onSend: (text: string) => void;
  onToggleFeedback: (id: string) => void;
}

export function PlaygroundChat({
  messages,
  loading,
  onSend,
  onToggleFeedback,
}: PlaygroundChatProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  // Scroll automático para o fim quando chega nova mensagem
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSend() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    onSend(text);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Área de mensagens */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            Envie uma mensagem para iniciar a simulação
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onToggleFeedback={onToggleFeedback}
            />
          ))
        )}

        {/* Indicador de digitação do bot */}
        {loading && (
          <div className="flex justify-start mb-3">
            <div className="flex items-center gap-2 bg-muted rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Bot digitando…
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
          placeholder="Digite como se fosse o lead… (Enter para enviar, Shift+Enter para nova linha)"
          rows={2}
          className="flex-1 resize-none text-sm min-h-[44px] max-h-32"
          disabled={loading}
        />
        <Button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          size="icon"
          className="shrink-0 h-[44px] w-[44px]"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </div>
    </div>
  );
}
