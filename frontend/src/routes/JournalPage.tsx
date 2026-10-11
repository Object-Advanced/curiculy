import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useKid } from "../api/kid";
import { useLessonsBetween } from "../api/queries";
import { ChildPicker } from "../components/ChildPicker";
import { KidHeader } from "../components/KidHeader";
import { StickerBadge, StickerIcon } from "../components/StickerIcon";
import { addDays, monthEnd, monthStart, rangeLabel, seasonOf, todayISO, weekStart, weekdayLong } from "../lib/dates";
import { journalWeek, monthCollection, weekMonth, type EarnedSticker, type JournalDay } from "../lib/journal";

const MONDAY = /^\d{4}-\d{2}-\d{2}$/;

function campLabel(day: JournalDay): string | null {
  if (day.camp === "reached") return "Camp!";
  if (day.camp === "open" || day.camp === "missed") return "Camp";
  return null;
}

function Tent({ reached }: { reached: boolean }) {
  return (
    <svg width="30" height="30" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <path d="M6 40L24 12l18 28z" className={reached ? "journal-tent journal-tent-up" : "journal-tent"} />
      {reached && <path d="M18 40l6-12 6 12z" className="journal-tent-door" />}
    </svg>
  );
}

function detailText(item: EarnedSticker): string {
  const when = weekdayLong(item.day);
  return item.dated
    ? `Your ${item.sticker.label} sticker is from “${item.title}”, finished on ${when}.`
    : `Your ${item.sticker.label} sticker is from “${item.title}”, on ${when}.`;
}

/**
 * The Sticker journal: this week's stickers by day, camp tents, and the
 * month's seasonal collection. Read-only; stickers come from finished lessons.
 */
