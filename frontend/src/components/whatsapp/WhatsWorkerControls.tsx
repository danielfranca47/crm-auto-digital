import React, { useEffect, useRef, useState } from "react";
import { api } from "@/services/api";

type Props = {
  onRunningChange?: (running: boolean) => void;
};

const POLL_MS = 8000;

export default function WhatsWorkerControls({ onRunningChange }: Props) {
  const [agentOnline, setAgentOnline] = useState<boolean>(false);
  const [pending, setPending] = useState<number>(0);
  const timerRef = useRef<number | null>(null);

  const refresh = async () => {
    try {
      const overview = await api.agents.overview();
      const agents = Array.isArray(overview?.agents) ? overview.agents : [];
      const isOnline = agents.some((agent: any) => agent?.online);
      setAgentOnline(isOnline);
      onRunningChange?.(isOnline);

      const q = await api.prospeccao.whatsapp.queue(50);
      setPending(Array.isArray(q) ? q.length : 0);
    } catch {
      setAgentOnline(false);
    }
  };

  useEffect(() => {
    refresh();
    timerRef.current = window.setInterval(refresh, POLL_MS);
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <span
        className={
          "px-2 py-1 rounded-full text-xs " +
          (agentOnline ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600")
        }
        title={agentOnline ? "Agente Local conectado" : "Agente Local offline"}
      >
        Agente Local {agentOnline ? "Online" : "Offline"}
      </span>

      <span className="px-2 py-1 rounded-full text-xs bg-indigo-100 text-indigo-700" title="Itens pendentes na fila">
        Pendentes: {pending}
      </span>

      {!agentOnline && (
        <span className="text-xs text-slate-500">
          Execute o aplicativo do agente local para consumir os jobs automaticamente.
        </span>
      )}
    </div>
  );
}
