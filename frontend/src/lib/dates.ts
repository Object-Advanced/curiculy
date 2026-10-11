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
