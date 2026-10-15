import { useEffect, useState } from "react";

import {
  useAttendanceDays,
  useAttendanceSummary,
  useConfirmAttendance,
  type AttendanceDay,
  type AttendanceSummary,
} from "../api/parent";
import { DayCard } from "../components/attendance/DayCard";
import { ErrorLine } from "../components/ui/Fields";
import { addDays, shortDate, weekdayLong } from "../lib/dates";

const SWEEP_DAYS = 14;

function hoursLabel(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours} h${rest ? ` ${rest} min` : ""}` : `${rest} min`;
}

function YearSoFar({ summary }: { summary: AttendanceSummary }) {
  const hours = summary.count_by === "hours";
  if (!summary.school_year_id) {
    return <p className="notice">Set up your school year in Settings, and the year's counts show here.</p>;
  }
  return (
    <section className="stack" aria-labelledby="year-so-far">
      <h2 className="section-title" id="year-so-far">
        {summary.school_year_name}: the year so far
      </h2>
      <ul className="attendance-summary">
        {summary.children.map((child) => {
          const others = [
            child.field_trip_days ? `${child.field_trip_days} field trip${child.field_trip_days === 1 ? "" : "s"}` : null,
            `${child.sick_days} sick`,
            `${child.absent_days} absent`,
          ].filter(Boolean);
          return (
            <li key={child.student_id} className="card stack">
              <h3 className="card-title">{child.name}</h3>
              <p className="attendance-count">
                {hours ? (
                  <>
                    <strong>{hoursLabel(child.minutes)}</strong> of school
                  </>
                ) : (
                  <>
                    <strong>{child.present_days}</strong> day{child.present_days === 1 ? "" : "s"} present
                  </>
                )}
              </p>
              <p className="small muted">
                {hours ? `${child.present_days} day${child.present_days === 1 ? "" : "s"} present · ` : ""}
                {others.join(" · ")}
              </p>
              {!hours && summary.end_date ? (
                <p className="small">
                  On track for {child.on_track_days} days by {shortDate(summary.end_date)}, with {child.school_days_left} school
                  day{child.school_days_left === 1 ? "" : "s"} left on your calendar.
                </p>
              ) : null}
              {hours && child.lessons_without_minutes ? (
                <p className="small muted">
                  {child.lessons_without_minutes} finished lesson{child.lessons_without_minutes === 1 ? " has" : "s have"} no
                  minutes yet, so they add nothing. Add minutes in the lesson editor, or set a day's minutes above.
                </p>
              ) : null}
              {child.unmarked_days ? (
                <p>
                  <span className="badge badge-missing">
                    {child.unmarked_days} school day{child.unmarked_days === 1 ? "" : "s"} not marked
                  </span>
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
      <p className="small muted">
        Your state's requirement shows here once Curiculy checks your state's rules.
      </p>
    </section>
  );
}

/** One unmarked day in the sweep, on one line: confirm its suggestions, or open it to change. */
function SweepDay({ day, hours }: { day: AttendanceDay; hours: boolean }) {
  const confirm = useConfirmAttendance();
  const [open, setOpen] = useState(false);
  const title = `${weekdayLong(day.date)}, ${shortDate(day.date)}`;
  const suggested = day.children.filter((child) => !child.status && child.suggestion);
  const summary = day.children
    .filter((child) => child.expected || child.status)
    .map((child) => `${child.name}: ${child.status ?? (child.suggestion ? `${child.suggestion} (suggested)` : "not marked")}`)
    .join(" · ");
  return (
    <li className="sweep-day">
      <div className="row-between">
        <p>
          <strong>{title}</strong> <span className="small muted">{summary}</span>
        </p>
        <div className="row">
          {suggested.length ? (
            <button
              type="button"
              className="btn btn-small"
              disabled={confirm.isPending}
              aria-label={`Looks right: ${title}`}
              onClick={() =>
                confirm.mutate(
                  suggested.map((child) => ({ student_id: child.student_id, date: day.date, status: child.suggestion! })),
                )
              }
            >
              Looks right
            </button>
          ) : null}
          <button
            type="button"
            className="btn btn-quiet btn-small"
            aria-expanded={open}
            aria-label={`${open ? "Close" : "Change"} ${title}`}
            onClick={() => setOpen(!open)}
          >
            {open ? "Close" : "Change"}
          </button>
        </div>
      </div>
      {open ? <DayCard day={day} hours={hours} title={title} /> : null}
      <ErrorLine error={confirm.error} />
    </li>
  );
}

/**
 * Attendance: "School today?" for every child, pre-filled from the day's
 * work and saved with one tap; the school days of the last two weeks that
 * aren't marked; and each child's year so far. Nothing is recorded without
 * the parent's tap.
 */
export function AttendancePage() {
  const today = useAttendanceDays();
  const todayIso = today.data?.today;
  const sweep = useAttendanceDays(
    todayIso ? addDays(todayIso, -SWEEP_DAYS) : undefined,
    todayIso ? addDays(todayIso, -1) : undefined,
    Boolean(todayIso),
  );
  const summary = useAttendanceSummary();

  useEffect(() => {
    document.title = "Attendance · Curiculy";
  }, []);

  const hours = today.data?.count_by === "hours";
  const day = today.data?.days[0];
  const unmarked = (sweep.data?.days ?? [])
    .filter((item) => item.children.some((child) => child.expected && !child.status))
    .reverse();

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Attendance</h1>
          <p className="page-lede">
            One tap a day. Curiculy suggests who did school from the lessons checked off and the activities logged; nothing
            is recorded until you say it looks right.
          </p>
        </div>
      </div>

      {today.isError ? <ErrorLine error={today.error} /> : null}
      {today.isPending ? <p className="muted">Loading today…</p> : null}
      {day && day.children.length === 0 ? (
        <p className="notice">Add your children first (Kids, in the menu above). Then you can mark each day.</p>
      ) : null}
      {day && day.children.length > 0 ? (
        <DayCard key={day.date} day={day} hours={hours} title="School today?" />
      ) : null}

      {day && day.children.length > 0 ? (
        <section className="stack" aria-labelledby="not-marked">
          <h2 className="section-title" id="not-marked">
            Not marked yet
          </h2>
          {sweep.isPending ? <p className="muted">Checking the last two weeks…</p> : null}
          {sweep.isSuccess && unmarked.length === 0 ? (
            <p className="small muted">Every school day in the last two weeks is marked.</p>
          ) : null}
          {unmarked.length ? (
            <p className="small">
              {unmarked.length} day{unmarked.length === 1 ? "" : "s"} in the last two weeks {unmarked.length === 1 ? "isn't" : "aren't"}{" "}
              marked. Suggestions come from that day's work; days with nothing checked off need you.
            </p>
          ) : null}
          {unmarked.length ? (
            <ul className="card sweep-list">
              {unmarked.map((item) => (
                <SweepDay key={item.date} day={item} hours={hours} />
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {summary.isError ? <ErrorLine error={summary.error} /> : null}
      {summary.data && summary.data.children.length > 0 ? <YearSoFar summary={summary.data} /> : null}
    </>
  );
}
