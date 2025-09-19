import React, { useEffect, useRef, useState } from "react";
import { api } from "@/services/api";

type Props = {
  onRunningChange?: (running: boolean) => void;
};

const POLL_MS = 8000;

export default function WhatsWorkerControls({ onRunningChange }: Props) {
  const [running, setRunning] = useState<boolean>(false);
  const [pending, setPending] = useState<number>(0);
  const [busy, setBusy] = useState<boolean>(false);
  const timerRef = useRef<number | null>(null);

  const refresh = async () => {
    try {
      const st = await api.whatsapp.worker.status();
      const isRunning = !!st?.running;
      setRunning(isRunning);
      onRunningChange?.(isRunning);

      // pega até 50 pendentes (suficiente p/ um “mini monitor”)
      const q = await api.prospeccao.whatsapp.queue(50);
      setPending(Array.isArray(q) ? q.length : 0);
    } catch {
      /* silencioso no UI */
    }
  };

  const start = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await api.whatsapp.worker.start();
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await api.whatsapp.worker.stop();
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

  return (
    <div className="flex items-center gap-2">
      <span
        className={
          "px-2 py-1 rounded-full text-xs " +
          (running ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600")
        }
        title={running ? "Robô de envio está rodando" : "Robô parado"}
      >
        Worker {running ? "Rodando" : "Parado"}
      </span>

      <span className="px-2 py-1 rounded-full text-xs bg-indigo-100 text-indigo-700" title="Itens pendentes na fila">
        Pendentes: {pending}
      </span>

      <button
        onClick={start}
        disabled={busy || running}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
      >
        Iniciar envio
      </button>

      <button
        onClick={stop}
        disabled={busy || !running}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
      >
        Parar envio
      </button>
    </div>
  );
}
