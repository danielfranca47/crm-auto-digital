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
