import { describe, expect, it } from "vitest";

import { dayOf, monthOf, seasonOf, todayISO } from "./dates";

describe("dates", () => {
  it("uses the device's local calendar day", () => {
    expect(todayISO(new Date(2026, 9, 14, 23, 30))).toBe("2026-10-14");
    expect(todayISO(new Date(2026, 0, 3, 0, 5))).toBe("2026-01-03");
  });

  it("reads month and day", () => {
    expect(monthOf("2026-10-14")).toBe(9);
    expect(dayOf("2026-10-14")).toBe(14);
  });

  it("maps months to seasons", () => {
    expect(seasonOf("2026-10-14")).toBe("autumn");
    expect(seasonOf("2026-12-01")).toBe("winter");
    expect(seasonOf("2027-02-28")).toBe("winter");
    expect(seasonOf("2027-04-10")).toBe("spring");
    expect(seasonOf("2027-07-04")).toBe("summer");
  });
});
