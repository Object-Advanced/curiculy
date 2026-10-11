import { describe, expect, it } from "vitest";

import { buildDailySpark, gradeBand, mulberry32, puzzleWords, sparkSolvedKey } from "./spark";

const lessons = [
  { title: "Fractions worksheet", resource_title: null, scheduled_date: "2026-10-14" },
  { title: "Read The Hobbit, chapter 2", resource_title: "The Hobbit", scheduled_date: "2026-10-14" },
  { title: "Tomorrow's lesson", resource_title: null, scheduled_date: "2026-10-15" },
];

describe("daily puzzle", () => {
  it("is the same all day for the same child", () => {
    const a = buildDailySpark({ id: 7, grade: "4" }, lessons, "2026-10-14");
    const b = buildDailySpark({ id: 7, grade: "4" }, lessons, "2026-10-14");
    expect(a).toEqual(b);
  });

  it("changes with the day", () => {
    const days = ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"];
    const prompts = new Set(days.map((iso) => buildDailySpark({ id: 7, grade: "4" }, lessons, iso).prompt));
    expect(prompts.size).toBeGreaterThan(1);
  });

  it("always has an answer it can check", () => {
    for (let id = 1; id < 60; id += 1) {
      for (const grade of ["K", "1", "4", "8", null]) {
        const spark = buildDailySpark({ id, grade }, lessons, "2026-10-14");
        expect(spark.answer).toBeTruthy();
        if (spark.kind === "choice") expect(spark.choices).toContain(spark.answer);
        if (spark.kind === "scramble") expect(spark.prompt.toLowerCase()).not.toContain(spark.answer.toLowerCase());
      }
    }
  });

  it("picks words only from today's lessons", () => {
    for (let id = 1; id < 40; id += 1) {
      const spark = buildDailySpark({ id, grade: "4" }, lessons, "2026-10-14");
      if (spark.kind === "scramble") expect(["Fractions", "worksheet", "Hobbit"]).toContain(spark.answer);
    }
  });

  it("matches the legacy helpers", () => {
    expect(gradeBand("K")).toBe("early");
    expect(gradeBand("2")).toBe("early");
    expect(gradeBand("5")).toBe("elem");
    expect(gradeBand("9")).toBe("older");
    expect(gradeBand("")).toBe("elem");
    expect(puzzleWords("Read The Hobbit, chapter 2")).toEqual(["Hobbit"]);
    // Reference values printed by the legacy app.js mulberry32.
    const rand = mulberry32(42);
    expect(rand()).toBe(0.6011037519201636);
    expect(rand()).toBe(0.44829055899754167);
    expect(mulberry32(120261014)()).toBe(0.6914955663960427);
    expect(sparkSolvedKey(3, "2026-10-14")).toBe("curiculy-spark-3-2026-10-14");
  });
});
