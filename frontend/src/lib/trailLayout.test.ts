import { describe, expect, it } from "vitest";

import { MAP_HEIGHT, MAP_WIDTH, buildTrailLayout, type Point } from "./trailLayout";

const inside = (p: Point) => p.x > 0 && p.x < MAP_WIDTH && p.y > 0 && p.y < MAP_HEIGHT;
const gap = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.y - b.y);

describe("trail layout", () => {
  it.each([0, 1, 2, 3, 5, 8, 12])("places %i stops along the road, inside the map", (count) => {
    const layout = buildTrailLayout(count);
    expect(layout.stops).toHaveLength(count);
    for (const stop of layout.stops) expect(inside(stop)).toBe(true);
    expect(inside(layout.chest)).toBe(true);
    expect(layout.road.startsWith("M")).toBe(true);
  });

  it("keeps stops apart from each other, the trailhead, and camp", () => {
    for (const count of [1, 3, 6, 8]) {
      const { stops, start, camp } = buildTrailLayout(count);
      const points = [start, ...stops, camp];
      for (let i = 1; i < points.length; i += 1) expect(gap(points[i - 1]!, points[i]!)).toBeGreaterThan(60);
    }
  });

  it("keeps the bonus chest off the stops", () => {
    for (const count of [1, 2, 3, 4, 6, 8]) {
      const { stops, chest } = buildTrailLayout(count);
      for (const stop of stops) expect(gap(stop, chest)).toBeGreaterThan(50);
    }
  });

  it("draws the traveled road up to the current stop", () => {
    const layout = buildTrailLayout(3);
    const toFirst = layout.traveled(0);
    const toCamp = layout.traveled(3);
    expect(toFirst.startsWith("M")).toBe(true);
    expect(toCamp.length).toBeGreaterThan(toFirst.length);
  });
});
