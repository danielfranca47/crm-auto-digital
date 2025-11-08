import React, { useEffect, useRef, useState } from "react";
import { api } from "@/services/api";

type Props = {
  onRunningChange?: (running: boolean) => void;
};

const POLL_MS = 10_000;

export default function WhatsWorkerControls({ onRunningChange }: Props) {
  const [agentOnline, setAgentOnline] = useState<boolean | null>(null);
  const [pending, setPending] = useState<number>(0);
  const [inProgress, setInProgress] = useState<number>(0);
  const [busy, setBusy] = useState<boolean>(false);
  const timerRef = useRef<number | null>(null);

  const refresh = async () => {
    try {
      const overview = await api.agents.overview();
      const jobs = overview?.jobs ?? { pending: 0, in_progress: 0 };
      const running = (jobs.in_progress ?? 0) > 0;
      setInProgress(jobs.in_progress ?? 0);
      setPending(jobs.pending ?? 0);
      onRunningChange?.(running);

      const now = Date.now();
      const agents = overview?.agents ?? [];
      const anyOnline = agents.some((agent) => {
        if (agent?.status === "active") return true;
        if (!agent?.last_seen) return false;
        const last = new Date(agent.last_seen).getTime();
        return now - last < 2 * 60 * 1000;
      });
      setAgentOnline(anyOnline ? true : agents.length ? false : null);
    } catch (error) {
      console.warn("Não foi possível obter status do agente local", error);
      setAgentOnline(null);
      setPending(0);
      setInProgress(0);
      onRunningChange?.(false);
    }
  };

  const manualRefresh = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await refresh();
    } finally {
      setBusy(false);
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

  const agentBadgeClass = agentOnline === true
    ? "bg-emerald-100 text-emerald-700"
    : agentOnline === false
    ? "bg-rose-100 text-rose-700"
    : "bg-slate-100 text-slate-600";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span
        className={`px-2 py-1 rounded-full text-xs ${agentBadgeClass}`}
        title={
          agentOnline === true
            ? "Agente Local conectado"
            : agentOnline === false
            ? "Nenhum agente local comunicando recentemente"
            : "Status do agente local indisponível"
        }
      >
        {agentOnline === true ? "Agente Local: Online" : agentOnline === false ? "Agente Local: Offline" : "Agente Local"}
      </span>

      <span
        className="px-2 py-1 rounded-full text-xs bg-indigo-100 text-indigo-700"
        title="Jobs pendentes no backend aguardando execução"
      >
        Pendentes: {pending}
      </span>

      <span
        className="px-2 py-1 rounded-full text-xs bg-emerald-50 text-emerald-700"
        title="Jobs sendo processados pelo agente"
      >
        Em execução: {inProgress}
      </span>

      <button
        onClick={manualRefresh}
        disabled={busy}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-900 text-white hover:bg-slate-700 disabled:opacity-50"
      >
        Atualizar status
      </button>
    </div>
  );
}
