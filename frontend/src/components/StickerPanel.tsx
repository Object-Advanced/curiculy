import type { Lesson } from "../api/client";
import { BONUS_STICKER, lessonSticker, type Sticker } from "../lib/stickers";
import { StickerBadge } from "./StickerIcon";

interface StickerPanelProps {
  lessons: Lesson[];
  bonusSolved: boolean;
  campReached: boolean;
  prize: Sticker;
}

/** One slot per stop, plus the bonus and the camp prize. */
export function StickerPanel({ lessons, bonusSolved, campReached, prize }: StickerPanelProps) {
  const done = lessons.filter((lesson) => lesson.status === "completed").length;
  return (
    <section className="kid-card sticker-panel" aria-labelledby="stickers-title">
      <h2 id="stickers-title" className="kid-card-title">
        Today’s stickers
      </h2>
      <p className="kid-card-sub">
        {lessons.length ? `${done} of ${lessons.length} stops done` : "No stops today"}
      </p>
      <ul className="sticker-slots">
        {lessons.map((lesson, index) => {
          const sticker = lessonSticker(lesson);
          const earned = lesson.status === "completed";
          return (
            <li key={lesson.id} className="sticker-slot">
              <StickerBadge sticker={sticker} size={60} tilt={earned ? (index % 2 ? 7 : -7) : 0} earned={earned} />
              <span className="sticker-slot-label">
                {sticker.label}
                <span className="sr-only">{earned ? ", earned" : ", not yet"}</span>
              </span>
            </li>
          );
        })}
        <li className="sticker-slot">
          <StickerBadge sticker={BONUS_STICKER} size={60} tilt={bonusSolved ? -5 : 0} earned={bonusSolved} />
          <span className="sticker-slot-label">
            Bonus<span className="sr-only">{bonusSolved ? ", earned" : ", not yet"}</span>
          </span>
        </li>
        {lessons.length > 0 && (
          <li className="sticker-slot sticker-slot-camp">
            <StickerBadge sticker={prize} size={60} tilt={campReached ? 8 : 0} earned={campReached} />
            <span className="sticker-slot-label">
              Camp: {prize.label}
              <span className="sr-only">{campReached ? ", earned" : ", reach camp to earn it"}</span>
            </span>
          </li>
        )}
      </ul>
    </section>
  );
}
