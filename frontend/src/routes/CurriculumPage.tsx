import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import {
  useAddCurriculumItem,
  useAddFromCommunity,
  useCurriculum,
  useDeleteCurriculum,
  useLibrary,
  useReference,
  useRemoveCurriculumItem,
  useSuggestions,
  useUnschedule,
  useUpdateCurriculum,
  type Curriculum,
} from "../api/parent";
import { BookCover } from "../components/library/BookCover";
import { gradeOptions, subjectOptions } from "../components/library/KindFields";
import { ScheduleStep } from "../components/planner/ScheduleStep";
import { Checklist } from "../components/ui/Checklist";
import { ErrorLine, SelectField, TextField } from "../components/ui/Fields";
import { shortDate } from "../lib/dates";

const ROLE_ORDER = ["textbook", "workbook", "online", "reading", "teacher"];
const DEFAULT_ROLE: Record<string, string> = {
  reading_book: "reading",
  workbook: "workbook",
  online_program: "online",
  textbook: "teacher",
};

function BasicsStep({ curriculum }: { curriculum: Curriculum }) {
  const reference = useReference();
  const update = useUpdateCurriculum(curriculum.id);
  const [name, setName] = useState(curriculum.name);
  const [subject, setSubject] = useState(curriculum.subject_code ?? "");
  const [grade, setGrade] = useState(curriculum.grade ?? "");
  const [days, setDays] = useState(curriculum.days_per_week ? String(curriculum.days_per_week) : "");
  const [saved, setSaved] = useState(false);
  const edit = (set: (value: string) => void) => (value: string) => {
    setSaved(false);
    set(value);
  };
  const dirty =
    name !== curriculum.name ||
    subject !== (curriculum.subject_code ?? "") ||
    grade !== (curriculum.grade ?? "") ||
    days !== (curriculum.days_per_week ? String(curriculum.days_per_week) : "");

  return (
    <form
      className="stack"
      onSubmit={(event) => {
        event.preventDefault();
        update.mutate(
          { name, subject_code: subject || null, grade: grade || null, days_per_week: days ? Number(days) : null },
          { onSuccess: () => setSaved(true) },
        );
      }}
    >
      <div className="form-grid">
        <TextField label="Name" required value={name} onChange={edit(setName)} hint="What you call it: “4th grade reading”." />
        <SelectField
          label="Subject"
          required
          value={subject}
          onChange={edit(setSubject)}
          options={subjectOptions(reference.data)}
          hint="Connects it to your child's subjects and your state's requirements."
        />
        <SelectField label="Grade" value={grade} onChange={edit(setGrade)} options={gradeOptions(reference.data)} />
        <SelectField
          label="Days a week"
          value={days}
          onChange={edit(setDays)}
          options={[1, 2, 3, 4, 5, 6, 7].map((day) => ({ value: String(day), label: `${day} days a week` }))}
          placeholder="My school days"
          hint="From the textbook when it says. A 4-day program on a 5-day week leaves a free day."
        />
      </div>
      <div className="row">
        <button type="submit" className="btn btn-primary btn-small" disabled={!dirty || update.isPending}>
          {update.isPending ? "Saving…" : "Save"}
        </button>
        {saved && !dirty ? (
          <span className="muted small" role="status">
            Saved.
          </span>
        ) : null}
      </div>
      <ErrorLine error={update.error} />
    </form>
  );
}

