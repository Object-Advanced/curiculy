import type { MovePreview } from "../../api/parent";

/** "Tue, Oct 13": short, with the weekday, since moves are about which day. */
export function dayLabel(iso: string): string {
  const day = new Date(`${iso}T00:00:00Z`);
  return day.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });
}

const SHOWN = 8;

/**
 * What a move does, before anything changes: the summary, the plan checker's
 * warnings, anything else it adds, each course's finish date, and the lessons
 * that move (the first few, then a count).
 */
export function PreviewList({ preview }: { preview: MovePreview }) {
  const changes = preview.changes;
  return (
    <div className="stack move-preview">
      <p>
        <strong>{preview.summary}</strong>
      </p>
      {preview.warnings?.length ? (
        <ul className="notice notice-warn move-warnings" aria-label="Worth knowing">
          {preview.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
      {preview.notes?.length ? (
        <ul className="move-notes small">
          {preview.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
      {preview.courses.length ? (
        <ul className="move-notes small">
          {preview.courses.map((course) => (
            <li key={course.course_id}>
              {course.course_name} ({course.student_name})
              {course.finish_after
                ? course.finish_after === course.finish_before
                  ? `: still finishes ${dayLabel(course.finish_after)}`
                  : `: finishes ${dayLabel(course.finish_after)}${course.finish_before ? ` instead of ${dayLabel(course.finish_before)}` : ""}`
                : ""}
            </li>
          ))}
        </ul>
      ) : null}
      {changes.length ? (
        <details className="move-changes">
          <summary>What moves</summary>
          <ul className="small">
            {changes.slice(0, SHOWN).map((change) => (
              <li key={change.assignment_id}>
                {change.title}: {dayLabel(change.from_date)}
                {change.skipped ? " → skipped" : change.to_date ? ` → ${dayLabel(change.to_date)}` : ""}
              </li>
            ))}
            {changes.length > SHOWN ? <li className="muted">…and {changes.length - SHOWN} more, in order.</li> : null}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
