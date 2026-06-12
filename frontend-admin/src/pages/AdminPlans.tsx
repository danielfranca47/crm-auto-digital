import { useEffect, useState } from "react";
import { api } from "@/services/api";
import type { PlanLimits } from "@/services/api";

function fmt(val: number | null | undefined): string {
  if (val === null || val === undefined) return "∞";
  return val.toLocaleString("pt-BR");
}

function BoolBadge({ val }: { val: boolean | null | undefined }) {
  if (val === null || val === undefined) return <span className="text-slate-500">—</span>;
  return val
    ? <span className="text-emerald-400 font-medium">✅ Sim</span>
    : <span className="text-red-400 font-medium">❌ Não</span>;
}

const COMMERCIAL_PLANS = ["crm_start", "crm_growth", "crm_internal"];

export default function AdminPlans() {
  const [plans, setPlans] = useState<PlanLimits[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.adminListPlans()
      .then(setPlans)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const commercial = plans.filter(p => COMMERCIAL_PLANS.includes(p.plan_code));
  const legacy = plans.filter(p => !COMMERCIAL_PLANS.includes(p.plan_code));

  return (
    <div className="p-6 max-w-5xl">
      <h1 className="text-xl font-semibold text-slate-200 mb-1">Planos</h1>
      <p className="text-slate-500 text-sm mb-6">Limites e features por plano comercial.</p>

      {loading ? (
        <p className="text-slate-500 text-sm">Carregando…</p>
      ) : (
        <>
          {/* Planos comerciais */}
          <div className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden mb-8">
            <div className="px-5 py-3 border-b border-slate-700">
              <h2 className="text-sm font-semibold text-slate-300">Planos comerciais</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left px-5 py-2.5 text-slate-400 font-medium">Recurso</th>
                    {commercial.map(p => (
                      <th key={p.plan_code} className="text-center px-5 py-2.5 text-slate-200 font-semibold">
                        {p.plan_name}
                        {p.plan_code === "crm_internal" && (
                          <span className="ml-1 text-xs text-amber-400">(interno)</span>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {[
                    { label: "Leads no CRM", key: "max_leads" as const },
                    { label: "Conversas IA / mês", key: "max_ia_conversas_monthly" as const },
                    { label: "Envios WhatsApp / dia", key: "max_whatsapp_send_daily" as const },
                    { label: "Agentes locais", key: "max_agents_local" as const },
                  ].map(({ label, key }) => (
                    <tr key={key} className="hover:bg-slate-800/40">
                      <td className="px-5 py-2.5 text-slate-400">{label}</td>
                      {commercial.map(p => (
                        <td key={p.plan_code} className="px-5 py-2.5 text-center text-slate-200">
                          {fmt(p[key])}
                        </td>
                      ))}
                    </tr>
                  ))}
                  <tr className="hover:bg-slate-800/40">
                    <td className="px-5 py-2.5 text-slate-400">Follow-up automático</td>
                    {commercial.map(p => (
                      <td key={p.plan_code} className="px-5 py-2.5 text-center">
                        <BoolBadge val={p.follow_up_enabled} />
                      </td>
                    ))}
                  </tr>
                  <tr className="hover:bg-slate-800/40">
                    <td className="px-5 py-2.5 text-slate-400">Playground testes / mês</td>
                    {commercial.map(p => (
                      <td key={p.plan_code} className="px-5 py-2.5 text-center text-slate-200">
                        {fmt(p.playground_monthly_limit)}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Planos legados */}
          {legacy.length > 0 && (
            <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-700/50">
                <h2 className="text-sm font-medium text-slate-500">Planos legados (utilizadores existentes)</h2>
              </div>
              <div className="divide-y divide-slate-700/40">
                {legacy.map(p => (
                  <div key={p.plan_code} className="px-5 py-2.5 flex items-center justify-between">
                    <span className="text-sm text-slate-400">{p.plan_name}</span>
                    <span className="text-xs text-slate-600 font-mono">{p.plan_code}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