export function JournalPage() {
  const today = useMemo(() => todayISO(), []);
  const thisMonday = weekStart(today);
  const [params, setParams] = useSearchParams();
  const requested = params.get("week") ?? "";
  const monday = MONDAY.test(requested) && weekStart(requested) <= thisMonday ? weekStart(requested) : thisMonday;
  const sunday = addDays(monday, 6);
  const isThisWeek = monday === thisMonday;
  const month = weekMonth(monday, today);

  const kid = useKid();
  const { isChild, students, studentId, name } = kid;
  // Lessons scheduled up to a month before can be finished this week, and the
  // collection needs the whole month.
  const from = addDays(monday < monthStart(month) ? monday : monthStart(month), -31);
  const to = sunday > monthEnd(month) ? sunday : monthEnd(month);
  const range = useLessonsBetween(studentId, from, to);
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.persona = "kid";
    root.dataset.season = seasonOf(today);
    document.title = `${name}’s sticker journal · Curiculy`;
  }, [name, today]);
  useEffect(() => setSelected(null), [monday, studentId]);

  const goToWeek = (iso: string) => {
    const next = new URLSearchParams(params);
    if (iso === thisMonday) next.delete("week");
    else next.set("week", iso);
    setParams(next);
  };

  if (kid.error || range.isError) {
    return (
      <main className="trail-page">
        <section className="kid-card" role="alert">
          <h1 className="kid-card-title">We couldn’t load your journal</h1>
          <p className="kid-card-sub">Check the internet, then try again.</p>
          <button type="button" className="kid-btn kid-btn-primary" onClick={() => void range.refetch()}>
            Try again
          </button>
        </section>
      </main>
    );
  }

  if (kid.loading || (studentId !== null && range.isPending)) {
    return (
      <main className="trail-page" aria-busy="true">
        <p className="kid-card-sub">Opening your sticker journal…</p>
      </main>
    );
  }

  if (studentId === null) {
    return (
      <main className="trail-page">
        <section className="kid-card">
          <h1 className="kid-card-title">No journal yet</h1>
          <p className="kid-card-sub">Add a child in Settings to see their sticker journal.</p>
          <a className="kid-btn" href="/#/settings/students">
            Open Settings
          </a>
        </section>
      </main>
    );
  }

  const lessons = range.data ?? [];
  const days = journalWeek(monday, today, lessons);
  const weekStickers = days.reduce((sum, day) => sum + day.stickers.length, 0);
  const collection = monthCollection(month, today, lessons);
  const chosen = days.flatMap((day) => day.stickers).find((item) => item.lessonId === selected) ?? null;
  const line = weekStickers
    ? `${weekStickers} ${weekStickers === 1 ? "sticker" : "stickers"} ${isThisWeek ? "this week" : "that week"}`
    : isThisWeek
      ? "Stickers you earn this week land here."
      : "No stickers that week.";
  const friday = addDays(monday, 4);
  const lastDay = days.at(-1)?.iso ?? friday;

  return (
    <main className="trail-page">
      <KidHeader
        name={name}
        line={line}
        current="journal"
        backHref={kid.backHref}
        backLabel={kid.backLabel}
        search={kid.search}
      />

      {!isChild && students.data && students.data.length > 0 && (
        <ChildPicker students={students.data} currentId={studentId} name={name} onPick={kid.selectStudent} />
      )}

      <div className="journal-book">
        <section className="journal-sheet journal-sheet-week" aria-labelledby="week-title">
          <div className="journal-sheet-head">
            <div>
              <h2 id="week-title" className="journal-title">
                {isThisWeek ? "This week" : "That week"}
              </h2>
              <p className="kid-card-sub">{rangeLabel(monday, lastDay > friday ? lastDay : friday)}</p>
            </div>
            <div className="journal-week-nav">
              <button type="button" className="kid-btn kid-btn-quiet" onClick={() => goToWeek(addDays(monday, -7))}>
                ‹ Week before
              </button>
              <button
                type="button"
                className="kid-btn kid-btn-quiet"
                onClick={() => goToWeek(addDays(monday, 7))}
                disabled={isThisWeek}
              >
                Week after ›
              </button>
            </div>
          </div>

          <ol className="journal-days" aria-label="Stickers by day">
            {days.map((day) => {
              const camp = campLabel(day);
              const left = day.planned - day.done;
              return (
                <li key={day.iso} className={`journal-day${day.isToday ? " is-today" : ""}${day.isFuture ? " is-future" : ""}`}>
                  <span className="journal-day-label">
                    <span className="journal-day-name">{day.isToday ? "Today" : day.weekday}</span>
                    <span className="journal-day-number">{day.dayNumber}</span>
                  </span>
                  <div className="journal-day-stickers">
                    {day.stickers.map((item, index) => (
                      <button
                        key={item.lessonId}
                        type="button"
                        className="journal-sticker"
                        aria-pressed={selected === item.lessonId}
                        aria-label={`${item.sticker.label} sticker: ${item.title}`}
                        onClick={() => setSelected(selected === item.lessonId ? null : item.lessonId)}
                      >
                        <StickerBadge sticker={item.sticker} size={52} tilt={index % 2 ? 6 : -7} />
                      </button>
                    ))}
                    {day.stickers.length === 0 && (
                      <span className="journal-day-empty">
                        {day.isFuture ? "Coming up" : day.planned === 0 ? "Rest day" : <span className="sr-only">No stickers on this day</span>}
                      </span>
                    )}
                    {day.isToday && day.camp === "open" && (
                      <Link to={{ pathname: "/trail", search: kid.search }} className="kid-chip journal-to-trail">
                        {left} {left === 1 ? "stop" : "stops"} to go
                      </Link>
                    )}
                  </div>
                  {camp && (
                    <span className={`journal-camp camp-${day.camp}`}>
                      <Tent reached={day.camp === "reached"} />
                      <span>{camp}</span>
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
          <p className="journal-detail" aria-live="polite">
            {chosen ? detailText(chosen) : weekStickers ? "Tap a sticker to see which lesson earned it." : ""}
          </p>
        </section>

        <div className="journal-spine" aria-hidden="true">
          {[0, 1, 2, 3, 4].map((ring) => (
            <span key={ring} className="journal-ring" />
          ))}
        </div>

        <section className="journal-sheet journal-sheet-collection" aria-labelledby="collection-title">
          <div className="journal-sheet-head">
            <h2 id="collection-title" className="journal-title">
              {collection.title}
            </h2>
            <p className="kid-card-sub">
              {collection.earned} of {collection.slots.length}
            </p>
          </div>
          <p className="journal-collection-note">Every time you reach camp, a new one joins your page.</p>
          <ul className="journal-collection">
            {collection.slots.map((slot, index) => (
              <li key={slot.sticker.label} className={`journal-slot is-${slot.state}`}>
                {slot.state === "mystery" ? (
                  <span className="sticker sticker-empty journal-mystery" aria-hidden="true">
                    ?
                  </span>
                ) : (
                  <span className={slot.state === "next" ? "journal-next" : undefined}>
                    <StickerBadge sticker={slot.sticker} size={76} tilt={slot.state === "earned" ? (index % 2 ? 7 : -6) : 0} earned={slot.state === "earned"} />
                  </span>
                )}
                <span className="journal-slot-label">
                  {slot.state === "earned" ? slot.sticker.label : slot.state === "next" ? "Today’s prize" : "Mystery"}
                  {slot.state === "next" && <span className="sr-only">: reach camp today to earn the {slot.sticker.label}</span>}
                </span>
              </li>
            ))}
          </ul>
          <p className="journal-collection-note journal-hint">
            <StickerIcon name="star" size={18} />
            <span>
              Finish every stop on <Link to={{ pathname: "/trail", search: kid.search }}>My trail</Link> to reach camp.
            </span>
          </p>
        </section>
      </div>
    </main>
  );
}
