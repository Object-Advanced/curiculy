// Where the trail, its stops, the bonus chest and camp sit on the map.
//
// The road is a smooth curve (Catmull-Rom through fixed waypoints) that winds
// from the trailhead at the bottom left to camp at the top right. Stops are
// spaced evenly along its length, however many lessons there are today, so the
// map works for one lesson or eight. Pure geometry: no React, easy to test.

export interface Point {
  x: number;
  y: number;
}

export interface TrailLayout {
  width: number;
  height: number;
  road: string;
  start: Point;
  stops: Point[];
  camp: Point;
  chest: Point;
  spur: string;
  /** Road from the trailhead to stop `index` (or to camp when index ≥ stops). */
  traveled: (index: number) => string;
}

export const MAP_WIDTH = 800;
export const MAP_HEIGHT = 560;
const MARGIN = 56;

const WAYPOINTS: Point[] = [
  { x: 70, y: 500 },
  { x: 250, y: 515 },
  { x: 440, y: 470 },
  { x: 620, y: 470 },
  { x: 720, y: 395 },
  { x: 610, y: 320 },
  { x: 410, y: 305 },
  { x: 220, y: 285 },
  { x: 120, y: 205 },
  { x: 230, y: 120 },
  { x: 450, y: 105 },
  { x: 630, y: 115 },
  { x: 730, y: 70 },
];

const SAMPLES_PER_SEGMENT = 32;

type Segment = [Point, Point, Point, Point];

function segments(points: Point[]): Segment[] {
  const out: Segment[] = [];
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[Math.max(i - 1, 0)]!;
    const p1 = points[i]!;
    const p2 = points[i + 1]!;
    const p3 = points[Math.min(i + 2, points.length - 1)]!;
    out.push([
      p1,
      { x: p1.x + (p2.x - p0.x) / 6, y: p1.y + (p2.y - p0.y) / 6 },
      { x: p2.x - (p3.x - p1.x) / 6, y: p2.y - (p3.y - p1.y) / 6 },
      p2,
    ]);
  }
  return out;
}

function cubic([a, b, c, d]: Segment, t: number): Point {
  const u = 1 - t;
  return {
    x: u * u * u * a.x + 3 * u * u * t * b.x + 3 * u * t * t * c.x + t * t * t * d.x,
    y: u * u * u * a.y + 3 * u * u * t * b.y + 3 * u * t * t * c.y + t * t * t * d.y,
  };
}

const round = (n: number) => Math.round(n * 10) / 10;
const fmt = (p: Point) => `${round(p.x)} ${round(p.y)}`;

function polyline(points: Point[]): string {
  return points.map((p, i) => `${i === 0 ? "M" : "L"}${fmt(p)}`).join(" ");
}

export function buildTrailLayout(stopCount: number): TrailLayout {
  const segs = segments(WAYPOINTS);
  const road = `M${fmt(WAYPOINTS[0]!)} ` + segs.map(([, b, c, d]) => `C${fmt(b)} ${fmt(c)} ${fmt(d)}`).join(" ");

  // Sample the road and measure it, so stops can sit at even distances.
  const samples: Point[] = [WAYPOINTS[0]!];
  for (const seg of segs) {
    for (let k = 1; k <= SAMPLES_PER_SEGMENT; k += 1) samples.push(cubic(seg, k / SAMPLES_PER_SEGMENT));
  }
  const lengths = [0];
  for (let i = 1; i < samples.length; i += 1) {
    const a = samples[i - 1]!;
    const b = samples[i]!;
    lengths.push(lengths[i - 1]! + Math.hypot(b.x - a.x, b.y - a.y));
  }
  const total = lengths.at(-1)!;

  const indexAt = (distance: number) => {
    let i = lengths.findIndex((len) => len >= distance);
    if (i === -1) i = samples.length - 1;
    return i;
  };
  const pointAt = (distance: number): Point => samples[indexAt(distance)]!;

  const count = Math.max(0, Math.floor(stopCount));
  const stopDistances = Array.from({ length: count }, (_, i) => (total * (i + 1)) / (count + 1));
  const stops = stopDistances.map(pointAt);
  const start = WAYPOINTS[0]!;
  const camp = WAYPOINTS.at(-1)!;

  // The bonus chest sits beside the middle of the road, on whichever side is
  // further from every stop, kept inside the map.
  const midIndex = indexAt(total / 2);
  const mid = samples[midIndex]!;
  const ahead = samples[Math.min(midIndex + 1, samples.length - 1)]!;
  const behind = samples[Math.max(midIndex - 1, 0)]!;
  const tx = ahead.x - behind.x;
  const ty = ahead.y - behind.y;
  const norm = Math.hypot(tx, ty) || 1;
  const offset = 92;
  const clamp = (p: Point): Point => ({
    x: Math.min(MAP_WIDTH - MARGIN, Math.max(MARGIN, p.x)),
    y: Math.min(MAP_HEIGHT - MARGIN, Math.max(MARGIN, p.y)),
  });
  const candidates = [1, -1].map((side) =>
    clamp({ x: mid.x + (side * -ty * offset) / norm, y: mid.y + (side * tx * offset) / norm }),
  );
  const clearance = (p: Point) =>
    Math.min(Infinity, ...[...stops, start, camp].map((s) => Math.hypot(s.x - p.x, s.y - p.y)));
  const chest = clearance(candidates[0]!) >= clearance(candidates[1]!) ? candidates[0]! : candidates[1]!;
  const bend = { x: (mid.x + chest.x) / 2 + (chest.y - mid.y) * 0.25, y: (mid.y + chest.y) / 2 - (chest.x - mid.x) * 0.25 };
  const spur = `M${fmt(mid)} Q${fmt(bend)} ${fmt(chest)}`;

  const traveled = (index: number) => {
    const distance = index >= count ? total : (stopDistances[index] ?? 0);
    return polyline(samples.slice(0, indexAt(distance) + 1));
  };

  return { width: MAP_WIDTH, height: MAP_HEIGHT, road, start, stops, camp, chest, spur, traveled };
}
