import { useEffect, useRef, useState, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Send, Layers, X, Mic, Square } from "lucide-react";
import { MessageBubble, type ChatMessage, type RatingValue } from "./MessageBubble";

interface PlaygroundChatProps {
  messages: ChatMessage[];
  loading: boolean;
  scenarioType?: "inbound" | "outbound";
  audioEnabled?: boolean;
  onSend: (text: string) => void;
  onSendAudio?: (blob: Blob) => void;
  onToggleFeedback: (id: string) => void;
  onRate: (id: string, rating: RatingValue, comment: string) => void;
}

export function PlaygroundChat({
  messages,
  loading,
  scenarioType = "inbound",
  audioEnabled = false,
  onSend,
  onSendAudio,
  onToggleFeedback,
  onRate,
}: PlaygroundChatProps) {
  const [input, setInput] = useState("");
  const [batchMode, setBatchMode] = useState(false);
  const [pendingBatch, setPendingBatch] = useState<string[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [pendingAudio, setPendingAudio] = useState<{ blob: Blob; objectUrl: string } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (pendingAudio) URL.revokeObjectURL(pendingAudio.objectUrl);
    };
  }, []);

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

  async function startRecording() {
    if (pendingAudio) cancelAudio();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
      const mr = new MediaRecorder(stream);
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/ogg; codecs=opus" });
        const objectUrl = URL.createObjectURL(blob);
        setPendingAudio({ blob, objectUrl });
        setIsRecording(false);
        setRecordingSeconds(0);
        if (timerRef.current) clearInterval(timerRef.current);
      };
      mr.start();
      mediaRecorderRef.current = mr;
      setIsRecording(true);
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
    } catch {
      alert("Permissão de microfone negada. Verifique as configurações do browser.");
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    if (timerRef.current) clearInterval(timerRef.current);
  }

  function cancelAudio() {
    if (pendingAudio) {
      URL.revokeObjectURL(pendingAudio.objectUrl);
      setPendingAudio(null);
    }
  }

  function sendPendingAudio() {
    if (!pendingAudio || loading) return;
    const { blob, objectUrl } = pendingAudio;
    setPendingAudio(null);
    URL.revokeObjectURL(objectUrl);
    onSendAudio?.(blob);
  }

  const isMediaMarker = /^\{(áudio|audio|imagem|vídeo|video|documento)\}$/i.test(input.trim());
  const fmtSeconds = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

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
        {/* Preview de áudio pendente */}
        {pendingAudio && (
          <div className="flex items-center gap-2 px-2 py-1.5 bg-muted rounded-lg border">
            <Mic className="h-4 w-4 text-primary shrink-0" />
            <audio controls src={pendingAudio.objectUrl} className="h-8 flex-1 min-w-0" />
            <Button size="sm" onClick={sendPendingAudio} disabled={loading} className="shrink-0 h-8 text-xs">
              {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : "Enviar"}
            </Button>
            <Button size="icon" variant="ghost" onClick={cancelAudio} className="shrink-0 h-8 w-8">
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}

        {/* Indicador de gravação */}
        {isRecording && (
          <div className="flex items-center gap-2 px-2 py-1 text-sm text-red-500">
            <span className="inline-block h-2 w-2 rounded-full bg-red-500 animate-pulse" />
            Gravando… {fmtSeconds(recordingSeconds)}
          </div>
        )}

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
            disabled={loading || isRecording}
          />

          {/* Botão de microfone */}
          <Button
            onClick={isRecording ? stopRecording : startRecording}
            variant={isRecording ? "destructive" : "outline"}
            size="icon"
            className="shrink-0 h-[44px] w-[44px]"
            title={isRecording ? "Parar gravação" : "Gravar áudio"}
            disabled={loading || !!pendingAudio}
          >
            {isRecording ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
          </Button>

          {/* Toggle modo lote */}
          <Button
            onClick={toggleBatchMode}
            variant={batchMode ? "default" : "outline"}
            size="icon"
            className="shrink-0 h-[44px] w-[44px]"
            title={batchMode ? "Desativar modo lote" : "Ativar modo lote — simula absorção de mensagens consecutivas"}
            disabled={isRecording}
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
              disabled={!input.trim() || loading || isRecording}
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
        ) : isRecording ? (
          <p className="text-xs text-red-500 px-1">
            Gravando áudio… clique <strong>Stop</strong> para parar e pré-visualizar.
          </p>
        ) : pendingAudio ? (
          <p className="text-xs text-primary font-medium px-1">
            Áudio gravado — reproduza para confirmar e clique <strong>Enviar</strong>.
          </p>
        ) : isMediaMarker ? (
          <p className="text-xs text-primary font-medium px-1">
            Mídia simulada — será exibida como card no chat
          </p>
        ) : !audioEnabled ? (
          <p className="text-xs text-muted-foreground px-1">
            Ative <strong>Receber áudio</strong> no AI Profile para testar transcrição de áudio. O microfone ainda funciona — a resposta seguirá a configuração de Mídia inválida.
          </p>
        ) : (
          <p className="text-xs text-muted-foreground px-1">
            Dica: escreva <code className="bg-muted px-1 rounded">{"{áudio}"}</code>,{" "}
            <code className="bg-muted px-1 rounded">{"{imagem}"}</code> ou{" "}
            <code className="bg-muted px-1 rounded">{"{vídeo}"}</code> para simular envio de mídia,
            ou use o microfone para gravar um áudio real.
            Use <code className="bg-muted px-1 rounded"><Layers className="inline h-3 w-3" /></code> para simular múltiplas mensagens antes da resposta.
          </p>
        )}
      </div>
    </div>
  );
}
