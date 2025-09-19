import React, { useEffect, useState } from "react";
import { ProspectionBoard } from "@/components/prospection/ProspectionBoard";
import { useLeads } from "@/contexts/LeadsContext";
import WhatsAppLogin from "@/components/whatsapp/WhatsAppLogin";
import WhatsWorkerControls from "@/components/whatsapp/WhatsWorkerControls";
import { api } from "@/services/api";

const Prospeccao: React.FC = () => {
  const {
    prospectionColumns,
    updateProspectionLead,
    moveProspectionLead,
    bulkProspection,
  } = useLeads();

  // --- WhatsApp session UI state ---
  const [openWhats, setOpenWhats] = useState(false);
  const [waLogged, setWaLogged] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    api.whatsapp.verificarLogin()
      .then((r) => { if (alive) setWaLogged(!!r?.logado); })
      .catch(() => { if (alive) setWaLogged(null); });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    // checa status ao entrar
    api.whatsapp
      .verificarLogin({ passive: true })
      .then((r) => setWaLogged(!!r?.logado))
      .catch(() => setWaLogged(null));
  }, []);

  const handleMoveToNext = (leadId: string) => {
    const allLeads = prospectionColumns.flatMap((col) => col.leads);
    const lead = allLeads.find((l) => l.id === leadId);
    if (!lead) return;

    let nextStatus: "to-prospect" | "in-progress" | "prospected";
    if (lead.prospectionStatus === "to-prospect") nextStatus = "in-progress";
    else if (lead.prospectionStatus === "in-progress") nextStatus = "prospected";
    else return;

    moveProspectionLead(leadId, nextStatus);
  };

  // badge helper
  const waBadge = (
    <span
      className={
        "px-2 py-1 rounded-full text-xs " +
        (waLogged === true
          ? "bg-emerald-100 text-emerald-700"
          : waLogged === false
          ? "bg-rose-100 text-rose-700"
          : "bg-slate-100 text-slate-600")
      }
      title={
        waLogged === true
          ? "WhatsApp conectado"
          : waLogged === false
          ? "WhatsApp desconectado"
          : "Status indisponível"
      }
    >
      {waLogged === true
        ? "WA Conectado"
        : waLogged === false
        ? "WA Desconectado"
        : "WA —"}
    </span>
  );

  return (
    <div className="space-y-4">
      {/* Barra superior da página (alinha com o título/toolbar existentes) */}
      <div className="flex items-center justify-end gap-3">
        {waBadge}
        

        <button
          onClick={() => setOpenWhats(true)}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition"
        >
          {/* ícone simples de balão */}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 3H4a1 1 0 0 0-1 1v16l4-4h13a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1z" />
          </svg>
          Conectar WhatsApp
        </button>
      </div>

      {/* Board original (sem mudanças) */}
      <ProspectionBoard
        columns={prospectionColumns}
        onUpdateLead={updateProspectionLead}
        onMoveToNext={handleMoveToNext}
        onBulkProspection={bulkProspection}
      />

      {/* Modal WhatsApp Login */}
      {openWhats && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="relative w-full max-w-md bg-white rounded-2xl shadow-xl p-4">
            <button
              onClick={() => {
                setOpenWhats(false);
                // re-checa status ao fechar
                api.whatsapp
                  .verificarLogin()
                  .then((r) => setWaLogged(!!r?.logado))
                  .catch(() => setWaLogged(null));
              }}
              className="absolute right-3 top-3 text-slate-500 hover:text-slate-700"
              aria-label="Fechar"
            >
              ✕
            </button>
            <WhatsAppLogin />
          </div>
        </div>
      )}
    </div>
  );
};

export default Prospeccao;