function ItemsStep({ curriculum }: { curriculum: Curriculum }) {
  const reference = useReference();
  const library = useLibrary();
  const add = useAddCurriculumItem(curriculum.id);
  const remove = useRemoveCurriculumItem(curriculum.id);
  const adoptEntry = useAddFromCommunity();
  const textbook = curriculum.items.find((item) => item.role === "textbook");
  const suggestions = useSuggestions(textbook?.library_item_id ?? null);
  const [pick, setPick] = useState("");
  const [role, setRole] = useState("");

  const inCurriculum = new Set(curriculum.items.map((item) => item.library_item_id));
  const available = (library.data ?? []).filter((item) => !inCurriculum.has(item.id));
  const roles = reference.data?.curriculum_roles ?? [];
  const pickedItem = available.find((item) => String(item.id) === pick);
  const defaultRole = (kind: string) => (kind === "textbook" && !textbook ? "textbook" : (DEFAULT_ROLE[kind] ?? ""));

  // What other families used alongside this textbook, minus what's already here.
  const often = (suggestions.data?.often_used_with ?? []).filter(
    (suggested) => !(suggested.library_item_id && inCurriculum.has(suggested.library_item_id)),
  );

  const groups = ROLE_ORDER.map((code) => ({
    code,
    role: roles.find((option) => option.code === code),
    items: curriculum.items.filter((item) => item.role === code),
  })).filter((group) => group.items.length > 0);

  return (
    <div className="stack-lg">
      {groups.length === 0 ? (
        <p className="muted">Nothing yet. Start with the textbook, or, for a subject without one, a workbook, website or book.</p>
      ) : null}
      {groups.map((group) => (
        <div className="role-group" key={group.code}>
          <p className="role-title">{group.role?.label ?? group.code}</p>
          {group.role ? <p className="field-hint">{group.role.hint}</p> : null}
          {group.items.map((link) => (
            <div className="item-row" key={link.id}>
              <BookCover
                small
                url={link.item.cover.url}
                title={link.item.title}
                kindLabel={link.item.kind_label}
                subjectCode={link.item.subject_code}
                kind={link.item.kind}
              />
              <div>
                <p className="result-title">{link.item.title}</p>
                <p className="result-meta">
                  {link.item.kind_label}
                  {link.item.ready ? " · ready" : " · "}
                  {link.item.ready ? null : <Link to={`/library?item=${link.library_item_id}`}>finish it in your Library</Link>}
                </p>
              </div>
              <button
                type="button"
                className="btn btn-quiet btn-small"
                disabled={remove.isPending}
                onClick={() => remove.mutate(link.library_item_id)}
                aria-label={`Take ${link.item.title} out of this curriculum`}
              >
                Take out
              </button>
            </div>
          ))}
        </div>
      ))}

      <div className="card stack">
        <p className="card-title">Add from your library</p>
        <div className="form-grid">
          <SelectField
            label="Book or site"
            value={pick}
            onChange={(value) => {
              setPick(value);
              const item = available.find((option) => String(option.id) === value);
              setRole(item ? defaultRole(item.kind) : "");
            }}
            options={available.map((item) => ({ value: String(item.id), label: `${item.title} (${item.kind_label})` }))}
            placeholder={available.length ? "Choose…" : "Everything in your library is already here"}
          />
          <SelectField
            label="As"
            value={role}
            onChange={setRole}
            options={roles.map((option) => ({ value: option.code, label: option.label }))}
            hint={roles.find((option) => option.code === role)?.hint}
          />
        </div>
        <div className="row">
          <button
            type="button"
            className="btn btn-primary btn-small"
            disabled={!pickedItem || !role || add.isPending}
            onClick={() =>
              pickedItem &&
              add.mutate(
                { library_item_id: pickedItem.id, role },
                {
                  onSuccess: () => {
                    setPick("");
                    setRole("");
                  },
                },
              )
            }
          >
            Add it
          </button>
          <Link className="btn btn-quiet btn-small" to="/library?add=1">
            Add something new to your library
          </Link>
        </div>
        <ErrorLine error={add.error ?? remove.error} />
      </div>

      {often.length > 0 ? (
        <div className="suggestion">
          <p className="card-title">Other families used these with {textbook?.item.title}</p>
          <ul className="suggestion-items">
            {often.map((suggested) => (
              <li key={`${suggested.role}-${suggested.entry.id}`} className="row-between">
                <span className="row">
                  <BookCover
                    small
                    url={suggested.entry.cover_url}
                    title={suggested.entry.title}
                    kindLabel={suggested.entry.kind_label}
                    subjectCode={suggested.entry.subject_code}
                    kind={suggested.entry.kind}
                  />
                  <span>
                    <strong>{suggested.entry.title}</strong>
                    <span className="check-why">
                      {suggested.role_label} · used by {suggested.families_count}{" "}
                      {suggested.families_count === 1 ? "family" : "families"}
                    </span>
                  </span>
                </span>
                <button
                  type="button"
                  className="btn btn-small"
                  disabled={add.isPending || adoptEntry.isPending}
                  onClick={async () => {
                    const itemId =
                      suggested.library_item_id ?? (await adoptEntry.mutateAsync(suggested.entry.id)).id;
                    add.mutate({ library_item_id: itemId, role: suggested.role });
                  }}
                >
                  Add it
                </button>
              </li>
            ))}
          </ul>
          <ErrorLine error={adoptEntry.error} />
        </div>
      ) : null}
    </div>
  );
}

function CoursesSection({ curriculum, onUnscheduled }: { curriculum: Curriculum; onUnscheduled: () => void }) {
  const unschedule = useUnschedule();
  const [confirming, setConfirming] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  if (curriculum.courses.length === 0 && !message) return null;
  return (
    <section className="card stack" aria-labelledby="on-calendar">
      <h2 className="section-title" id="on-calendar">
        On the calendar
      </h2>
      {curriculum.courses.map((course) => (
        <div className="row-between" key={course.id}>
          <span>
            <strong>{course.student_name}</strong>: {shortDate(course.start_date)}
            {course.end_date ? ` to ${shortDate(course.end_date)}` : ""}, {course.lessons_scheduled} lessons
          </span>
          {confirming === course.id ? (
            <span className="row">
              <span className="small">Take the unfinished lessons off {course.student_name}'s calendar?</span>
              <button
                type="button"
                className="btn btn-danger btn-small"
                disabled={unschedule.isPending}
                onClick={() =>
                  unschedule.mutate(course.id, {
                    onSuccess: (result) => {
                      onUnscheduled();
                      setConfirming(null);
                      setMessage(
                        `Took ${result.lessons_removed} lessons off the calendar.${result.lessons_kept ? ` ${result.lessons_kept} finished lessons stay where they were done.` : ""}`,
                      );
                    },
                  })
                }
              >
                Yes, take them off
              </button>
              <button type="button" className="btn btn-quiet btn-small" onClick={() => setConfirming(null)}>
                Keep them
              </button>
            </span>
          ) : (
            <button type="button" className="btn btn-small" onClick={() => setConfirming(course.id)}>
              Take off the calendar
            </button>
          )}
        </div>
      ))}
      {message ? (
        <p className="field-hint" role="status">
          {message}
        </p>
      ) : null}
      <ErrorLine error={unschedule.error} />
    </section>
  );
}

