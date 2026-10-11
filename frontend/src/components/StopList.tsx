import type { Lesson } from "../api/client";
import { lessonSticker } from "../lib/stickers";
import { StickerBadge } from "./StickerIcon";

/** The parent's own note, without lines older builds logged into it. */
export function parentNoteText(notes: string | null | undefined): string {
  return String(notes || "")
    .split("\n")
    .filter((line) => line.trim() && !line.trim().startsWith("[Homework help]"))
    .join("\n")
    .trim();
}

interface StopListProps {
  lessons: Lesson[];
  currentIndex: number;
  busyId: number | null;
  onDone: (lesson: Lesson) => void;
  onUndo: (lesson: Lesson) => void;
}

/** Today's stops in order, each pointing at the family's own materials. */
export function StopList({ lessons, currentIndex, busyId, onDone, onUndo }: StopListProps) {
  return (
    <ol className="stop-list" aria-label="Today's stops">
      {lessons.map((lesson, index) => {
        const done = lesson.status === "completed";
        const current = index === currentIndex;
        const sticker = lessonSticker(lesson);
        const note = parentNoteText(lesson.notes);
        const busy = busyId === lesson.id;
        return (
          <li
            key={lesson.id}
            className={`stop-item${done ? " is-done" : ""}${current ? " is-current" : ""}`}
            aria-current={current ? "step" : undefined}
          >
            <span className="stop-badge" aria-hidden="true">
              {done ? <StickerBadge sticker={sticker} size={44} tilt={index % 2 ? 6 : -6} /> : <span className="stop-number">{index + 1}</span>}
            </span>
            <div className="stop-copy">
              {current && <p className="stop-kicker">You are here</p>}
              <p className="stop-title">{lesson.title}</p>
              {lesson.resource_title && <p className="stop-meta">From {lesson.resource_title}</p>}
              {note && <p className="stop-note">Note: {note}</p>}
              {done && <p className="stop-earned">Done! {sticker.label} sticker earned</p>}
            </div>
            {done ? (
              <button
                type="button"
                className="kid-btn kid-btn-quiet"
                onClick={() => onUndo(lesson)}
                disabled={busy}
                aria-label={`Not done yet: ${lesson.title}`}
              >
                Not done yet
              </button>
            ) : (
              <button
                type="button"
                className="kid-btn kid-btn-primary"
                onClick={() => onDone(lesson)}
                disabled={busy}
                aria-label={`I did it: ${lesson.title}`}
              >
                I did it!
              </button>
            )}
          </li>
        );
      })}
    </ol>
  );
}
