import { useId, useState } from "react";

import {
  useConfirmAttendance,
  type AttendanceChild,
  type AttendanceDay,
  type AttendanceMark,
  type AttendanceStatus,
} from "../../api/parent";
import { ErrorLine } from "../ui/Fields";

const CHOICES: { value: AttendanceStatus; label: string }[] = [
  { value: "Present", label: "Present" },
  { value: "Field trip", label: "Field trip" },
  { value: "Sick", label: "Sick" },
  { value: "Absent", label: "Absent" },
];

const PRESENT_LIKE = new Set<AttendanceStatus>(["Present", "Field trip"]);

interface Row {
  choice: AttendanceStatus | null;
  minutes: number | null;
  // A day off with no work: the choices stay folded away until asked for.
  open: boolean;
}

function startRow(child: AttendanceChild): Row {
  return {
    choice: child.status ?? child.suggestion ?? null,
    minutes: child.minutes ?? null,
    open: child.expected || Boolean(child.status),
  };
}

function hoursLabel(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours} h${rest ? ` ${rest} min` : ""}` : `${rest} min`;
}

function where(child: AttendanceChild): string {
  if (child.status) return child.source === "suggestion" ? `Marked ${child.status}, as suggested` : `Marked ${child.status}`;
  if (child.suggestion) return `${child.suggestion} (suggested)`;
  return child.expected ? "Not marked yet" : "No school";
}

/**
 * One day's attendance for every child: pre-filled from the day's work, and
 * saved only when the parent taps "Looks right". In hours mode, each present
 * child's minutes (from their lessons and activities) can be changed.
 */
export function DayCard({
  day,
  title,
  hours,
}: {
  day: AttendanceDay;
  title: string;
  hours: boolean;
}) {
  const confirm = useConfirmAttendance();
  const headingId = useId();
  const [rows, setRows] = useState<Record<number, Row>>(() =>
    Object.fromEntries(day.children.map((child) => [child.student_id, startRow(child)])),
  );
  const [saved, setSaved] = useState(false);
  const change = (studentId: number, patch: Partial<Row>) => {
    setSaved(false);
    setRows((current) => ({ ...current, [studentId]: { ...current[studentId]!, ...patch } }));
  };

  const marks: AttendanceMark[] = [];
  for (const child of day.children) {
    const row = rows[child.student_id]!;
    if (!row.choice) continue;
    const minutesChanged = hours && PRESENT_LIKE.has(row.choice) && row.minutes !== (child.minutes ?? null);
    if (row.choice === child.status && !minutesChanged) continue;
    marks.push({
      student_id: child.student_id,
      date: day.date,
      status: row.choice,
      // Only the parent's own number is kept; otherwise lessons and activities are added up.
      ...(minutesChanged ? { minutes: row.minutes } : {}),
    });
  }
  const waiting = day.children.filter((child) => child.expected && !rows[child.student_id]!.choice);
  const allMarked = day.children.every((child) => !child.expected || child.status);

  return (
    <section className="card attendance-card" aria-labelledby={headingId}>
      <div className="row-between">
        <h2 className="section-title" id={headingId}>
          {title}
        </h2>
        {day.day_off ? <span className="badge">Day off: {day.day_off}</span> : null}
        {!day.day_off && !day.school_day ? <span className="badge">Not a school day</span> : null}
      </div>
      <ul className="attendance-rows">
        {day.children.map((child) => {
          const row = rows[child.student_id]!;
          return (
            <li key={child.student_id} className="attendance-row">
              <div className="stack">
                <p>
                  <strong>{child.name}</strong> <span className="muted small">{where(child)}</span>
                </p>
                {child.reasons?.length ? <p className="small muted">{child.reasons.join(" · ")}</p> : null}
              </div>
              {row.open ? (
                <div className="stack">
                  <div className="chips" role="group" aria-label={`${child.name} on ${title}`}>
                    {CHOICES.map((choice) => (
                      <button
                        key={choice.value}
                        type="button"
                        className="chip"
                        aria-pressed={row.choice === choice.value}
                        onClick={() => change(child.student_id, { choice: choice.value })}
                      >
                        {choice.label}
                      </button>
                    ))}
                  </div>
                  {hours && row.choice && PRESENT_LIKE.has(row.choice) ? (
                    <div className="attendance-minutes small">
                      <label htmlFor={`${headingId}-${child.student_id}-minutes`}>Minutes of school</label>
                      <input
                        id={`${headingId}-${child.student_id}-minutes`}
                        className="input input-small num-input"
                        type="number"
                        min={1}
                        max={1440}
                        aria-describedby={`${headingId}-${child.student_id}-from`}
                        value={row.minutes ?? ""}
                        onChange={(event) =>
                          change(child.student_id, { minutes: event.target.value === "" ? null : Number(event.target.value) })
                        }
                      />
                      <span className="muted" id={`${headingId}-${child.student_id}-from`}>
                        {child.minutes_from_work
                          ? `${hoursLabel(child.minutes_from_work)} from lessons and activities`
                          : "No minutes on this day's lessons yet"}
                        {child.lessons_without_minutes
                          ? `; ${child.lessons_without_minutes} lesson${child.lessons_without_minutes === 1 ? " has" : "s have"} none`
                          : ""}
                      </span>
                    </div>
                  ) : null}
                </div>
              ) : (
                <button type="button" className="btn btn-quiet btn-small" onClick={() => change(child.student_id, { open: true })}>
                  Mark it anyway
                </button>
              )}
            </li>
          );
        })}
      </ul>
      <div className="row">
        <button
          type="button"
          className="btn btn-primary"
          disabled={marks.length === 0 || confirm.isPending}
          onClick={() => confirm.mutate(marks, { onSuccess: () => setSaved(true) })}
        >
          {confirm.isPending ? "Saving…" : "Looks right"}
        </button>
        <span className="small muted" role="status">
          {saved
            ? "Saved."
            : waiting.length
              ? `${waiting.map((child) => child.name).join(" and ")} ${waiting.length === 1 ? "isn't" : "aren't"} marked: pick one, or leave it for later.`
              : allMarked && marks.length === 0
                ? "Everyone's marked."
                : ""}
        </span>
      </div>
      <ErrorLine error={confirm.error} />
    </section>
  );
}
