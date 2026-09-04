/**
 * origin classifica a DIREÇÃO da conversa: o literal "outbound" sinaliza que a empresa
 * abordou o lead primeiro; "Manual" (default) e qualquer outro valor técnico gravado pelo
 * sistema (whatsapp_inbound, Formulário Website, Planilha) representam inbound. O canal de
 * marketing/aquisição (Facebook Ads, Indicação, Website...) vive em `acquisition_channel`,
 * um campo separado e livre — ver backend-crm/services/ai_orchestrator/orchestrator.py,
 * _classify_lead_origin().
 */
export const LEAD_DIRECTION_OPTIONS = [
  { value: "Manual", label: "Inbound — o lead procurou primeiro" },
  { value: "outbound", label: "Outbound — eu abordei primeiro" },
] as const;

export function formatLeadOriginLabel(origin: string | null | undefined): string {
  const raw = (origin || "").trim();
  const normalized = raw.toLowerCase();
  if (!raw) return "—";
  if (normalized === "manual") return "Inbound";
  if (normalized === "outbound") return "Outbound";
  if (normalized === "whatsapp_inbound") return "Inbound (WhatsApp)";
  if (normalized === "formulário website") return "Inbound (Formulário do site)";
  if (normalized === "planilha") return "Inbound (Planilha)";
  // valor técnico ainda não mapeado: mesmo default-safe do _classify_lead_origin()
  // (tudo que não é "outbound" é inbound) — nunca mostra o valor cru sozinho.
  return `Inbound (${raw})`;
}