/** One curriculum, step by step: basics, what goes with it, ready?, and the calendar. */
export function CurriculumPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const curriculumId = Number(id);
  const query = useCurriculum(Number.isFinite(curriculumId) ? curriculumId : null);
  const remove = useDeleteCurriculum();
  const [confirming, setConfirming] = useState(false);
  // A fresh schedule form after taking a course off the calendar (not after
  // adding one: the "Done" message must survive that refresh).
  const [round, setRound] = useState(0);
  const curriculum = query.data;

  useEffect(() => {
    if (curriculum) document.title = `${curriculum.name} · Curriculum planner · Curiculy`;
  }, [curriculum]);

  if (!curriculum) {
    return query.isError ? <ErrorLine error={query.error} /> : <p className="muted">Loading…</p>;
  }

  const itemProblems = curriculum.readiness.problems;
  return (
    <>
      <div className="page-head">
        <div>
          <Link className="back-link" to="/planner">
            ← Curriculum planner
          </Link>
          <h1 className="page-title">{curriculum.name}</h1>
          <p className="page-lede">
            {[curriculum.subject_name, curriculum.grade ? `Grade ${curriculum.grade}` : null].filter(Boolean).join(" · ")}
            {curriculum.community_curriculum_id ? " · started from a curriculum other families built" : ""}
          </p>
        </div>
      </div>

      <ol className="stepper">
        <li className="card">
          <div className="stepper-head">
            <div>
              <h2 className="section-title">The basics</h2>
              <p className="field-hint">Most of this came from the textbook. Change anything that's not right.</p>
            </div>
          </div>
          <BasicsStep key={curriculum.id} curriculum={curriculum} />
        </li>
        <li className="card">
          <div className="stepper-head">
            <div>
              <h2 className="section-title">What goes with it</h2>
              <p className="field-hint">
                {curriculum.paced_by?.kind === "textbook" || !curriculum.paced_by
                  ? "The textbook sets the pace. Add the workbooks, websites and books your child uses alongside it, and the teacher's edition for you."
                  : `No textbook: ${curriculum.paced_by.title} sets the pace, and you choose how fast when you schedule it. Add anything that goes with it.`}
              </p>
            </div>
          </div>
          <ItemsStep curriculum={curriculum} />
        </li>
        <li className="card">
          <div className="stepper-head">
            <div>
              <h2 className="section-title">Ready to schedule?</h2>
              <p className="field-hint">Curiculy needs each book's details to work out the dates.</p>
            </div>
          </div>
          <Checklist
            ready={curriculum.readiness.ready}
            missing={curriculum.readiness.missing}
            problems={itemProblems}
            readyText="Everything is ready. Put it on the calendar below."
          />
          {itemProblems.length ? (
            <p className="field-hint">Open a book from the list above (“finish it in your Library”) to fill in what it's missing.</p>
          ) : null}
        </li>
        <li className="card">
          <div className="stepper-head">
            <div>
              <h2 className="section-title">Put it on the calendar</h2>
              <p className="field-hint">You'll see every date before anything is saved.</p>
            </div>
          </div>
          <ScheduleStep
            key={round}
            target={{
              kind: "curriculum",
              id: curriculum.id,
              ready: curriculum.readiness.ready,
              pacedBy: curriculum.paced_by,
              daysPerWeek: curriculum.days_per_week,
              scheduledStudentIds: curriculum.courses.map((course) => course.student_id),
            }}
          />
        </li>
      </ol>

      <CoursesSection curriculum={curriculum} onUnscheduled={() => setRound((value) => value + 1)} />

      {curriculum.courses.length === 0 ? (
        <div className="row">
          {confirming ? (
            <>
              <span className="small">Delete this curriculum? The books stay in your library.</span>
              <button
                type="button"
                className="btn btn-danger btn-small"
                disabled={remove.isPending}
                onClick={() => remove.mutate(curriculum.id, { onSuccess: () => navigate("/planner") })}
              >
                Yes, delete it
              </button>
              <button type="button" className="btn btn-quiet btn-small" onClick={() => setConfirming(false)}>
                Keep it
              </button>
            </>
          ) : (
            <button type="button" className="btn btn-danger btn-small" onClick={() => setConfirming(true)}>
              Delete this curriculum
            </button>
          )}
          <ErrorLine error={remove.error} />
        </div>
      ) : null}
    </>
  );
}
