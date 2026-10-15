/**
 * Turning what a parent pastes (a contents page, a publisher's lesson list)
 * into chapters and lessons. Forgiving on purpose: one item per line, the
 * page numbers wherever they are, and anything it can't read is skipped and
 * counted so the parent knows.
 */
import { addDays, weekStart } from "./dates";

export interface ChapterDraft {
  name: string;
  start_page: number | null;
}

export type LessonType = "lesson" | "test" | "quiz" | "review" | "project";

export interface LessonDraft {
  number: number | null;
  name: string;
  type: LessonType;
  start_page: number | null;
  end_page: number | null;
  /** How long it usually takes, when the publisher says (families who count hours). */
  minutes?: number | null;
}

export interface Parsed<T> {
  rows: T[];
  skipped: number;
}

const SEPARATORS = /[\s,.:;–—\-·|]+$/;
const LEADING = /^[\s,.:;–—\-·|]+/;
const PAGE_WORD = /\b(?:pp?|pages?|pgs?)\.?\s*$/i;

function tidy(text: string): string {
  return text.replace(PAGE_WORD, "").replace(SEPARATORS, "").replace(LEADING, "").replace(/\s+/g, " ").trim();
}

/** "Addition, 5", "1. Addition ....... 5", "Chapter 2: Fractions — p. 62" */
export function parseChapters(text: string): Parsed<ChapterDraft> {
  const rows: ChapterDraft[] = [];
  let skipped = 0;
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const match = line.match(/^(.*?)(\d{1,4})\s*$/);
    const name = match ? tidy(match[1]!.replace(/\.{2,}/g, " ")) : "";
    if (!match || !name) {
      skipped += 1;
      continue;
    }
    rows.push({ name, start_page: Number(match[2]) });
  }
  return { rows, skipped };
}

const TYPE_WORDS: [RegExp, LessonType][] = [
  [/^(?:chapter\s+|unit\s+)?test\b/i, "test"],
  [/^quiz\b/i, "quiz"],
  [/^review\b/i, "review"],
  [/^project\b/i, "project"],
];

/**
 * "12 The Lost Dog 45-49", "Lesson 12: The Lost Dog, pp. 45–49",
 * "Test 1, 50-51", "Quiz 3 p. 60". Lessons without a number are numbered
 * on from the one before.
 */
export function parseLessons(text: string, firstNumber = 1): Parsed<LessonDraft> {
  const rows: LessonDraft[] = [];
  let skipped = 0;
  let next = firstNumber;
  for (const raw of text.split(/\r?\n/)) {
    let line = raw.trim();
    if (!line) continue;

    let start: number | null = null;
    let end: number | null = null;
    const range = line.match(/(?:pp?\.?|pages?)?\s*(\d{1,4})\s*[-–—]\s*(\d{1,4})\s*$/i);
    const single = line.match(/(?:pp?\.?|pages?)\s*(\d{1,4})\s*$/i);
    if (range) {
      start = Number(range[1]);
      end = Number(range[2]);
      line = line.slice(0, range.index).trim();
    } else if (single) {
      start = end = Number(single[1]);
      line = line.slice(0, single.index).trim();
    }

    let type: LessonType = "lesson";
    for (const [pattern, kind] of TYPE_WORDS) {
      if (pattern.test(line)) type = kind;
    }

    let number: number | null = null;
    const numbered = line.match(/^(?:lesson\s+)?(\d{1,4})\b[\s.:)\-–—]*/i);
    if (numbered && type === "lesson") {
      number = Number(numbered[1]);
      line = line.slice(numbered[0].length);
    }
    const name = tidy(line);
    if (!name && start === null) {
      skipped += 1;
      continue;
    }
    if (number === null) number = next;
    next = number + 1;
    rows.push({ number, name: name || (type === "lesson" ? "" : type[0]!.toUpperCase() + type.slice(1)), type, start_page: start, end_page: end });
  }
  return { rows, skipped };
}

/** "Make lessons 1–170": numbered rows to fill in. */
export function numberedLessons(count: number, firstNumber = 1): LessonDraft[] {
  return Array.from({ length: count }, (_, index) => ({
    number: firstNumber + index,
    name: "",
    type: "lesson" as const,
    start_page: null,
    end_page: null,
  }));
}

/** The Monday to start on: today if it's Monday, otherwise next Monday. */
export function nextMonday(todayIso: string): string {
  const monday = weekStart(todayIso);
  return monday === todayIso ? todayIso : addDays(monday, 7);
}
