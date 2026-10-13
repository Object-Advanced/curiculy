import { describe, expect, it } from "vitest";

import { nextMonday, numberedLessons, parseChapters, parseLessons } from "./structure";

describe("pasting chapters", () => {
  it("reads the start page wherever the line ends", () => {
    const { rows, skipped } = parseChapters(
      ["Addition, 5", "1. Fractions ........ 62", "Chapter 3: Time — p. 101", "", "Contents"].join("\n"),
    );
    expect(rows).toEqual([
      { name: "Addition", start_page: 5 },
      { name: "1. Fractions", start_page: 62 },
      { name: "Chapter 3: Time", start_page: 101 },
    ]);
    expect(skipped).toBe(1);
  });
});

describe("pasting lessons", () => {
  it("reads numbers, names, types and pages", () => {
    const { rows } = parseLessons(
      ["12 The Lost Dog 45-49", "Lesson 13: Home Again, pp. 50–53", "Test 2, 54-55", "Quiz 3 p. 56", "Rest Day"].join("\n"),
    );
    expect(rows).toEqual([
      { number: 12, name: "The Lost Dog", type: "lesson", start_page: 45, end_page: 49 },
      { number: 13, name: "Home Again", type: "lesson", start_page: 50, end_page: 53 },
      { number: 14, name: "Test 2", type: "test", start_page: 54, end_page: 55 },
      { number: 15, name: "Quiz 3", type: "quiz", start_page: 56, end_page: 56 },
      { number: 16, name: "Rest Day", type: "lesson", start_page: null, end_page: null },
    ]);
  });

  it("numbers lessons on from where you start", () => {
    expect(parseLessons("Adding\nSubtracting", 5).rows.map((row) => row.number)).toEqual([5, 6]);
  });

  it("makes numbered lessons to fill in", () => {
    expect(numberedLessons(3, 1).map((row) => row.number)).toEqual([1, 2, 3]);
  });
});

describe("start dates", () => {
  it("starts on Monday", () => {
    expect(nextMonday("2026-10-12")).toBe("2026-10-12");
    expect(nextMonday("2026-10-14")).toBe("2026-10-19");
    expect(nextMonday("2026-10-18")).toBe("2026-10-19");
  });
});
