import type { ReactNode } from "react";

import type { Sticker, StickerIcon as IconName } from "../lib/stickers";

// Simple 24×24 drawings in the Sticker Book style: white or tinted fills with
// an ink outline. Colors come from tokens via CSS classes (.sticker-*).
const ICONS: Record<IconName, ReactNode> = {
  star: <path d="M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4 6.7 19.4l1.2-6L3.4 9.3l6-.7z" className="fill-white" />,
  book: (
    <>
      <path d="M3 6c3-1 6-1 9 1v13c-3-2-6-2-9-1z" className="fill-white" />
      <path d="M21 6c-3-1-6-1-9 1v13c3-2 6-2 9-1z" className="fill-white" />
    </>
  ),
  leaf: (
    <>
      <path d="M5 19c8 0 14-6 14-14C11 5 5 11 5 19z" className="fill-white" />
      <path d="M5 19L13 11" fill="none" />
    </>
  ),
  pencil: (
    <>
      <path d="M4 20l4-1 11-11-3-3L5 16z" className="fill-white" />
      <path d="M14 7l3 3" fill="none" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="8.5" className="fill-white" />
      <path d="M3.5 12h17M12 3.5c3 3 3 14 0 17M12 3.5c-3 3-3 14 0 17" fill="none" />
    </>
  ),
  palette: (
    <>
      <path d="M12 3.5c-5 0-8.5 3.6-8.5 8 0 4.2 3.2 8 7.4 8 1.3 0 1.8-.9 1.4-1.9-.5-1.2.2-2.4 1.6-2.4h2.3c2.6 0 4.3-1.8 4.3-4.1 0-4.2-3.6-7.6-8.5-7.6z" className="fill-white" />
      <circle cx="8" cy="10" r="1.3" className="fill-ink" />
      <circle cx="12" cy="7.5" r="1.3" className="fill-ink" />
      <circle cx="16" cy="10" r="1.3" className="fill-ink" />
    </>
  ),
  note: (
    <>
      <path d="M9 17V5l10-2v12" fill="none" />
      <circle cx="7" cy="17" r="2.5" className="fill-white" />
      <circle cx="17" cy="15" r="2.5" className="fill-white" />
    </>
  ),
  heart: <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" className="fill-white" />,
  acorn: (
    <>
      <path d="M6 10h12c0 6-3 10-6 10s-6-4-6-10z" className="fill-white" />
      <path d="M5 10c0-4 3-6 7-6s7 2 7 6z" className="fill-ink" />
      <path d="M12 4V2" fill="none" />
    </>
  ),
  apple: (
    <>
      <path d="M12 7c-2-1.5-7-1-7 5 0 5 3 9 5 9 1 0 1.5-.5 2-.5s1 .5 2 .5c2 0 5-4 5-9 0-6-5-6.5-7-5z" className="fill-white" />
      <path d="M12 7c0-2 1-3 3-4" fill="none" />
    </>
  ),
  owl: (
    <>
      <path d="M6 8c0-3 3-4 6-4s6 1 6 4v6c0 4-3 7-6 7s-6-3-6-7z" className="fill-white" />
      <circle cx="9.5" cy="10" r="1.6" className="fill-ink" />
      <circle cx="14.5" cy="10" r="1.6" className="fill-ink" />
      <path d="M11 13l1 1.5 1-1.5z" className="fill-ink" />
    </>
  ),
  pumpkin: (
    <>
      <path d="M12 7c-5 0-8 3-8 7s3 6 8 6 8-2 8-6-3-7-8-7z" className="fill-white" />
      <path d="M12 7c-2 2-2 11 0 13M12 7c2 2 2 11 0 13M12 7V4l2-1" fill="none" />
    </>
  ),
  snowflake: <path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9M9.5 4.5L12 7l2.5-2.5M9.5 19.5L12 17l2.5 2.5" fill="none" />,
  mitten: <path d="M8 21h8v-4l2-5c1-2.5-.5-4-2-4l-1 3V7a4 4 0 0 0-8 0v10z" className="fill-white" />,
  flower: (
    <>
      <circle cx="12" cy="7" r="3" className="fill-white" />
      <circle cx="7.5" cy="11" r="3" className="fill-white" />
      <circle cx="16.5" cy="11" r="3" className="fill-white" />
      <circle cx="12" cy="11" r="2" className="fill-ink" />
      <path d="M12 14v7" fill="none" />
    </>
  ),
  kite: (
    <>
      <path d="M12 2l6 7-6 9-6-9z" className="fill-white" />
      <path d="M12 18c-1 2 1 2 0 4M6 9h12" fill="none" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4.5" className="fill-white" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" fill="none" />
    </>
  ),
  shell: (
    <>
      <path d="M12 4c-5 0-8 5-8 9l8 7 8-7c0-4-3-9-8-9z" className="fill-white" />
      <path d="M12 4v16M8 6l4 14M16 6l-4 14" fill="none" />
    </>
  ),
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" className="fill-white" />,
  tree: (
    <>
      <path d="M12 3l6 9h-3l4 6H5l4-6H6z" className="fill-white" />
      <path d="M12 18v3" fill="none" />
    </>
  ),
};

/** The icon's shapes alone, for drawing inside another SVG (the trail map). */
export function StickerPaths({ name }: { name: IconName }) {
  return (
    <g className="stroke-ink" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      {ICONS[name]}
    </g>
  );
}

/** A drawn sticker icon; decorative, so callers label the sticker in text. */
export function StickerIcon({ name, size = 28 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      className="stroke-ink"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {ICONS[name]}
    </svg>
  );
}

/** A round sticker: tinted base, white rim, ink ring, a little tilt. */
export function StickerBadge({
  sticker,
  size = 64,
  tilt = 0,
  earned = true,
}: {
  sticker: Sticker;
  size?: number;
  tilt?: number;
  earned?: boolean;
}) {
  return (
    <span
      className={earned ? `sticker sticker-${sticker.tone}` : "sticker sticker-empty"}
      style={{ width: size, height: size, transform: `rotate(${tilt}deg)` }}
    >
      <StickerIcon name={sticker.icon} size={Math.round(size * 0.52)} />
    </span>
  );
}
