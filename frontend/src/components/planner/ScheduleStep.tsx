import { useMemo, useState } from "react";

import {
  previewItemSchedule,
  previewSchedule,
  useSchedule,
  useScheduleItem,
  type Pace,
  type SchedulePreview,
  type ScheduleRequest,
  type ScheduleResult,
} from "../../api/parent";
import { useStudents } from "../../api/queries";
import { shortDate, todayISO } from "../../lib/dates";
import { nextMonday } from "../../lib/structure";
import { ErrorLine, NumberField, TextField } from "../ui/Fields";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** What's being scheduled: a curriculum from the planner, or one library item on its own. */
export interface ScheduleTarget {
  kind: "curriculum" | "item";
  id: number;
  ready: boolean;
  pacedBy: Pace | null | undefined;
  daysPerWeek: number | null | undefined;
  scheduledStudentIds: number[];
}

type PaceChoice = "year" | "pages" | "chapters" | "finish";

function paceOptions(pace: Pace): { value: PaceChoice; label: string }[] {
  const options: { value: PaceChoice; label: string }[] = [];
  const pages = pace.kind === "workbook" || pace.kind === "reading_book";
  if (pages) options.push({ value: "pages", label: "A number of pages a day" });
  if (pages && pace.chapters > 0) options.push({ value: "chapters", label: "A chapter or more a day" });
  options.push({ value: "finish", label: "Finish by a date" });
  options.push({
    value: "year",
    label:
      pace.kind === "online_program" && pace.measure === "lessons"
        ? "One lesson each session, until it's done"
        : "Spread it over the rest of the school year",
  });
  return options;
}

function defaultChoice(pace: Pace): PaceChoice {
  if ((pace.kind === "workbook" || pace.kind === "reading_book") && pace.usual_pages_per_day) return "pages";
  return "year";
}

/**
 * Put a curriculum (or one book) on the calendar: which children, from when,
 * on which days, and, without a textbook, how fast. A preview shows every
 * book's dates first; nothing is saved until "Put it on the calendar".
 */
