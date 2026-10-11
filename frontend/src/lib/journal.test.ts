import { describe, expect, it } from "vitest";

import { addDays, monthEnd, rangeLabel, weekStart } from "./dates";
import { campDays, earnedSticker, journalWeek, monthCollection, weekMonth, type JournalLesson } from "./journal";
import { SEASON_COLLECTIONS, campPrize } from "./stickers";

const TODAY = "2026-10-14"; // a Wednesday

function lesson(id: number, scheduled: string, done: boolean, extra: Partial<JournalLesson> = {}): JournalLesson {
  return { id, title: `Lesson ${id}`, status: done ? "completed" : "assigned", scheduled_date: scheduled, completion_date: null, ...extra };
}

describe("calendar helpers", () => {
  it("finds Mondays, month ends, and labels", () => {
    expect(weekStart("2026-10-14")).toBe("2026-10-12");
    expect(weekStart("2026-10-12")).toBe("2026-10-12");
    expect(weekStart("2026-10-18")).toBe("2026-10-12");
    expect(addDays("2026-10-30", 3)).toBe("2026-11-02");
    expect(monthEnd("2026-02-10")).toBe("2026-02-28");
    expect(rangeLabel("2026-10-12", "2026-10-16")).toBe("Oct 12 – 16");
    expect(rangeLabel("2026-09-28", "2026-10-02")).toBe("Sep 28 – Oct 2");
  });
});

describe("stickers by day", () => {
  it("counts a finished lesson on its finish date", () => {
    const item = earnedSticker(lesson(1, "2026-10-12", true, { completion_date: "2026-10-13", title: "Saxon Math Lesson 41" }));
    expect(item).toMatchObject({ day: "2026-10-13", dated: true, title: "Saxon Math Lesson 41" });
    expect(item?.sticker.label).toBe("Math");
  });

  it("falls back to the scheduled day for older lessons with no finish date", () => {
    expect(earnedSticker(lesson(2, "2026-10-05", true))).toMatchObject({ day: "2026-10-05", dated: false });
  });

  it("gives nothing for unfinished lessons", () => {
    expect(earnedSticker(lesson(3, "2026-10-12", false))).toBeNull();
  });
});

describe("camp", () => {
  it("is reached on days that had lessons and finished all of them, up to today", () => {
    const lessons = [
      lesson(1, "2026-10-12", true),
      lesson(2, "2026-10-12", true),
      lesson(3, "2026-10-13", true),
      lesson(4, "2026-10-13", false),
      lesson(5, "2026-10-15", true), // tomorrow, finished early: not counted yet
    ];
    expect([...campDays(lessons, TODAY)]).toEqual(["2026-10-12"]);
  });
});

describe("the week", () => {
  const lessons = [
    lesson(1, "2026-10-12", true, { completion_date: "2026-10-12" }),
    lesson(2, "2026-10-13", false),
    lesson(3, "2026-10-14", true, { completion_date: "2026-10-14" }),
    lesson(4, "2026-10-14", false),
    lesson(5, "2026-10-15", false),
    lesson(6, "2026-10-09", true, { completion_date: "2026-10-13" }), // last week's, finished Tuesday
  ];

  it("lists Monday to Friday with each day's stickers and camp", () => {
    const days = journalWeek("2026-10-12", TODAY, lessons);
    expect(days.map((day) => day.weekday)).toEqual(["Mon", "Tue", "Wed", "Thu", "Fri"]);
    expect(days.map((day) => day.camp)).toEqual(["reached", "missed", "open", "future", "none"]);
    expect(days[1]?.stickers.map((item) => item.lessonId)).toEqual([6]);
    expect(days[2]).toMatchObject({ isToday: true, planned: 2, done: 1 });
    expect(days[3]).toMatchObject({ isFuture: true });
  });

  it("shows a weekend day only when something happened", () => {
    const withSaturday = [...lessons, lesson(9, "2026-10-17", true)];
    const days = journalWeek("2026-10-12", "2026-10-18", withSaturday);
    expect(days.map((day) => day.weekday)).toEqual(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]);
  });
});

describe("the month's collection", () => {
  it("earns the prize of each camp day and marks today's prize as next", () => {
    const lessons = [lesson(1, "2026-10-01", true), lesson(2, "2026-10-12", true), lesson(3, "2026-10-14", false)];
    const collection = monthCollection(TODAY, TODAY, lessons);
    expect(collection.title).toBe("October collection");
    expect(collection.slots).toHaveLength(8);
    expect(collection.earned).toBe(2);
    const earned = collection.slots.filter((slot) => slot.state === "earned").map((slot) => slot.sticker.label);
    expect(earned).toEqual(expect.arrayContaining([campPrize("2026-10-01").label, campPrize("2026-10-12").label]));
    const next = collection.slots.find((slot) => slot.state === "next");
    expect(next?.sticker.label).toBe(campPrize(TODAY).label);
  });

  it("ignores camps from other months and has no 'next' for a past month", () => {
    const lessons = [lesson(1, "2026-09-30", true)];
    const october = monthCollection(TODAY, TODAY, lessons);
    expect(october.earned).toBe(0);
    const september = monthCollection("2026-09-15", TODAY, lessons);
    expect(september.earned).toBe(1);
    expect(september.slots.some((slot) => slot.state === "next")).toBe(false);
    expect(september.slots.map((slot) => slot.sticker)).toEqual(SEASON_COLLECTIONS.autumn);
  });

  it("assigns a week to today's month, or its Thursday's", () => {
    expect(weekMonth("2026-10-12", TODAY)).toBe(TODAY);
    expect(weekMonth("2026-09-28", TODAY)).toBe("2026-10-01");
    expect(weekMonth("2026-10-26", TODAY)).toBe("2026-10-26");
  });
});
