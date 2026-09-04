import { useWhatsappConnectionAlert } from "@/hooks/useWhatsappConnectionAlert";

export default function WhatsappDisconnectBanner() {
  const { disconnected } = useWhatsappConnectionAlert();

  if (!disconnected) return null;

  return (
    <div className="w-full px-4 py-2.5 flex items-center justify-between text-sm bg-red-900/50 border-b border-red-700/60 text-red-200">
      <div className="flex items-center gap-2 min-w-0">
        <span>🔴</span>
        <span className="truncate">
          WhatsApp desconectado — reconecte para continuar respondendo automaticamente.
        </span>
      </div>
      <a
        href="/ai-profile"
        className="shrink-0 ml-4 px-3 py-1 rounded-lg text-xs font-semibold transition bg-red-600 hover:bg-red-500 text-white"
      >
        Reconectar
      </a>
    </div>
  );
}
