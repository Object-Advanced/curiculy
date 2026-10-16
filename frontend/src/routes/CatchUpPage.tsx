import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { useBehind } from "../api/parent";
import { CatchUpSheet } from "../components/moves/CatchUpSheet";
import { DayMoveSheet, MoveLessonSheet } from "../components/moves/MoveSheets";
import { dayLabel } from "../components/moves/PreviewList";
import { ErrorLine } from "../components/ui/Fields";

/**
 * Catch up: the courses with lessons left on days that have passed, each with
 * its catch-up sheet, and a day off or sick day for one child or everyone.
 * Links open a sheet directly: `?course=<id>`, `?move=<lesson id>` (the
 * calendar's "Move to…"), `?day=<date>&student=<id>` (from Attendance).
 */
export function CatchUpPage() {
  const [params, setParams] = useSearchParams();
  const behind = useBehind();
  const [dayOpen, setDayOpen] = useState(false);

  useEffect(() => {
    document.title = "Catch up · Curiculy";
  }, []);

  const courseId = params.get("course") ? Number(params.get("course")) : null;
  const moveId = params.get("move") ? Number(params.get("move")) : null;
  const day = params.get("day");
  const student = params.get("student") ? Number(params.get("student")) : null;
  const close = () => {
    setDayOpen(false);
    setParams({}, { replace: true });
  };
  const courses = behind.data ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Catch up</h1>
          <p className="page-lede">
            Life happens. Pick how each course catches up, or move a day's lessons for a sick day or a day off. Every change
            shows what it does first, and finished lessons never move.
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn" onClick={() => setDayOpen(true)}>
            A day off or sick day
          </button>
        </div>
      </div>

      <section className="stack" aria-labelledby="behind-title">
        <h2 className="section-title" id="behind-title">
          Behind
        </h2>
        <ErrorLine error={behind.error} />
        {behind.isPending ? <p className="muted">Checking every course…</p> : null}
        {behind.isSuccess && courses.length === 0 ? (
          <p className="notice notice-success">Nobody's behind: every course's lessons are on today or later.</p>
        ) : null}
        {courses.length ? (
          <ul className="card sweep-list">
            {courses.map((course) => (
              <li className="sweep-day" key={course.course_id}>
                <div className="row-between">
                  <p>
                    <strong>{course.course_name}</strong>{" "}
                    <span className="small muted">
                      {course.student_name}: {course.behind} lesson{course.behind === 1 ? "" : "s"} behind, since{" "}
                      {dayLabel(course.behind_since)}
                    </span>
                  </p>
                  <button
                    type="button"
                    className="btn btn-small btn-primary"
                    aria-label={`Catch up ${course.course_name} for ${course.student_name}`}
                    onClick={() => setParams({ course: String(course.course_id) }, { replace: true })}
                  >
                    Catch up
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
        <p className="small muted">
          Lessons added by hand (not from the Curriculum planner) catch up with Recalibrate on the calendar.
        </p>
      </section>

      {courseId !== null ? <CatchUpSheet courseId={courseId} onClose={close} /> : null}
      {moveId !== null ? <MoveLessonSheet assignmentId={moveId} onClose={close} /> : null}
      {dayOpen || day ? (
        <DayMoveSheet
          initialDate={day ?? undefined}
          initialStudentIds={student !== null ? [student] : undefined}
          onClose={close}
        />
      ) : null}
    </>
  );
}
