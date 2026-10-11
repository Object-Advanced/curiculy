// The Sticker journal's rules, kept pure so they're easy to test.
//
// - A finished lesson earns its subject sticker on the day it was finished
//   (`completion_date`). Lessons finished before October 2026 have no date,
//   so they count on the day they were scheduled.
// - A day "reaches camp" when it had lessons and every lesson scheduled that
//   day is done (the same rule as My trail).
// - Each camp day wins that day's seasonal prize (campPrize), so the month's
//   collection fills in as camps are reached.

import { addDays, dayOf, monthName, monthOf, seasonOf, weekdayShort, type Season } from "./dates";
import { SEASON_COLLECTIONS, campPrize, lessonSticker, type Sticker } from "./stickers";

export interface JournalLesson {
  id: number;
  title: string;
  status: string;
  scheduled_date: string;
  completion_date?: string | null;
  subject_name?: string | null;
  resource_title?: string | null;
}

export interface EarnedSticker {
  lessonId: number;
  title: string;
  sticker: Sticker;
  day: string;
  /** False when the day is the scheduled day standing in for a missing finish date. */
  dated: boolean;
}

export type CampState = "reached" | "missed" | "open" | "future" | "none";

export interface JournalDay {
  iso: string;
  weekday: string;
  dayNumber: number;
  isToday: boolean;
  isFuture: boolean;
  planned: number;
  done: number;
  stickers: EarnedSticker[];
  camp: CampState;
}

export function isDone(lesson: JournalLesson): boolean {
  return lesson.status === "completed";
}

export function earnedSticker(lesson: JournalLesson): EarnedSticker | null {
  if (!isDone(lesson)) return null;
  return {
    lessonId: lesson.id,
    title: lesson.title,
    sticker: lessonSticker(lesson),
    day: lesson.completion_date ?? lesson.scheduled_date,
    dated: Boolean(lesson.completion_date),
  };
}

/** Days up to today that had lessons and finished all of them. */
export function campDays(lessons: JournalLesson[], today: string): Set<string> {
  const byDay = new Map<string, { planned: number; done: number }>();
  for (const lesson of lessons) {
    const entry = byDay.get(lesson.scheduled_date) ?? { planned: 0, done: 0 };
    entry.planned += 1;
    if (isDone(lesson)) entry.done += 1;
    byDay.set(lesson.scheduled_date, entry);
  }
  const days = new Set<string>();
  for (const [day, { planned, done }] of byDay) {
    if (day <= today && planned > 0 && done === planned) days.add(day);
  }
  return days;
}

/**
 * The week from Monday: Monday–Friday always, Saturday and Sunday only when
 * they had lessons or stickers.
 */
export function journalWeek(monday: string, today: string, lessons: JournalLesson[]): JournalDay[] {
  const camps = campDays(lessons, today);
  const earned = lessons.map(earnedSticker).filter((item): item is EarnedSticker => item !== null);
  const days: JournalDay[] = [];
  for (let offset = 0; offset < 7; offset += 1) {
    const iso = addDays(monday, offset);
    const scheduled = lessons.filter((lesson) => lesson.scheduled_date === iso);
    const stickers = earned.filter((item) => item.day === iso).sort((a, b) => a.lessonId - b.lessonId);
    const weekend = offset >= 5;
    if (weekend && scheduled.length === 0 && stickers.length === 0) continue;
    const isFuture = iso > today;
    const done = scheduled.filter(isDone).length;
    let camp: CampState = "none";
    if (scheduled.length > 0) {
      if (isFuture) camp = "future";
      else if (camps.has(iso)) camp = "reached";
      else camp = iso === today ? "open" : "missed";
    }
    days.push({
      iso,
      weekday: weekdayShort(iso),
      dayNumber: dayOf(iso),
      isToday: iso === today,
      isFuture,
      planned: scheduled.length,
      done,
      stickers,
      camp,
    });
  }
  return days;
}

export interface CollectionSlot {
  sticker: Sticker;
  state: "earned" | "next" | "mystery";
  earnedOn?: string;
}

export interface MonthCollection {
  season: Season;
  title: string;
  slots: CollectionSlot[];
  earned: number;
}

/** The month's 8 seasonal stickers: earned by reaching camp, the next prize, and mysteries. */
export function monthCollection(anyDayInMonth: string, today: string, lessons: JournalLesson[]): MonthCollection {
  const month = anyDayInMonth.slice(0, 7);
  const season = seasonOf(anyDayInMonth);
  const firstEarned = new Map<string, string>();
  for (const day of [...campDays(lessons, today)].sort()) {
    if (day.slice(0, 7) !== month) continue;
    const label = campPrize(day).label;
    if (!firstEarned.has(label)) firstEarned.set(label, day);
  }
  const nextLabel = today.slice(0, 7) === month ? campPrize(today).label : null;
  const slots = SEASON_COLLECTIONS[season].map((sticker): CollectionSlot => {
    const earnedOn = firstEarned.get(sticker.label);
    if (earnedOn) return { sticker, state: "earned", earnedOn };
    if (sticker.label === nextLabel) return { sticker, state: "next" };
    return { sticker, state: "mystery" };
  });
  return {
    season,
    title: `${monthName(anyDayInMonth)} collection`,
    slots,
    earned: slots.filter((slot) => slot.state === "earned").length,
  };
}

/** The month a week belongs to: today's month for this week, else its Thursday's. */
export function weekMonth(monday: string, today: string): string {
  const sunday = addDays(monday, 6);
  if (today >= monday && today <= sunday) return today;
  const thursday = addDays(monday, 3);
  return monthOf(thursday) === monthOf(monday) ? monday : thursday;
}
