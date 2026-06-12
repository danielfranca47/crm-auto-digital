import { useUsage } from "@/hooks/useUsage";

const CHECKOUT_START = "https://pay.kiwify.com.br/gOjcexD";
const CHECKOUT_GROWTH = "https://pay.kiwify.com.br/To8qV99";

export default function UsageAlertBanner() {
  const { data } = useUsage();

  const ia = (data?.usage?.ia_monthly as any) ?? null;
  if (!ia || ia.pct === null || ia.pct < 80) return null;

  const isFull = ia.pct >= 100;

  // Se já tem Growth (500 conversas), oferece plano Scale (quando existir); caso contrário, oferece Growth
  const planCode = data?.entitlements?.products?.find(
    (p) => p.product_code === "crm" && p.status === "active"
  )?.plan_code;
  const upgradeUrl = planCode === "crm_growth" ? CHECKOUT_GROWTH : CHECKOUT_GROWTH;

  return (
    <div
      className={`w-full px-4 py-2.5 flex items-center justify-between text-sm ${
        isFull
          ? "bg-red-900/50 border-b border-red-700/60 text-red-200"
          : "bg-amber-900/40 border-b border-amber-700/50 text-amber-200"
      }`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span>{isFull ? "🔴" : "🟡"}</span>
        <span className="truncate">
          {isFull
            ? `Limite atingido — ${ia.used}/${ia.limit} conversas IA usadas. O bot está pausado.`
            : `${ia.pct}% das conversas IA usadas este mês (${ia.used}/${ia.limit}).`}
        </span>
      </div>
      <a
        href={upgradeUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={`shrink-0 ml-4 px-3 py-1 rounded-lg text-xs font-semibold transition ${
          isFull
            ? "bg-red-600 hover:bg-red-500 text-white"
            : "bg-amber-600 hover:bg-amber-500 text-white"
        }`}
      >
        {isFull ? "Comprar mais" : "Fazer upgrade"}
      </a>
    </div>
  );
}
