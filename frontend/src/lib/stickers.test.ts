import { describe, expect, it } from "vitest";

import { SEASON_COLLECTIONS, campPrize, lessonSticker } from "./stickers";

describe("stickers", () => {
  it("picks a sticker from the subject, then the book, then the title", () => {
    expect(lessonSticker({ title: "Lesson 42", resource_title: "Saxon Math 5/4" }).label).toBe("Math");
    expect(lessonSticker({ title: "Read The Wild Robot, ch. 3" }).label).toBe("Reading");
    expect(lessonSticker({ title: "Spelling list 6" }).label).toBe("Writing");
    expect(lessonSticker({ title: "States of matter", subject_name: "Science" }).label).toBe("Science");
    expect(lessonSticker({ title: "Something else" }).label).toBe("Star");
  });

  it("gives camp a seasonal prize that follows the date", () => {
    expect(campPrize("2026-10-01")).toEqual(SEASON_COLLECTIONS.autumn[0]);
    expect(campPrize("2026-10-14")).toEqual(SEASON_COLLECTIONS.autumn[5]);
    expect(campPrize("2026-12-25")).toEqual(SEASON_COLLECTIONS.winter[0]);
    for (const collection of Object.values(SEASON_COLLECTIONS)) expect(collection).toHaveLength(8);
  });
});