export function ScheduleStep({ target }: { target: ScheduleTarget }) {
  const students = useStudents(true);
  const scheduleCurriculum = useSchedule(target.id);
  const scheduleItem = useScheduleItem(target.id);
  const schedule = target.kind === "curriculum" ? scheduleCurriculum : scheduleItem;
  const scheduledFor = useMemo(() => new Set(target.scheduledStudentIds), [target.scheduledStudentIds]);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [start, setStart] = useState(() => nextMonday(todayISO()));
  const [weekdays, setWeekdays] = useState<number[] | null>(null);
  const pace = target.pacedBy && target.pacedBy.kind !== "textbook" ? target.pacedBy : null;
  const [choice, setChoice] = useState<PaceChoice>(() => (pace ? defaultChoice(pace) : "year"));
  const [pagesPerDay, setPagesPerDay] = useState<number | null>(pace?.usual_pages_per_day ?? 5);
  const [chaptersPerDay, setChaptersPerDay] = useState<number | null>(1);
  const [finishBy, setFinishBy] = useState("");
  const [minutes, setMinutes] = useState<number | null>(null);
  const [preview, setPreview] = useState<SchedulePreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<ScheduleResult | null>(null);

  const kids = (students.data ?? []).filter((student) => !scheduledFor.has(student.id));
  const chosen = picked.size ? [...picked] : kids.length === 1 ? [kids[0]!.id] : [];
  const stale = () => setPreview(null);
  const paceMissing =
    pace !== null &&
    ((choice === "pages" && !pagesPerDay) || (choice === "chapters" && !chaptersPerDay) || (choice === "finish" && !finishBy));

  const request = (): ScheduleRequest => ({
    student_ids: chosen,
    start_date: start,
    weekdays,
    ...(pace && choice === "pages" ? { pages_per_day: pagesPerDay } : {}),
    ...(pace && choice === "chapters" ? { chapters_per_day: chaptersPerDay } : {}),
    ...(pace && choice === "finish" ? { finish_by: finishBy } : {}),
    ...(minutes ? { minutes_per_lesson: minutes } : {}),
  });

  const runPreview = async () => {
    setPreviewing(true);
    setError(null);
    try {
      const body = request();
      const shown =
        target.kind === "curriculum" ? await previewSchedule(target.id, body) : await previewItemSchedule(target.id, body);
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

  if (!target.ready) {
    return (
      <p className="notice notice-warn">
        {target.kind === "curriculum"
          ? "Finish the steps above first. Then you can put it on the calendar."
          : "Finish what's missing above first. Then you can put it on the calendar."}
      </p>
    );
  }

  if (students.isSuccess && kids.length === 0) {
    return (
      <p className="notice">
        {students.data.length === 0
          ? "Add your children first (Kids, in the menu above). Then you can put this on their calendars."
          : "This is already on every child's calendar."}
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
        <NumberField
          label="About how many minutes a lesson?"
          max={600}
          value={minutes}
          onChange={setMinutes}
          hint="Optional. Families who count hours add these up. A lesson list's own times, and an online site's session length, come first."
        />
      </div>

      {pace ? (
        <fieldset className="field">
          <legend className="field-label">How fast?</legend>
          <p className="field-hint">
            There's no textbook to set the pace, so you choose it for {pace.title}
            {pace.total_pages ? ` (${pace.total_pages} pages${pace.chapters ? `, ${pace.chapters} chapters` : ""})` : ""}.
          </p>
          <div className="pace-options">
            {paceOptions(pace).map((option) => (
              <div className="pace-option" key={option.value}>
                <label>
                  <input
                    type="radio"
                    name={`pace-${target.kind}-${target.id}`}
                    checked={choice === option.value}
                    onChange={() => {
                      stale();
                      setChoice(option.value);
                    }}
                  />
                  <span>{option.label}</span>
                </label>
                {option.value === "pages" && choice === "pages" ? (
                  <input
                    className="input input-small num-input"
                    type="number"
                    min={1}
                    max={200}
                    aria-label="Pages a day"
                    value={pagesPerDay ?? ""}
                    onChange={(event) => {
                      stale();
                      setPagesPerDay(event.target.value ? Number(event.target.value) : null);
                    }}
                  />
                ) : null}
                {option.value === "chapters" && choice === "chapters" ? (
                  <input
                    className="input input-small num-input"
                    type="number"
                    min={1}
                    max={20}
                    aria-label="Chapters a day"
                    value={chaptersPerDay ?? ""}
                    onChange={(event) => {
                      stale();
                      setChaptersPerDay(event.target.value ? Number(event.target.value) : null);
                    }}
                  />
                ) : null}
                {option.value === "finish" && choice === "finish" ? (
                  <input
                    className="input input-small"
                    type="date"
                    aria-label="Finish by"
                    min={start}
                    value={finishBy}
                    onChange={(event) => {
                      stale();
                      setFinishBy(event.target.value);
                    }}
                  />
                ) : null}
              </div>
            ))}
          </div>
        </fieldset>
      ) : null}

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
            Your school days{target.daysPerWeek ? `, ${target.daysPerWeek} a week` : ""}.
            {target.daysPerWeek ? " A 4-day program on a 5-day week leaves a free day for catching up." : ""} You can change
            the days after the preview.
          </p>
        )}
      </fieldset>

      <div className="row">
        <button
          type="button"
          className="btn btn-primary"
          disabled={!chosen.length || !start || previewing || weekdays?.length === 0 || paceMissing}
          onClick={runPreview}
        >
          {previewing ? "Working it out…" : preview ? "Preview again" : "Preview the dates"}
        </button>
        {!chosen.length ? <span className="field-hint">Pick a child first.</span> : null}
      </div>
      <ErrorLine error={error} />

      {preview ? (
        <section className="stack-lg" aria-label="Preview">
          <p className="small">
            <strong>Pace:</strong> {preview.pace}.
          </p>
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
              onClick={() => schedule.mutate(request(), { onSuccess: setResult })}
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
