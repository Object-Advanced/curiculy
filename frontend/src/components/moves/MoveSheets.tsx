import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { lessonDetails, previewMove, useApplyMove, type MovePreview, type MoveRequest } from "../../api/parent";
import { useStudents } from "../../api/queries";
import { addDays, todayISO } from "../../lib/dates";
import { ErrorLine, SelectField, TextField } from "../ui/Fields";
import { Modal } from "../ui/Modal";
import { PreviewList, dayLabel } from "./PreviewList";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/**
 * The shared shape of every move: a few questions, "Preview", what changes,
 * then "Move them". Changing an answer clears the preview, so what's applied
 * is always what was shown; the server refuses if the calendar changed since.
 */
function MoveFrame({
  title,
  request,
  ready,
  onClose,
  children,
}: {
  title: string;
  request: MoveRequest | null;
  ready: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  const apply = useApplyMove();
  const [preview, setPreview] = useState<{ key: string; data: MovePreview } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<string | null>(null);
  const key = JSON.stringify(request);
  const shown = preview && preview.key === key ? preview.data : null;
  const nothing = shown && shown.changes.length === 0 && !shown.notes?.length;

  const runPreview = async () => {
    if (!request) return;
    setPreviewing(true);
    setError(null);
    try {
      setPreview({ key, data: await previewMove(request) });
    } catch (problem) {
      setError(problem);
    } finally {
      setPreviewing(false);
    }
  };

  return (
    <Modal
      title={title}
      onClose={onClose}
      wide
      footer={
        done ? (
          <>
            <a className="btn" href="/#/assignments">
              Go to the calendar
            </a>
            <button type="button" className="btn btn-primary" onClick={onClose}>
              Done
            </button>
          </>
        ) : (
          <>
            <button type="button" className="btn btn-quiet" onClick={onClose}>
              Cancel
            </button>
            {shown && !nothing ? (
              <button
                type="button"
                className="btn btn-primary"
                disabled={apply.isPending}
                onClick={() =>
                  request &&
                  apply.mutate({ request, planHash: shown.plan_hash }, { onSuccess: (result) => setDone(result.summary) })
                }
              >
                {apply.isPending ? "Moving…" : "Move them"}
              </button>
            ) : (
              <button type="button" className="btn btn-primary" disabled={!ready || previewing} onClick={() => void runPreview()}>
                {previewing ? "Working it out…" : "Preview"}
              </button>
            )}
          </>
        )
      }
    >
      <div className="stack-lg">
        {done ? (
          <p className="notice notice-success" role="status">
            Done. {done}
          </p>
        ) : (
          <>
            {children}
            {shown ? (
              <section className="stack" aria-label="What changes">
                <h3 className="section-title">What changes</h3>
                <PreviewList preview={shown} />
              </section>
            ) : null}
          </>
        )}
        <ErrorLine error={error ?? apply.error} />
      </div>
    </Modal>
  );
}

/** "Move to…": one lesson, pushing the rest of its course back or just this one. */
export function MoveLessonSheet({ assignmentId, onClose }: { assignmentId: number; onClose: () => void }) {
  const lesson = useQuery({ queryKey: ["lesson", assignmentId], queryFn: () => lessonDetails(assignmentId) });
  const [target, setTarget] = useState<string | null>(null);
  const [mode, setMode] = useState<"ripple" | "just_this">("ripple");
  const data = lesson.data;
  const day = target ?? (data ? addDays(data.scheduled_date > todayISO() ? data.scheduled_date : todayISO(), 1) : "");
  const sequenced = Boolean(data?.course_id);
  const request: MoveRequest | null = data && day ? { kind: "lesson", assignment_id: data.id, to_date: day, mode } : null;

  return (
    <MoveFrame title={data ? `Move ${data.title}` : "Move a lesson"} request={request} ready={Boolean(request)} onClose={onClose}>
      {lesson.isPending ? <p className="muted">Loading the lesson…</p> : null}
      <ErrorLine error={lesson.error} />
      {data ? (
        <>
          <p className="step-lede">
            It's on {dayLabel(data.scheduled_date)}.
            {data.status === "completed" ? " It's finished, so it stays on the day it was done." : ""}
          </p>
          <div className="form-grid">
            <TextField label="Move it to" type="date" required value={day} onChange={setTarget} />
          </div>
          {sequenced ? (
            <fieldset className="choice-cards">
              <legend className="field-label">The rest of its course</legend>
              <label className="choice-card">
                <input type="radio" name="mode" checked={mode === "ripple"} onChange={() => setMode("ripple")} />
                <span className="choice-title">Push the rest back</span>
                <span className="choice-hint">Every lesson after it moves along too, in order, on the course's days.</span>
              </label>
              <label className="choice-card">
                <input type="radio" name="mode" checked={mode === "just_this"} onChange={() => setMode("just_this")} />
                <span className="choice-title">Just this one</span>
                <span className="choice-hint">
                  Only the lessons between the two days slide by one, so they stay in order. Nothing after moves.
                </span>
              </label>
            </fieldset>
          ) : null}
        </>
      ) : null}
    </MoveFrame>
  );
}

/** "Ada is sick Tuesday" or "We're off Friday": that day's lessons move forward, each course in order. */
export function DayMoveSheet({
  initialDate,
  initialStudentIds,
  onClose,
}: {
  initialDate?: string;
  initialStudentIds?: number[];
  onClose: () => void;
}) {
  const students = useStudents(true);
  const [day, setDay] = useState(initialDate ?? todayISO());
  const [who, setWho] = useState<number[]>(initialStudentIds ?? []);
  const [calendar, setCalendar] = useState<"" | "sick" | "off">("");
  const [title, setTitle] = useState("Day off");
  const kids = students.data ?? [];
  const ahead = day >= todayISO();
  const request: MoveRequest | null = day
    ? {
        kind: "day",
        date: day,
        student_ids: who,
        title: title.trim() || "Day off",
        ...(ahead && calendar ? { add_to_calendar: calendar } : {}),
      }
    : null;

  return (
    <MoveFrame title="A day off or a sick day" request={request} ready={Boolean(request)} onClose={onClose}>
      <p className="step-lede">
        That day's lessons move forward. Each course keeps its order and its own days; other lessons go to the next school
        day.
      </p>
      <div className="form-grid">
        <TextField label="Which day" type="date" required value={day} onChange={setDay} />
      </div>
      <fieldset className="field">
        <legend className="field-label">Who</legend>
        <div className="chips">
          <button type="button" className="chip" aria-pressed={who.length === 0} onClick={() => setWho([])}>
            Everyone
          </button>
          {kids.map((kid) => (
            <button
              key={kid.id}
              type="button"
              className="chip"
              aria-pressed={who.includes(kid.id)}
              onClick={() => setWho(who.includes(kid.id) ? who.filter((id) => id !== kid.id) : [...who, kid.id])}
            >
              {kid.name}
            </button>
          ))}
        </div>
      </fieldset>
      {ahead ? (
        <div className="form-grid">
          <SelectField
            label="Put it on the calendar"
            value={calendar}
            onChange={(value) => {
              setCalendar(value as "" | "sick" | "off");
              setTitle(value === "sick" ? "Sick" : "Day off");
            }}
            options={[
              { value: "sick", label: "As a sick day" },
              { value: "off", label: "As a day off" },
            ]}
            placeholder="No, just move the lessons"
            hint="So nothing else gets scheduled on it later."
          />
          {calendar ? <TextField label="Name it" value={title} onChange={setTitle} /> : null}
        </div>
      ) : null}
    </MoveFrame>
  );
}

/** A course's new days of the week, or a pause (a co-op term, a holiday). It re-paces from today. */
export function CourseMoveSheet({
  courseId,
  courseName,
  weekdays,
  onClose,
}: {
  courseId: number;
  courseName: string;
  weekdays: number[];
  onClose: () => void;
}) {
  const [days, setDays] = useState<number[]>(weekdays);
  const [pauseFrom, setPauseFrom] = useState("");
  const [pauseTo, setPauseTo] = useState("");
  const changedDays = days.length > 0 && days.join() !== [...weekdays].sort().join();
  const paused = Boolean(pauseFrom && pauseTo);
  const request: MoveRequest | null =
    changedDays || paused
      ? {
          kind: "course",
          course_id: courseId,
          ...(changedDays ? { weekdays: days } : {}),
          ...(paused ? { pause_from: pauseFrom, pause_to: pauseTo } : {}),
        }
      : null;

  return (
    <MoveFrame title={`Change ${courseName}'s days`} request={request} ready={Boolean(request)} onClose={onClose}>
      <fieldset className="field">
        <legend className="field-label">Days of the week</legend>
        <div className="chips">
          {WEEKDAYS.map((label, index) => (
            <button
              key={label}
              type="button"
              className="chip"
              aria-pressed={days.includes(index)}
              onClick={() =>
                setDays(days.includes(index) ? days.filter((day) => day !== index) : [...days, index].sort())
              }
            >
              {label}
            </button>
          ))}
        </div>
        <p className="field-hint">The lessons from today on move onto these days, in order.</p>
      </fieldset>
      <div className="form-grid">
        <TextField label="Pause from" type="date" value={pauseFrom} onChange={setPauseFrom} hint="Optional: a co-op term, a trip." />
        <TextField label="Pause until" type="date" value={pauseTo} onChange={setPauseTo} />
      </div>
    </MoveFrame>
  );
}
