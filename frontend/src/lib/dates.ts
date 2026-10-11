/** Today's date on this device as YYYY-MM-DD, the same day the legacy app uses. */
export function todayISO(now: Date = new Date()): string {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** Zero-based month (0 = January) of a YYYY-MM-DD date. */
export function monthOf(iso: string): number {
  return Number(iso.slice(5, 7)) - 1;
}

/** Day of the month (1–31) of a YYYY-MM-DD date. */
export function dayOf(iso: string): number {
  return Number(iso.slice(8, 10));
}

export type Season = "winter" | "spring" | "summer" | "autumn";

export function seasonOf(iso: string): Season {
  const month = monthOf(iso);
  if (month >= 2 && month <= 4) return "spring";
  if (month >= 5 && month <= 7) return "summer";
  if (month >= 8 && month <= 10) return "autumn";
  return "winter";
}

// ---- Calendar arithmetic on YYYY-MM-DD strings (UTC, so no time zone drift) ----

function toUTC(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number) as [number, number, number];
  return new Date(Date.UTC(year, month - 1, day));
}

function fromUTC(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(iso: string, days: number): string {
  const date = toUTC(iso);
  date.setUTCDate(date.getUTCDate() + days);
  return fromUTC(date);
}

/** Monday of the week containing `iso`. */
export function weekStart(iso: string): string {
  const offset = (toUTC(iso).getUTCDay() + 6) % 7;
  return addDays(iso, -offset);
}

export function monthStart(iso: string): string {
  return `${iso.slice(0, 7)}-01`;
}

export function monthEnd(iso: string): string {
  const date = toUTC(monthStart(iso));
  date.setUTCMonth(date.getUTCMonth() + 1, 0);
  return fromUTC(date);
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const WEEKDAYS_LONG = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export function weekdayShort(iso: string): string {
  return WEEKDAYS[toUTC(iso).getUTCDay()] ?? "";
}

export function weekdayLong(iso: string): string {
  return WEEKDAYS_LONG[toUTC(iso).getUTCDay()] ?? "";
}

export function monthName(iso: string): string {
  return MONTHS[monthOf(iso)] ?? "";
}

/** "Oct 12 – 16", or "Sep 29 – Oct 3" across a month boundary. */
export function rangeLabel(fromISO: string, toISO: string): string {
  const from = `${monthName(fromISO).slice(0, 3)} ${dayOf(fromISO)}`;
  const to = monthOf(fromISO) === monthOf(toISO) ? `${dayOf(toISO)}` : `${monthName(toISO).slice(0, 3)} ${dayOf(toISO)}`;
  return `${from} – ${to}`;
}
