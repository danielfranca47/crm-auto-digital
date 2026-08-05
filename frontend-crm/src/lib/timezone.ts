import { formatInTimeZone, fromZonedTime, toZonedTime } from "date-fns-tz";

/**
 * Formata uma data/ISO no fuso do negócio — substitui `format(date, formatStr)` do date-fns
 * puro, que sempre usa o fuso do navegador de quem está a ver a tela.
 */
export function formatInBusinessTimezone(
  date: Date | string | number,
  formatStr: string,
  timeZone: string
): string {
  return formatInTimeZone(date, timeZone, formatStr);
}

/**
 * Devolve um Date cujos getters locais (getHours, getMinutes, ...) refletem o horário de
 * parede no fuso do negócio — usado para popular campos de edição a partir de um ISO em UTC.
 */
export function toBusinessTimezoneDate(date: Date | string | number, timeZone: string): Date {
  return toZonedTime(date, timeZone);
}

/**
 * Constrói o instante UTC correto a partir de um Date cujos campos (ano/mês/dia/hora/minuto)
 * representam o horário de parede no fuso do negócio — substitui `date.setHours(...)`, que
 * interpreta a hora digitada no fuso do navegador em vez do fuso do negócio.
 */
export function fromBusinessTimezoneDate(date: Date, timeZone: string): Date {
  return fromZonedTime(date, timeZone);
}

/**
 * Início/fim (00:00:00.000–23:59:59.999) do dia de calendário informado (ano/mês/dia
 * lidos do Date como estão) no fuso do negócio — usado para montar os limites `start`/
 * `end` de busca enviados ao backend, em vez do fuso do navegador.
 */
export function getBusinessDayBounds(date: Date, timeZone: string): { start: Date; end: Date } {
  const y = date.getFullYear();
  const m = date.getMonth();
  const d = date.getDate();
  return {
    start: fromBusinessTimezoneDate(new Date(y, m, d, 0, 0, 0, 0), timeZone),
    end: fromBusinessTimezoneDate(new Date(y, m, d, 23, 59, 59, 999), timeZone),
  };
}

/**
 * Generaliza `getBusinessDayBounds` para um intervalo (semana/mês): início do primeiro
 * dia até fim do último dia, no fuso do negócio.
 */
export function getBusinessRangeBounds(
  startDate: Date,
  endDate: Date,
  timeZone: string
): { start: Date; end: Date } {
  return {
    start: getBusinessDayBounds(startDate, timeZone).start,
    end: getBusinessDayBounds(endDate, timeZone).end,
  };
}

const KNOWN_CITY_LABELS: Record<string, string> = {
  "America/Sao_Paulo": "São Paulo",
  "America/Manaus": "Manaus",
  "America/Fortaleza": "Fortaleza",
  "America/Belem": "Belém",
  "America/Noronha": "Noronha",
  "Europe/Lisbon": "Lisboa",
  "Europe/London": "Londres",
  UTC: "UTC",
};

/**
 * Nome curto de cidade para um fuso IANA — usado para deixar explícito de qual fuso é
 * um horário exibido (ex. "17:00 (São Paulo)"). Fusos fora da lista curada caem no
 * último segmento do próprio nome IANA (ex. "America/New_York" -> "New York").
 */
export function getTimezoneCityLabel(timeZone: string): string {
  if (KNOWN_CITY_LABELS[timeZone]) return KNOWN_CITY_LABELS[timeZone];
  const city = timeZone.split("/").pop() ?? timeZone;
  return city.replace(/_/g, " ");
}
