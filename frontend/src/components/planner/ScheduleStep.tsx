import { useMemo, useState } from "react";

import { previewSchedule, useSchedule, type Curriculum, type SchedulePreview, type ScheduleResult } from "../../api/parent";
import { useStudents } from "../../api/queries";
import { shortDate, todayISO } from "../../lib/dates";
import { nextMonday } from "../../lib/structure";
import { ErrorLine, TextField } from "../ui/Fields";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/**
 * Put a curriculum on the calendar: which children, from when, on which days.
 * A preview shows every book's dates first; nothing is saved until "Put it on the calendar".
 */
export function ScheduleStep({ curriculum }: { curriculum: Curriculum }) {
  const students = useStudents(true);
  const schedule = useSchedule(curriculum.id);
  const scheduledFor = useMemo(() => new Set(curriculum.courses.map((course) => course.student_id)), [curriculum.courses]);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [start, setStart] = useState(() => nextMonday(todayISO()));
  const [weekdays, setWeekdays] = useState<number[] | null>(null);
  const [preview, setPreview] = useState<SchedulePreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<ScheduleResult | null>(null);

  const kids = (students.data ?? []).filter((student) => !scheduledFor.has(student.id));
  const chosen = picked.size ? [...picked] : kids.length === 1 ? [kids[0]!.id] : [];
  const stale = () => setPreview(null);

  const runPreview = async () => {
    setPreviewing(true);
    setError(null);
    try {
      const shown = await previewSchedule(curriculum.id, { student_ids: chosen, start_date: start, weekdays });
      setPreview(shown);
      setWeekdays(shown.weekdays);
    } catch (problem) {
      setError(problem);
    } finally {
      setPreviewing(false);
    }
  };

  if (result) {
    const lessons = result.lessons_created;
    return (
      <div className="notice notice-success stack">
        <p>
          <strong>
            Done: {lessons} lesson{lessons === 1 ? "" : "s"} on the calendar
          </strong>{" "}
          for {result.courses.map((course) => course.student_name).join(" and ")}, from {shortDate(result.courses[0]!.start_date)}
          {result.courses[0]?.end_date ? ` to ${shortDate(result.courses[0].end_date)}` : ""}.
        </p>
        <p>
          On the calendar you can open any lesson to move it, mark sick days and days off, and catch up if you fall
          behind. A short tour shows you how.
        </p>
        <p>
          <a className="btn btn-primary" href={result.calendar_url}>
            Go to the calendar
          </a>
        </p>
      </div>
    );
  }

  if (!curriculum.readiness.ready) {
    return <p className="notice notice-warn">Finish the steps above first. Then you can put it on the calendar.</p>;
  }

  if (students.isSuccess && kids.length === 0) {
    return (
      <p className="notice">
        {students.data.length === 0
          ? "Add your children first (Kids, in the menu above). Then you can put this on their calendars."
          : "This curriculum is already on every child's calendar."}
      </p>
    );
  }

  return (
    <div className="stack-lg">
      <fieldset className="field">
        <legend className="field-label">Who's doing it?</legend>
        <div className="chips">
          {kids.map((student) => (
            <button
              key={student.id}
              type="button"
              className="chip"
              aria-pressed={chosen.includes(student.id)}
              onClick={() => {
                stale();
                const next = new Set(chosen);
                if (next.has(student.id)) next.delete(student.id);
                else next.add(student.id);
                setPicked(next);
              }}
            >
              {student.name}
            </button>
          ))}
        </div>
        <p className="field-hint">Pick more than one to schedule it for siblings working through it together.</p>
      </fieldset>

      <div className="form-grid">
        <TextField
          label="Start date"
          type="date"
          required
          value={start}
          onChange={(value) => {
            stale();
            setStart(value);
          }}
          hint="The first lesson lands on the first school day on or after this date."
        />
      </div>

      <fieldset className="field">
        <legend className="field-label">Which days?</legend>
        {weekdays ? (
          <div className="weekdays">
            {DAY_NAMES.map((name, day) => (
              <button
                key={name}
                type="button"
                className="chip"
                aria-pressed={weekdays.includes(day)}
                onClick={() => {
                  stale();
                  setWeekdays((current) => {
                    const days = new Set(current ?? []);
                    if (days.has(day)) days.delete(day);
                    else days.add(day);
                    return [...days].sort();
                  });
                }}
              >
                {name}
              </button>
            ))}
          </div>
        ) : (
          <p className="field-hint">
            Your school days{curriculum.days_per_week ? `, ${curriculum.days_per_week} a week` : ""}. A 4-day program on a
            5-day week leaves a free day for catching up. You can change the days after the preview.
          </p>
        )}
      </fieldset>

      <div className="row">
        <button type="button" className="btn btn-primary" disabled={!chosen.length || !start || previewing || weekdays?.length === 0} onClick={runPreview}>
          {previewing ? "Working it out…" : preview ? "Preview again" : "Preview the dates"}
        </button>
        {!chosen.length ? <span className="field-hint">Pick a child first.</span> : null}
      </div>
      <ErrorLine error={error} />

      {preview ? (
        <section className="stack-lg" aria-label="Preview">
          {preview.warnings.map((warning) => (
            <p className="notice notice-warn" key={warning}>
              {warning}
            </p>
          ))}
          {preview.students.map((kid) => (
            <div className="card preview-kid" key={kid.student_id}>
              <p className="card-title">
                {kid.student_name}: {kid.lessons} lessons, {preview.weekday_names.join(", ")}
                {kid.finish_date ? `, finishing ${shortDate(kid.finish_date)}` : ""}
              </p>
              <table className="preview-table">
                <thead>
                  <tr>
                    <th scope="col">Book</th>
                    <th scope="col">How</th>
                    <th scope="col">Dates</th>
                  </tr>
                </thead>
                <tbody>
                  {kid.items.map((item) => (
                    <tr key={item.library_item_id}>
                      <td>{item.title}</td>
                      <td>{item.summary}</td>
                      <td>{item.first_date && item.last_date ? `${shortDate(item.first_date)} – ${shortDate(item.last_date)}` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          <div className="row">
            <button
              type="button"
              className="btn btn-primary"
              disabled={schedule.isPending}
              onClick={() =>
                schedule.mutate({ student_ids: chosen, start_date: start, weekdays }, { onSuccess: setResult })
              }
            >
              {schedule.isPending ? "Adding lessons…" : "Put it on the calendar"}
            </button>
            <span className="field-hint">You can take it off again later; finished lessons always stay.</span>
          </div>
          <ErrorLine error={schedule.error} />
        </section>
      ) : null}
    </div>
  );
}
