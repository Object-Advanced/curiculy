import { useMemo } from "react";

import type { Sticker } from "../lib/stickers";
import { buildTrailLayout, type Point } from "../lib/trailLayout";
import { StickerPaths } from "./StickerIcon";

export interface TrailStop {
  id: number;
  done: boolean;
  sticker: Sticker;
}

interface TrailMapProps {
  stops: TrailStop[];
  /** Index of the next unfinished stop; equals stops.length when all are done. */
  currentIndex: number;
  bonusSolved: boolean;
  initial: string;
  /** The stop that was just checked off, for a little pop. */
  poppedId?: number | null;
  label: string;
}

const STOP_R = 30;

function Tree({ x, y, r, tone }: { x: number; y: number; r: number; tone: 1 | 2 | 3 }) {
  return (
    <g className="trail-tree">
      <path d={`M${x} ${y + r + 22}v-${r}`} className="trail-ink-line" />
      <circle cx={x} cy={y} r={r} className={`trail-tree-${tone}`} />
    </g>
  );
}

function Stop({ stop, index, point, current, popped }: { stop: TrailStop; index: number; point: Point; current: boolean; popped: boolean }) {
  if (stop.done) {
    return (
      <g transform={`translate(${point.x} ${point.y})`}>
        <g className={popped ? "stop-pop" : undefined}>
        <g transform={`rotate(${index % 2 === 0 ? -8 : 7})`}>
          <circle r={STOP_R} className={`trail-stop-done sticker-fill-${stop.sticker.tone}`} />
          <g transform="translate(-18 -18) scale(1.5)">
            <StickerPaths name={stop.sticker.icon} />
          </g>
        </g>
        <g transform={`translate(${STOP_R * 0.72} ${STOP_R * 0.72})`}>
          <circle r="12" className="trail-check" />
          <path d="M-5 0.5l3.5 3.5L5.5-4" className="trail-check-mark" />
        </g>
        </g>
      </g>
    );
  }
  if (current) {
    return (
      <g transform={`translate(${point.x} ${point.y})`}>
        <circle r={STOP_R + 12} className="trail-halo" />
        <circle r={STOP_R + 4} className="trail-stop-current" />
        <text className="trail-stop-number trail-stop-number-current" dy="0.35em">
          {index + 1}
        </text>
      </g>
    );
  }
  return (
    <g transform={`translate(${point.x} ${point.y})`}>
      <circle r={STOP_R} className="trail-stop-next" />
      <text className="trail-stop-number" dy="0.35em">
        {index + 1}
      </text>
    </g>
  );
}

/**
 * Today's lessons as stops on a winding trail to camp. Purely visual: the stop
 * list beside it carries the titles and the "I did it!" buttons, so the map is
 * one labelled image for screen readers.
 */
export function TrailMap({ stops, currentIndex, bonusSolved, initial, poppedId, label }: TrailMapProps) {
  const layout = useMemo(() => buildTrailLayout(stops.length), [stops.length]);
  const allDone = stops.length > 0 && currentIndex >= stops.length;
  const here = allDone ? layout.camp : currentIndex < stops.length ? layout.stops[currentIndex] : layout.start;

  return (
    <svg
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      className="trail-map"
      role="img"
      aria-label={label}
      preserveAspectRatio="xMidYMid meet"
    >
      <rect width={layout.width} height={layout.height} className="trail-paper" />
      <circle cx="84" cy="78" r="30" className="trail-sun" />
      <rect x="232" y="46" width="112" height="34" rx="17" className="trail-cloud" />
      <rect x="520" y="200" width="84" height="28" rx="14" className="trail-cloud" />
      <path d="M0 430 C150 380 300 430 430 410 C560 388 690 360 800 372 L800 560 L0 560z" className="trail-hill-1" />
      <path d="M0 505 C170 470 340 520 510 500 C630 486 720 482 800 488 L800 560 L0 560z" className="trail-hill-2" />
      <Tree x={60} y={300} r={24} tone={1} />
      <Tree x={330} y={196} r={20} tone={2} />
      <Tree x={760} y={250} r={22} tone={3} />
      <Tree x={500} y={380} r={18} tone={1} />
      <Tree x={150} y={420} r={16} tone={3} />

      <g aria-hidden="true">
        <path d={layout.road} className="trail-road-edge" />
        <path d={layout.spur} className="trail-spur-edge" />
        <path d={layout.road} className="trail-road" />
        <path d={layout.spur} className="trail-spur" />
        {stops.length > 0 && <path d={layout.traveled(currentIndex)} className="trail-road-traveled" />}
        <path d={layout.road} className="trail-road-dash" />

        <g transform={`translate(${layout.start.x - 34} ${layout.start.y - 52})`}>
          <rect width="68" height="28" rx="10" className="trail-sign" />
          <text x="34" y="14" dy="0.35em" className="trail-sign-text">
            Start
          </text>
        </g>

        <g transform={`translate(${layout.chest.x} ${layout.chest.y})`}>
          <rect x="-32" y="-32" width="64" height="64" rx="18" className={bonusSolved ? "trail-chest trail-chest-open" : "trail-chest"} />
          <g transform="translate(-16 -16) scale(1.35)">
            {bonusSolved ? (
              <StickerPaths name="star" />
            ) : (
              <g className="stroke-ink" fill="none" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="9" width="18" height="11" rx="2" className="fill-white" />
                <path d="M3 13h18M12 12v3M5 9c0-3 3-5 7-5s7 2 7 5" />
              </g>
            )}
          </g>
        </g>

        <g transform={`translate(${layout.camp.x} ${layout.camp.y})`} className={allDone ? "camp-reached" : undefined}>
          <rect x="-44" y="-40" width="88" height="80" rx="24" className="trail-camp" />
          <path d="M0 -26v12" className="trail-ink-line" />
          <path d="M0 -26l14 5-14 5z" className={allDone ? "trail-flag trail-flag-up" : "trail-flag"} />
          <path d="M-30 26L0 -14l30 40z" className="trail-tent" />
          <path d="M-10 26l10-18 10 18z" className="trail-tent-door" />
        </g>

        {stops.map((stop, index) => (
          <Stop
            key={stop.id}
            stop={stop}
            index={index}
            point={layout.stops[index]!}
            current={index === currentIndex}
            popped={poppedId === stop.id}
          />
        ))}

        {here && (
          <g transform={`translate(${here.x + 26} ${here.y - 34})`} className="trail-marker">
            <circle r="20" className="trail-marker-dot" />
            <text className="trail-marker-text" dy="0.35em">
              {initial}
            </text>
          </g>
        )}
      </g>
    </svg>
  );
}
