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
  const normalized = (origin || "").trim().toLowerCase();
  if (normalized === "manual") return "Inbound";
  if (normalized === "outbound") return "Outbound";
  // whatsapp_inbound, Formulário Website, Planilha, ou um canal livre: mostra cru.
  return origin || "—";
}
