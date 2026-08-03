import { useBusinessTimezone, browserTimezone } from "@/hooks/useBusinessTimezone";
import { formatInBusinessTimezone, getTimezoneCityLabel } from "@/lib/timezone";

interface AppointmentTimeLabelProps {
  startTime: string;
  endTime?: string | null;
  formatStr?: string;
  className?: string;
}

function formatSegment(
  startTime: string,
  endTime: string | null | undefined,
  timeZone: string,
  formatStr: string
): string {
  const start = formatInBusinessTimezone(startTime, formatStr, timeZone);
  if (!endTime) return start;
  const end = formatInBusinessTimezone(endTime, formatStr, timeZone);
  return `${start} – ${end}`;
}

/**
 * Horário de um compromisso, sempre no fuso do negócio; quando o fuso do navegador de
 * quem está a ver a tela é diferente, acrescenta o mesmo horário no fuso do navegador
 * (cada um com o nome da cidade) — evita a leitura ambígua de um horário "solto".
 */
export function AppointmentTimeLabel({
  startTime,
  endTime,
  formatStr = "HH:mm",
  className,
}: AppointmentTimeLabelProps) {
  const businessTimezone = useBusinessTimezone();
  const mismatched = businessTimezone !== browserTimezone;

  const businessSegment = formatSegment(startTime, endTime, businessTimezone, formatStr);

  if (!mismatched) {
    return <span className={className}>{businessSegment}</span>;
  }

  const browserSegment = formatSegment(startTime, endTime, browserTimezone, formatStr);

  return (
    <span className={className}>
      {businessSegment}
      <span className="ml-1 text-[11px] font-normal text-muted-foreground">
        ({getTimezoneCityLabel(businessTimezone)}) · {browserSegment} (
        {getTimezoneCityLabel(browserTimezone)})
      </span>
    </span>
  );
}
