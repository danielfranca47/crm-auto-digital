import { useEffect, useRef, useState, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Send, Layers, X } from "lucide-react";
import { MessageBubble, type ChatMessage, type RatingValue } from "./MessageBubble";

interface PlaygroundChatProps {
  messages: ChatMessage[];
  loading: boolean;
  scenarioType?: "inbound" | "outbound";
  onSend: (text: string) => void;
  onToggleFeedback: (id: string) => void;
  onRate: (id: string, rating: RatingValue, comment: string) => void;
}

export function PlaygroundChat({
  messages,
  loading,
  scenarioType = "inbound",
  onSend,
  onToggleFeedback,
  onRate,
}: PlaygroundChatProps) {
  const [input, setInput] = useState("");
  const [batchMode, setBatchMode] = useState(false);
  const [pendingBatch, setPendingBatch] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSend() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    onSend(text);
  }

  function handleAddToBatch() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setPendingBatch((prev) => [...prev, text]);
  }

  function handleSendBatch() {
    if (pendingBatch.length === 0 || loading) return;
    const combined = pendingBatch.join("\n");
    setPendingBatch([]);
    onSend(combined);
  }

  function handleRemoveFromBatch(index: number) {
    setPendingBatch((prev) => prev.filter((_, i) => i !== index));
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (batchMode) {
        handleAddToBatch();
      } else {
        handleSend();
      }
    }
  }

  function toggleBatchMode() {
    setBatchMode((v) => !v);
    setPendingBatch([]);
  }

  const isMediaMarker = /^\{(áudio|audio|imagem|vídeo|video|documento)\}$/i.test(input.trim());

  return (
    <div className="flex flex-col h-full">
      {/* Área de mensagens */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm text-center px-4">
            {scenarioType === "outbound"
              ? "Aguarde, o bot irá enviar a mensagem de abertura outbound…"
              : "Envie uma mensagem para iniciar a simulação"}
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onToggleFeedback={onToggleFeedback}
              onRate={onRate}
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
      <div className="border-t p-3 flex flex-col gap-1.5 bg-background">
        {/* Fila do lote */}
        {batchMode && pendingBatch.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pb-1">
            {pendingBatch.map((msg, i) => (
              <div
                key={i}
                className="flex items-center gap-1 bg-muted rounded-full pl-3 pr-1.5 py-1 text-xs text-foreground max-w-[240px]"
              >
                <span className="truncate">{msg}</span>
                <button
                  onClick={() => handleRemoveFromBatch(i)}
                  className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                  disabled={loading}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2 items-end">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              batchMode
                ? "Adicione mensagens ao lote… (Enter adiciona, Shift+Enter nova linha)"
                : scenarioType === "outbound"
                ? "Responda como se fosse o lead… (Enter para enviar, Shift+Enter para nova linha)"
                : "Digite como se fosse o lead… (Enter para enviar, Shift+Enter para nova linha)"
            }
            rows={2}
            className="flex-1 resize-none text-sm min-h-[44px] max-h-32"
            disabled={loading}
          />

          {/* Toggle modo lote */}
          <Button
            onClick={toggleBatchMode}
            variant={batchMode ? "default" : "outline"}
            size="icon"
            className="shrink-0 h-[44px] w-[44px]"
            title={batchMode ? "Desativar modo lote" : "Ativar modo lote — simula absorção de mensagens consecutivas"}
          >
            <Layers className="h-4 w-4" />
          </Button>

          {batchMode ? (
            <Button
              onClick={handleSendBatch}
              disabled={pendingBatch.length === 0 || loading}
              className="shrink-0 h-[44px] px-3 text-xs"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                `Enviar lote${pendingBatch.length > 0 ? ` (${pendingBatch.length})` : ""}`
              )}
            </Button>
          ) : (
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
          )}
        </div>

        {/* Hints */}
        {batchMode ? (
          <p className="text-xs text-primary font-medium px-1">
            Modo lote ativo — simula absorção de mensagens consecutivas. Adicione mensagens e clique "Enviar lote".
          </p>
        ) : isMediaMarker ? (
          <p className="text-xs text-primary font-medium px-1">
            Mídia simulada — será exibida como card no chat
          </p>
        ) : (
          <p className="text-xs text-muted-foreground px-1">
            Dica: escreva <code className="bg-muted px-1 rounded">{"{áudio}"}</code>,{" "}
            <code className="bg-muted px-1 rounded">{"{imagem}"}</code> ou{" "}
            <code className="bg-muted px-1 rounded">{"{vídeo}"}</code> para simular envio de mídia.
            Use <code className="bg-muted px-1 rounded"><Layers className="inline h-3 w-3" /></code> para simular múltiplas mensagens antes da resposta.
          </p>
        )}
      </div>
    </div>
  );
}
